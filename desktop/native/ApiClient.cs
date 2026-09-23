using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace SamrukDesktop
{
    public sealed class ApiException : Exception
    {
        public int StatusCode { get; private set; }
        public ApiException(string message, int statusCode = 0, Exception inner = null)
            : base(message, inner) { StatusCode = statusCode; }
    }

    public sealed class ApiClient : IDisposable
    {
        private const int JsonLimit = 32 * 1024 * 1024;
        private const int ExportLimit = 64 * 1024 * 1024;
        private readonly HttpClient client;
        private readonly string baseUrl;

        public ApiClient(string url)
        {
            baseUrl = Settings.ValidateUrl(url);
            var handler = new HttpClientHandler
            {
                AllowAutoRedirect = false,
                UseProxy = false,
                UseCookies = false,
                UseDefaultCredentials = false,
                AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate
            };
            client = new HttpClient(handler);
            client.Timeout = Timeout.InfiniteTimeSpan;
        }

        public async Task<HealthResult> HealthAsync(CancellationToken ct)
        {
            byte[] bytes = await SendAsync(HttpMethod.Get, "/health", null, 10, JsonLimit, ct).ConfigureAwait(false);
            var data = ParseObject(bytes);
            Require(data, "status", "local_only");
            HealthResult value = Convert<HealthResult>(data);
            if (String.IsNullOrWhiteSpace(value.status) || !(data["local_only"] is bool)) InvalidPayload();
            return value;
        }

        public async Task<List<Meeting>> ListAsync(CancellationToken ct)
        {
            byte[] bytes = await SendAsync(HttpMethod.Get, "/api/meetings", null, 30, JsonLimit, ct).ConfigureAwait(false);
            var data = ParseObject(bytes);
            Require(data, "items");
            var rows = data["items"] as object[];
            if (rows == null) InvalidPayload();
            var meetings = new List<Meeting>();
            foreach (object row in rows) meetings.Add(ParseMeeting(row as Dictionary<string, object>));
            return meetings;
        }

        public async Task<Meeting> UploadAsync(string path, string title, CancellationToken ct)
        {
            ct.ThrowIfCancellationRequested();
            string extension = Path.GetExtension(path).ToLowerInvariant();
            string mime;
            switch (extension)
            {
                case ".wav": mime = "audio/wav"; break;
                case ".mp3": mime = "audio/mpeg"; break;
                case ".m4a": mime = "audio/mp4"; break;
                case ".mp4": mime = "video/mp4"; break;
                default: throw new ApiException("Выберите запись WAV, MP3, M4A или MP4.");
            }
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 65536, true))
            using (var content = new MultipartFormDataContent())
            {
                if (stream.Length == 0) throw new ApiException("Выбранный файл пуст.");
                var file = new StreamContent(stream, 65536);
                file.Headers.ContentType = new MediaTypeHeaderValue(mime);
                content.Add(file, "file", Path.GetFileName(path));
                if (!String.IsNullOrWhiteSpace(title)) content.Add(new StringContent(title.Trim(), Encoding.UTF8), "title");
                // No retry: a timed-out POST may already have created a meeting.
                byte[] bytes = await SendAsync(HttpMethod.Post, "/api/meetings", content, 600, JsonLimit, ct).ConfigureAwait(false);
                return ParseMeeting(ParseObject(bytes));
            }
        }

        public async Task<Meeting> GetAsync(string id, CancellationToken ct)
        {
            byte[] bytes = await SendAsync(HttpMethod.Get, MeetingPath(id), null, 30, JsonLimit, ct).ConfigureAwait(false);
            Meeting value = ParseMeeting(ParseObject(bytes));
            if (value.id != id) InvalidPayload();
            return value;
        }

        public async Task<MeetingResult> ResultAsync(string id, CancellationToken ct)
        {
            byte[] bytes = await SendAsync(HttpMethod.Get, MeetingPath(id) + "/result", null, 60, JsonLimit, ct).ConfigureAwait(false);
            var data = ParseObject(bytes);
            Require(data, "meeting_id", "processing_state", "local_only", "summary", "transcript", "tasks", "exports");
            var result = Convert<MeetingResult>(data);
            if (result.meeting_id != id || result.processing_state != "completed" ||
                !(data["local_only"] is bool) || !result.local_only || result.summary == null ||
                result.transcript == null || result.tasks == null || result.exports == null) InvalidPayload();
            var segments = data["transcript"] as object[];
            var tasks = data["tasks"] as object[];
            if (segments == null || tasks == null) InvalidPayload();
            foreach (object segment in segments)
                Require(segment as Dictionary<string, object>, "speaker", "start", "end", "text", "detected_languages");
            foreach (Segment segment in result.transcript)
            {
                if (segment == null || String.IsNullOrWhiteSpace(segment.speaker) || segment.text == null ||
                    segment.start < 0 || segment.end < segment.start || Double.IsNaN(segment.start) ||
                    Double.IsNaN(segment.end) || Double.IsInfinity(segment.start) || Double.IsInfinity(segment.end) ||
                    segment.detected_languages == null) InvalidPayload();
                foreach (string language in segment.detected_languages)
                    if (String.IsNullOrWhiteSpace(language)) InvalidPayload();
            }
            foreach (object task in tasks)
                Require(task as Dictionary<string, object>, "assignee", "task", "deadline", "assigned_by", "source_speaker", "source_text");
            foreach (MeetingTask task in result.tasks)
                if (task == null || String.IsNullOrWhiteSpace(task.task) || task.source_speaker == null || task.source_text == null)
                    InvalidPayload();
            foreach (string format in result.exports)
                if (format != "docx" && format != "pdf") InvalidPayload();
            return result;
        }

        public async Task<byte[]> ExportAsync(string id, string format, CancellationToken ct)
        {
            if (format != "docx" && format != "pdf") throw new ArgumentException("Доступен экспорт DOCX или PDF.");
            byte[] bytes = await SendAsync(HttpMethod.Get, MeetingPath(id) + "/export?format=" + format,
                null, 90, ExportLimit, ct).ConfigureAwait(false);
            // Reject an HTML/JSON error page accidentally returned with HTTP 200.
            bool valid = format == "pdf"
                ? bytes.Length >= 5 && Encoding.ASCII.GetString(bytes, 0, 5) == "%PDF-"
                : bytes.Length >= 4 && bytes[0] == 0x50 && bytes[1] == 0x4b && bytes[2] == 3 && bytes[3] == 4;
            if (!valid) throw new ApiException("Backend вернул некорректный файл экспорта.");
            return bytes;
        }

        private async Task<byte[]> SendAsync(HttpMethod method, string path, HttpContent content,
            int seconds, int limit, CancellationToken ct)
        {
            using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct))
            using (var request = new HttpRequestMessage(method, baseUrl + path))
            {
                timeout.CancelAfter(TimeSpan.FromSeconds(seconds));
                request.Content = content;
                request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue(
                    path.IndexOf("/export?", StringComparison.Ordinal) >= 0 ? "*/*" : "application/json"));
                try
                {
                    using (HttpResponseMessage response = await client.SendAsync(request,
                        HttpCompletionOption.ResponseHeadersRead, timeout.Token).ConfigureAwait(false))
                    {
                        int status = (int)response.StatusCode;
                        if (status >= 300 && status < 400)
                            throw new ApiException("Backend предложил перенаправление. Укажите прямой адрес локального сервера в настройках.", status);
                        if (!response.IsSuccessStatusCode)
                        {
                            byte[] error = await ReadLimitedAsync(response.Content, 65536, timeout.Token).ConfigureAwait(false);
                            throw BuildHttpError(status, error);
                        }
                        return await ReadLimitedAsync(response.Content, limit, timeout.Token).ConfigureAwait(false);
                    }
                }
                catch (OperationCanceledException ex)
                {
                    ct.ThrowIfCancellationRequested();
                    string message = method == HttpMethod.Post
                        ? "Время загрузки истекло. Встреча могла быть создана: обновите список перед повторной отправкой."
                        : "Backend не ответил вовремя. Проверьте состояние сервера и подключение.";
                    throw new ApiException(message, 0, ex);
                }
                catch (HttpRequestException ex)
                {
                    string message = method == HttpMethod.Post
                        ? "Связь с backend прервалась. Встреча могла быть создана: проверьте список перед повторной отправкой."
                        : "Не удалось связаться с backend. Проверьте адрес, запуск сервера и подключение к локальной сети.";
                    throw new ApiException(message, 0, ex);
                }
                catch (IOException ex)
                {
                    throw new ApiException("Передача данных прервалась. Проверьте подключение; не повторяйте загрузку, пока не проверите список встреч.", 0, ex);
                }
            }
        }

        private static async Task<byte[]> ReadLimitedAsync(HttpContent content, int limit, CancellationToken ct)
        {
            if (content == null) throw new ApiException("Backend вернул пустой ответ.");
            if (content.Headers.ContentLength.HasValue && content.Headers.ContentLength.Value > limit)
                throw new ApiException("Ответ backend превышает допустимый размер.");
            using (Stream stream = await content.ReadAsStreamAsync().ConfigureAwait(false))
            using (CancellationTokenRegistration cancellation = ct.Register(delegate
            {
                // Framework HTTP streams do not consistently interrupt an in-flight read
                // when only its CancellationToken is cancelled. Close this response only.
                try { stream.Dispose(); }
                catch (IOException) { }
            }))
            using (var output = new MemoryStream())
            {
                byte[] buffer = new byte[65536];
                try
                {
                    while (true)
                    {
                        ct.ThrowIfCancellationRequested();
                        int count = await stream.ReadAsync(buffer, 0, buffer.Length, ct).ConfigureAwait(false);
                        if (count == 0) break;
                        if (output.Length + count > limit) throw new ApiException("Ответ backend превышает допустимый размер.");
                        output.Write(buffer, 0, count);
                    }
                }
                catch (IOException) { ct.ThrowIfCancellationRequested(); throw; }
                catch (ObjectDisposedException) { ct.ThrowIfCancellationRequested(); throw; }
                ct.ThrowIfCancellationRequested();
                return output.ToArray();
            }
        }

        private static string MeetingPath(string id)
        {
            if (String.IsNullOrWhiteSpace(id) || id.Length > 1024)
                throw new ArgumentException("Некорректный идентификатор встречи.");
            return "/api/meetings/" + Uri.EscapeDataString(id);
        }

        private static JavaScriptSerializer Serializer()
        {
            return new JavaScriptSerializer { MaxJsonLength = JsonLimit, RecursionLimit = 128 };
        }

        private static Dictionary<string, object> ParseObject(byte[] bytes)
        {
            try
            {
                var data = Serializer().DeserializeObject(new UTF8Encoding(false, true).GetString(bytes))
                    as Dictionary<string, object>;
                if (data == null) InvalidPayload();
                return data;
            }
            catch (ArgumentException ex) { throw new ApiException("Backend вернул некорректный JSON. Проверьте адрес и версию API.", 0, ex); }
            catch (InvalidOperationException ex) { throw new ApiException("Backend вернул некорректный JSON. Проверьте адрес и версию API.", 0, ex); }
        }

        private static T Convert<T>(Dictionary<string, object> data)
        {
            try { return Serializer().ConvertToType<T>(data); }
            catch (ArgumentException ex) { throw new ApiException("Ответ backend не соответствует API v1.", 0, ex); }
            catch (InvalidOperationException ex) { throw new ApiException("Ответ backend не соответствует API v1.", 0, ex); }
            catch (FormatException ex) { throw new ApiException("Ответ backend не соответствует API v1.", 0, ex); }
            catch (OverflowException ex) { throw new ApiException("Ответ backend не соответствует API v1.", 0, ex); }
        }

        private static Meeting ParseMeeting(Dictionary<string, object> data)
        {
            Require(data, "id", "title", "created_at", "status", "stage", "error");
            Meeting value = Convert<Meeting>(data);
            DateTimeOffset created;
            if (String.IsNullOrWhiteSpace(value.id) || String.IsNullOrWhiteSpace(value.title) ||
                !DateTimeOffset.TryParse(value.created_at, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out created) ||
                (value.status != "queued" && value.status != "processing" && value.status != "completed" && value.status != "failed"))
                InvalidPayload();
            if (value.stage != null && value.stage != "preprocessing" && value.stage != "transcribing" &&
                value.stage != "diarizing" && value.stage != "analyzing") InvalidPayload();
            if ((value.status == "completed" || value.status == "failed") && value.stage != null) InvalidPayload();
            if (value.error != null && (String.IsNullOrWhiteSpace(value.error.code) || String.IsNullOrWhiteSpace(value.error.message)))
                InvalidPayload();
            return value;
        }

        private static void Require(Dictionary<string, object> data, params string[] fields)
        {
            if (data == null) InvalidPayload();
            foreach (string field in fields) if (!data.ContainsKey(field)) InvalidPayload();
        }

        private static void InvalidPayload()
        {
            throw new ApiException("Ответ backend не соответствует согласованному API v1. Проверьте версию сервера.");
        }

        private static ApiException BuildHttpError(int status, byte[] bytes)
        {
            if (status == 501)
                return new ApiException("Backend пока работает как каркас: обработка записей ещё не реализована (HTTP 501).", status);
            string message;
            switch (status)
            {
                case 404: message = "Встреча или метод API не найдены. Обновите список и проверьте версию backend."; break;
                case 409: message = "Результат или экспорт ещё не готовы. Дождитесь завершения обработки."; break;
                case 413: message = "Файл превышает лимит размера на сервере."; break;
                case 415: message = "Сервер не поддерживает этот формат записи."; break;
                case 422: message = "Сервер отклонил поля запроса. Проверьте файл и совместимость API."; break;
                case 503: message = "Сервис обработки временно недоступен. Проверьте backend и локальные модели."; break;
                case 401:
                case 403: message = "Сервер отказал в доступе. Проверьте адрес и настройки доступа backend."; break;
                default: message = "Backend вернул ошибку HTTP " + status.ToString(CultureInfo.InvariantCulture) + "."; break;
            }
            // Only contract error text is displayed; never echo HTML or validation input values.
            try
            {
                var payload = Serializer().DeserializeObject(Encoding.UTF8.GetString(bytes)) as Dictionary<string, object>;
                object detail;
                if (payload != null && payload.TryGetValue("detail", out detail))
                {
                    string explanation = detail as string;
                    var error = detail as Dictionary<string, object>;
                    object errorMessage;
                    if (error != null && error.TryGetValue("message", out errorMessage)) explanation = errorMessage as string;
                    if (explanation == null && detail is object[])
                    {
                        var reasons = new List<string>();
                        foreach (object item in (object[])detail)
                        {
                            var validation = item as Dictionary<string, object>;
                            if (validation != null && validation.TryGetValue("msg", out errorMessage) && errorMessage is string)
                                reasons.Add((string)errorMessage);
                            if (reasons.Count == 3) break;
                        }
                        explanation = String.Join("; ", reasons);
                    }
                    if (!String.IsNullOrWhiteSpace(explanation)) message += "\n" + SafeErrorText(explanation);
                }
            }
            catch (ArgumentException) { }
            catch (InvalidOperationException) { }
            return new ApiException(message, status);
        }

        private static string SafeErrorText(string value)
        {
            var output = new StringBuilder();
            foreach (char character in value)
            {
                if (!Char.IsControl(character)) output.Append(character);
                else if (character == '\r' || character == '\n' || character == '\t') output.Append(' ');
                if (output.Length >= 500) break;
            }
            return output.ToString();
        }

        public void Dispose() { client.Dispose(); }
    }
}
