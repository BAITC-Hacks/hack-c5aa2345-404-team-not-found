using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Xml;
using SamrukDesktop;

public static class NativeBackendIntegration
{
    private static int checks;
    private static void Require(bool condition, string name)
    {
        if (!condition) throw new Exception(name);
        checks++;
        Console.WriteLine("PASS " + name);
    }

    public static int Main(string[] args)
    {
        try { Run(args).GetAwaiter().GetResult(); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static async Task Run(string[] args)
    {
        string output = args[2];
        using (var api = new ApiClient(args[0]))
        {
            var health = await api.HealthAsync(CancellationToken.None);
            Require(health.status == "ok" && health.local_only, "real_fastapi_health");
            var created = await api.UploadAsync(args[1], "Синтетический тест Қазақша", CancellationToken.None);
            Require(created.status == "queued" && created.title == "Синтетический тест Қазақша", "real_multipart_upload_and_title");
            var timer = Stopwatch.StartNew();
            Meeting current;
            do
            {
                current = await api.GetAsync(created.id, CancellationToken.None);
                if (current.status == "completed" || current.status == "failed") break;
                await Task.Delay(100);
            } while (timer.ElapsedMilliseconds < 30000);
            Require(current.status == "completed", "real_worker_completed" +
                (current.error == null ? "" : ": " + current.error.message));
            var result = await api.ResultAsync(created.id, CancellationToken.None);
            Require(result.meeting_id == created.id && result.local_only && result.processing_state == "completed", "real_result_envelope");
            Require(result.summary.Contains("отчёт") && result.transcript.Count == 2 &&
                result.transcript[0].text.Contains("Ертең") && result.transcript[1].text.Contains("Подготовлю"), "ru_kk_transcript_and_summary");
            Require(result.transcript[0].speaker == "SPEAKER_00" && result.transcript[1].speaker == "SPEAKER_01" &&
                result.transcript[1].start == 1.0, "real_timestamp_and_speaker_merge");
            Require(result.tasks.Count == 1 && result.tasks[0].assignee == "Айдос" &&
                result.tasks[0].source_text == result.transcript[0].text, "real_task_and_evidence");
            var items = await api.ListAsync(CancellationToken.None);
            Require(items.Count == 1 && items[0].id == created.id && items[0].status == "completed", "real_sqlite_meeting_list");
            byte[] docx = await api.ExportAsync(created.id, "docx", CancellationToken.None);
            byte[] pdf = await api.ExportAsync(created.id, "pdf", CancellationToken.None);
            File.WriteAllBytes(Path.Combine(output, "protocol.docx"), docx);
            File.WriteAllBytes(Path.Combine(output, "protocol.pdf"), pdf);
            using (var memory = new MemoryStream(docx))
            using (var archive = new ZipArchive(memory, ZipArchiveMode.Read))
            using (var stream = archive.GetEntry("word/document.xml").Open())
            {
                var xml = new XmlDocument { XmlResolver = null };
                xml.Load(stream);
                Require(xml.InnerText.Contains("Ертең есеп дайындау.") && xml.InnerText.Contains("Подготовлю отчёт."), "real_docx_ru_kk_roundtrip");
            }
            string pdfBytes = Encoding.ASCII.GetString(pdf);
            Require(pdfBytes.StartsWith("%PDF-") && pdfBytes.TrimEnd().EndsWith("%%EOF") && pdfBytes.Contains("/ToUnicode"), "real_pdf_package_and_unicode_font");
            File.WriteAllText(Path.Combine(output, "native-integration.json"), new JavaScriptSerializer().Serialize(
                new { passed = true, checks = checks, meeting_id = created.id, synthetic_models = true, backend = "real FastAPI/SQLite/worker/export" }), Encoding.UTF8);
            Console.WriteLine("PASS " + checks + " native EXE -> real backend integration checks; synthetic models only.");
        }
    }
}
