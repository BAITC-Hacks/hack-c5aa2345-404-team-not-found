using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Xml;
using SamrukDesktop;

internal static class NativeChecks
{
    private static readonly List<object> Results = new List<object>();
    private static int failures;
    private static string output;
    private static MeetingResult demo;

    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    private static void Check(string name, Action action)
    {
        try { action(); Record(name, null); }
        catch (Exception error) { Record(name, error); }
    }

    private static async Task CheckAsync(string name, Func<Task> action)
    {
        try { await action(); Record(name, null); }
        catch (Exception error) { Record(name, error); }
    }

    private static void Record(string name, Exception error)
    {
        if (error != null) failures++;
        Results.Add(new { name = name, passed = error == null, error = error == null ? null : error.ToString() });
        Console.WriteLine((error == null ? "PASS " : "FAIL ") + name + (error == null ? "" : ": " + error.Message));
    }

    private static async Task ExpectApi(Func<Task> action, int status)
    {
        try { await action(); }
        catch (ApiException error)
        {
            Assert(error.StatusCode == status, "Unexpected HTTP status: " + error.StatusCode);
            Assert(!String.IsNullOrWhiteSpace(error.Message), "Missing friendly error");
            return;
        }
        throw new Exception("Expected ApiException");
    }

    private static async Task Run(string url)
    {
        Check("settings_origin_normalization", delegate
        {
            Assert(Settings.ValidateUrl(" http://LOCALHOST:8000/ ") == "http://localhost:8000", "URL normalization failed");
            Assert(Settings.ValidateUrl("http://192.168.1.12:8000") == "http://192.168.1.12:8000", "LAN URL rejected");
            string ipv6 = Settings.ValidateUrl("http://[::1]:8000/");
            Uri normalized = new Uri(ipv6);
            Assert(IPAddress.IsLoopback(IPAddress.Parse(normalized.DnsSafeHost)) && normalized.Port == 8000,
                "IPv6 loopback changed: " + ipv6);
        });
        Check("settings_rejects_secrets_and_non_origins", delegate
        {
            string[] invalid = { null, "", "file:///C:/secret", "https://user:pass@localhost", "http://localhost?token=secret",
                "http://localhost#secret", "http://localhost/api", "http://localhost:0", "http://localhost:65536", "http://local host", "http://localhost\\secret" };
            foreach (string value in invalid)
            {
                bool rejected = false;
                try { Settings.ValidateUrl(value); } catch (ArgumentException) { rejected = true; }
                Assert(rejected, "Unexpected accepted URL: " + value);
            }
        });
        Check("embedded_demo_loads_and_contains_kazakh", delegate
        {
            Type form = typeof(MeetingResult).Assembly.GetType("SamrukDesktop.MainForm", true);
            MethodInfo reader = form.GetMethod("ReadDemo", BindingFlags.NonPublic | BindingFlags.Static);
            Assert(reader != null, "ReadDemo missing");
            demo = (MeetingResult)reader.Invoke(null, new object[0]);
            Assert(demo != null && demo.local_only && demo.transcript.Count > 0 && demo.tasks.Count > 0, "Incomplete embedded demo");
            Assert(demo.transcript[0].text.Contains("Айдос") && demo.transcript[0].text.Contains("ертеңге"), "Kazakh text missing");
        });
        Check("docx_package_xml_and_kazakh_roundtrip", delegate
        {
            Assert(demo != null, "Demo prerequisite failed");
            string path = Path.Combine(output, "native-demo.docx");
            LocalExport.SaveDocx(demo, "Қазақша & Русский <протокол>", path, true);
            using (ZipArchive archive = ZipFile.OpenRead(path))
            {
                string[] required = { "[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml", "word/_rels/document.xml.rels" };
                foreach (string name in required)
                {
                    ZipArchiveEntry entry = archive.GetEntry(name);
                    Assert(entry != null, "DOCX missing " + name);
                    var xml = new XmlDocument { XmlResolver = null };
                    using (Stream stream = entry.Open()) xml.Load(stream);
                    if (name == "word/document.xml")
                    {
                        Assert(xml.InnerText.Contains("Қазақша & Русский <протокол>"), "Title was not preserved");
                        Assert(xml.InnerText.Contains(demo.transcript[0].text), "Kazakh transcript was not preserved");
                        Assert(xml.InnerText.Contains(demo.tasks[0].source_text), "Task evidence was not preserved");
                        Assert(xml.InnerText.Contains("DEMO") && xml.InnerText.Contains("синтетический"), "Demo label missing");
                    }
                }
            }
        });
        Check("docx_atomic_overwrite_and_invalid_xml_characters", delegate
        {
            string path = Path.Combine(output, "native-demo-replaced.docx");
            File.WriteAllText(path, "old document");
            LocalExport.SaveDocx(demo, "Жаңарту \u0001 \uD800", path, false);
            using (ZipArchive archive = ZipFile.OpenRead(path))
            using (Stream stream = archive.GetEntry("word/document.xml").Open())
            {
                var xml = new XmlDocument { XmlResolver = null };
                xml.Load(stream);
                Assert(xml.InnerText.Contains("Жаңарту") && xml.InnerText.Contains("\uFFFD"), "Invalid XML characters not cleaned");
                Assert(!xml.InnerText.Contains("DEMO —"), "Real document incorrectly marked demo");
            }
            Assert(Directory.GetFiles(output, ".samruk-export-*.tmp").Length == 0, "Temporary export leaked");
        });

        byte[] recording = Encoding.ASCII.GetBytes("RIFF_SYNTHETIC_UPLOAD_FIXTURE_NO_SPEECH");
        string recordingPath = Path.Combine(output, "sample.wav");
        File.WriteAllBytes(recordingPath, recording);
        using (var api = new ApiClient(url))
        {
            await CheckAsync("api_health", async delegate
            {
                HealthResult health = await api.HealthAsync(CancellationToken.None);
                Assert(health.status == "fixture" && health.local_only, "Unexpected health");
            });
            await CheckAsync("api_list_items_envelope", async delegate
            {
                List<Meeting> meetings = await api.ListAsync(CancellationToken.None);
                Assert(meetings.Count == 1 && meetings[0].id == "example-meeting-001", "Wrong list envelope");
            });
            await CheckAsync("api_upload_file_and_title_multipart", async delegate
            {
                Meeting meeting = await api.UploadAsync(recordingPath, "Сынақ қазақша", CancellationToken.None);
                Assert(meeting.id == "upload-001" && meeting.status == "queued" && meeting.title == "Сынақ қазақша", "Upload response mismatch");
            });
            await CheckAsync("api_get_meeting", async delegate
            {
                Meeting meeting = await api.GetAsync("example-meeting-001", CancellationToken.None);
                Assert(meeting.status == "completed" && meeting.stage == null && meeting.error == null, "Wrong meeting status");
            });
            await CheckAsync("api_result_full_contract", async delegate
            {
                MeetingResult result = await api.ResultAsync("example-meeting-001", CancellationToken.None);
                Assert(result.meeting_id == "example-meeting-001" && result.transcript[0].text == demo.transcript[0].text &&
                    result.tasks[0].assignee == "Айдос" && result.exports.Count == 2, "Result data mismatch");
            });
            await CheckAsync("api_export_docx_and_pdf_routes", async delegate
            {
                byte[] docx = await api.ExportAsync("example-meeting-001", "docx", CancellationToken.None);
                byte[] pdf = await api.ExportAsync("example-meeting-001", "pdf", CancellationToken.None);
                Assert(docx.Length == File.ReadAllBytes(Path.Combine(output, "native-demo.docx")).Length, "DOCX length mismatch");
                Assert(Encoding.ASCII.GetString(pdf).StartsWith("%PDF-"), "PDF signature mismatch");
            });
            await CheckAsync("api_501_scaffold_error", async delegate
            {
                await ExpectApi(async delegate { await api.GetAsync("scaffold", CancellationToken.None); }, 501);
            });
            await CheckAsync("api_422_validation_error_no_echoed_input", async delegate
            {
                try { await api.GetAsync("validation", CancellationToken.None); }
                catch (ApiException error)
                {
                    Assert(error.StatusCode == 422 && !error.Message.Contains("SECRET_FIXTURE_INPUT") && error.Message.Contains("Field required"), "Validation error leaked input or omitted reason");
                    return;
                }
                throw new Exception("Expected validation failure");
            });
            await CheckAsync("api_post_redirect_rejected_without_retry", async delegate
            {
                await ExpectApi(async delegate { await api.UploadAsync(recordingPath, "REDIRECT_FIXTURE", CancellationToken.None); }, 307);
            });
            await CheckAsync("api_invalid_json_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.GetAsync("invalid-json", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_mismatched_meeting_id_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.GetAsync("wrong-id", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_invalid_timestamps_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.ResultAsync("invalid-segment", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_nonlocal_result_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.ResultAsync("nonlocal", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_oversize_json_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.GetAsync("oversize", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_invalid_export_rejected", async delegate
            {
                await ExpectApi(async delegate { await api.ExportAsync("invalid-export", "pdf", CancellationToken.None); }, 0);
            });
            await CheckAsync("api_cancellation_interrupts_response_body", async delegate
            {
                using (var cancel = new CancellationTokenSource())
                {
                    var timer = Stopwatch.StartNew();
                    cancel.CancelAfter(200);
                    try { await api.GetAsync("slow", cancel.Token); }
                    catch (OperationCanceledException)
                    {
                        Assert(timer.ElapsedMilliseconds < 3000, "Cancellation did not interrupt read promptly");
                        return;
                    }
                    throw new Exception("Cancellation was not propagated");
                }
            });
        }
    }

    private static int Main(string[] args)
    {
        if (args.Length != 2) return 2;
        Console.OutputEncoding = new UTF8Encoding(false);
        output = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(output);
        try { Run(args[0]).GetAwaiter().GetResult(); }
        catch (Exception error) { Record("harness", error); }
        var report = new { passed = failures == 0, checks = Results.Count, failures = failures, results = Results };
        File.WriteAllText(Path.Combine(output, "checks.json"), new JavaScriptSerializer().Serialize(report), new UTF8Encoding(false));
        Console.WriteLine("Checks: " + Results.Count + "; failures: " + failures);
        return failures == 0 ? 0 : 1;
    }
}
