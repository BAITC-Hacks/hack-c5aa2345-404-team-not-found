using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Printing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Windows.Forms;
using System.Xml;

namespace SamrukDesktop
{
    /// <summary>Local DOCX export and printing. Does not contact any service.</summary>
    public static class LocalExport
    {
        private const string WordNamespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
        private const string PackageRelationships = "http://schemas.openxmlformats.org/package/2006/relationships";
        private const string OfficeRelationships = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/";

        private sealed class Paragraph
        {
            public string Text;
            public string Style;
            public float Size;
            public bool Bold;
            public bool KeepNext;

            public Paragraph(string text, string style, float size, bool bold, bool keepNext)
            {
                Text = CleanText(text ?? String.Empty);
                Style = style;
                Size = size;
                Bold = bold;
                KeepNext = keepNext;
            }
        }

        /// <summary>
        /// Writes a complete DOCX beside the destination before atomically replacing it.
        /// The caller must obtain overwrite confirmation before passing an existing path.
        /// </summary>
        public static void SaveDocx(MeetingResult result, string title, string path, bool isDemo)
        {
            if (result == null) throw new ArgumentNullException("result");
            if (String.IsNullOrWhiteSpace(path)) throw new ArgumentException("Укажите путь к файлу DOCX.", "path");

            List<Paragraph> paragraphs = BuildParagraphs(result, title, isDemo);
            string destination = Path.GetFullPath(path);
            string directory = Path.GetDirectoryName(destination);
            if (!Directory.Exists(directory)) throw new DirectoryNotFoundException("Папка сохранения не существует.");
            string temporary = Path.Combine(directory, ".samruk-export-" + Guid.NewGuid().ToString("N") + ".tmp");

            try
            {
                using (FileStream file = new FileStream(temporary, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None))
                {
                    using (ZipArchive archive = new ZipArchive(file, ZipArchiveMode.Create, true))
                    {
                        WriteContentTypes(archive);
                        WriteRelationships(archive);
                        WriteStyles(archive);
                        WriteDocument(archive, paragraphs);
                    }
                    file.Flush(true);
                }

                if (File.Exists(destination))
                {
                    // No delete-and-move fallback: a failed replace must preserve the existing file.
                    File.Replace(temporary, destination, null);
                }
                else
                {
                    // File.Move refuses to overwrite a destination that appeared during export.
                    File.Move(temporary, destination);
                }
            }
            finally
            {
                if (File.Exists(temporary))
                {
                    try { File.Delete(temporary); }
                    catch (IOException) { }
                    catch (UnauthorizedAccessException) { }
                }
            }
        }

        /// <summary>
        /// Opens the Windows print dialog. PDF is available only through an installed PDF printer.
        /// Canceling the dialog does not create a file or submit a print job.
        /// </summary>
        public static void Print(MeetingResult result, string title, bool isDemo, IWin32Window owner)
        {
            if (result == null) throw new ArgumentNullException("result");
            if (PrinterSettings.InstalledPrinters.Count == 0)
                throw new InvalidOperationException("В Windows не найден принтер. Для сохранения PDF нужен установленный PDF-принтер, например Microsoft Print to PDF. Доступен локальный экспорт DOCX.");

            List<Paragraph> paragraphs = BuildParagraphs(result, title, isDemo);
            using (PrintDocument document = new PrintDocument())
            using (PrintDialog dialog = new PrintDialog())
            using (PrintLayout layout = new PrintLayout(paragraphs, isDemo))
            {
                document.DocumentName = isDemo ? "SAMRUK KAZYNA — DEMO" : "SAMRUK KAZYNA — Протокол";
                document.OriginAtMargins = false;
                document.DefaultPageSettings.Margins = new Margins(65, 65, 65, 65);
                if (!document.PrinterSettings.IsValid)
                    document.PrinterSettings.PrinterName = PrinterSettings.InstalledPrinters[0];

                document.BeginPrint += delegate { layout.Reset(); };
                document.PrintPage += layout.PrintPage;
                dialog.Document = document;
                dialog.UseEXDialog = true;
                dialog.AllowSomePages = false;
                dialog.AllowSelection = false;
                dialog.AllowCurrentPage = false;
                dialog.AllowPrintToFile = false;

                DialogResult selection = owner == null ? dialog.ShowDialog() : dialog.ShowDialog(owner);
                if (selection != DialogResult.OK) return;
                if (!document.PrinterSettings.IsValid)
                    throw new InvalidOperationException("Выбранный принтер недоступен. Выберите доступный системный принтер или сохраните DOCX.");
                document.Print();
            }
        }

        private static List<Paragraph> BuildParagraphs(MeetingResult result, string title, bool isDemo)
        {
            List<Paragraph> paragraphs = new List<Paragraph>();
            paragraphs.Add(new Paragraph("SAMRUK KAZYNA · Протокол совещания", "Subtitle", 10, false, true));
            paragraphs.Add(new Paragraph(Value(title, "Совещание"), "Title", 20, true, true));
            if (isDemo)
                paragraphs.Add(new Paragraph("DEMO — синтетический пример. Этот документ не является результатом обработки записи или реального совещания.", "Demo", 11, true, false));
            paragraphs.Add(new Paragraph("Документ сформирован: " + DateTime.Now.ToString("dd.MM.yyyy HH:mm", CultureInfo.InvariantCulture), "Subtitle", 9, false, false));

            Heading(paragraphs, "Резюме");
            Body(paragraphs, Value(result.summary, "Резюме не предоставлено."));
            Heading(paragraphs, "Поручения");
            if (result.tasks == null || result.tasks.Count == 0)
            {
                Body(paragraphs, "Поручения не предоставлены.");
            }
            else
            {
                int index = 0;
                foreach (MeetingTask task in result.tasks)
                {
                    index++;
                    if (task == null)
                    {
                        Body(paragraphs, index.ToString(CultureInfo.InvariantCulture) + ". Поручение не содержит данных.");
                        continue;
                    }
                    paragraphs.Add(new Paragraph(index.ToString(CultureInfo.InvariantCulture) + ". " + Value(task.task, "Текст поручения не указан"), "Heading2", 12, true, true));
                    Body(paragraphs, "Ответственный: " + Value(task.assignee, "не указан"));
                    Body(paragraphs, "Срок: " + Value(task.deadline, "не указан"));
                    Body(paragraphs, "Поручил: " + Value(task.assigned_by, "не указан"));
                    Body(paragraphs, "Говорящий в источнике: " + Value(task.source_speaker, "не определён"));
                    Body(paragraphs, "Исходная реплика: " + Value(task.source_text, "не предоставлена"));
                }
            }

            Heading(paragraphs, "Транскрипт");
            if (result.transcript == null || result.transcript.Count == 0)
            {
                Body(paragraphs, "Реплики не предоставлены.");
            }
            else
            {
                foreach (Segment segment in result.transcript)
                {
                    if (segment == null) continue;
                    string label = FormatTime(segment.start) + " — " + FormatTime(segment.end) + "  ·  " + Value(segment.speaker, "Говорящий не определён");
                    if (segment.detected_languages != null && segment.detected_languages.Count > 0)
                        label += "  ·  Языки: " + String.Join(", ", segment.detected_languages.ToArray());
                    paragraphs.Add(new Paragraph(label, "Heading2", 10, true, true));
                    Body(paragraphs, Value(segment.text, "Реплика не содержит текста."));
                }
            }
            return paragraphs;
        }

        private static void Heading(List<Paragraph> paragraphs, string text)
        {
            paragraphs.Add(new Paragraph(text, "Heading1", 15, true, true));
        }

        private static void Body(List<Paragraph> paragraphs, string text)
        {
            paragraphs.Add(new Paragraph(text, "Normal", 11, false, false));
        }

        private static string Value(string text, string fallback)
        {
            return String.IsNullOrWhiteSpace(text) ? fallback : text;
        }

        private static string FormatTime(double seconds)
        {
            if (Double.IsNaN(seconds) || Double.IsInfinity(seconds) || seconds < 0 || seconds >= TimeSpan.MaxValue.TotalSeconds - 1)
                return "неизвестное время";
            TimeSpan time = TimeSpan.FromSeconds(seconds);
            return String.Format(CultureInfo.InvariantCulture, "{0:00}:{1:00}:{2:00}.{3:000}", (long)time.TotalHours, time.Minutes, time.Seconds, time.Milliseconds);
        }

        private static string CleanText(string text)
        {
            StringBuilder clean = new StringBuilder(text.Length);
            for (int i = 0; i < text.Length; i++)
            {
                char character = text[i];
                if (Char.IsHighSurrogate(character) && i + 1 < text.Length && Char.IsLowSurrogate(text[i + 1]))
                {
                    clean.Append(character);
                    clean.Append(text[++i]);
                }
                else if (XmlConvert.IsXmlChar(character)) clean.Append(character);
                else clean.Append('\uFFFD');
            }
            return clean.ToString().Replace("\r\n", "\n").Replace('\r', '\n');
        }

        private static XmlWriter OpenXmlEntry(ZipArchive archive, string name)
        {
            XmlWriterSettings settings = new XmlWriterSettings();
            settings.Encoding = new UTF8Encoding(false);
            settings.CloseOutput = true;
            settings.Indent = false;
            return XmlWriter.Create(archive.CreateEntry(name, CompressionLevel.Optimal).Open(), settings);
        }

        private static void WriteContentTypes(ZipArchive archive)
        {
            const string ns = "http://schemas.openxmlformats.org/package/2006/content-types";
            using (XmlWriter writer = OpenXmlEntry(archive, "[Content_Types].xml"))
            {
                writer.WriteStartDocument();
                writer.WriteStartElement("Types", ns);
                writer.WriteStartElement("Default", ns);
                writer.WriteAttributeString("Extension", "rels");
                writer.WriteAttributeString("ContentType", "application/vnd.openxmlformats-package.relationships+xml");
                writer.WriteEndElement();
                writer.WriteStartElement("Default", ns);
                writer.WriteAttributeString("Extension", "xml");
                writer.WriteAttributeString("ContentType", "application/xml");
                writer.WriteEndElement();
                WriteOverride(writer, ns, "/word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml");
                WriteOverride(writer, ns, "/word/styles.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml");
                writer.WriteEndElement();
                writer.WriteEndDocument();
            }
        }

        private static void WriteOverride(XmlWriter writer, string ns, string path, string type)
        {
            writer.WriteStartElement("Override", ns);
            writer.WriteAttributeString("PartName", path);
            writer.WriteAttributeString("ContentType", type);
            writer.WriteEndElement();
        }

        private static void WriteRelationships(ZipArchive archive)
        {
            WriteRelationshipFile(archive, "_rels/.rels", OfficeRelationships + "officeDocument", "word/document.xml");
            WriteRelationshipFile(archive, "word/_rels/document.xml.rels", OfficeRelationships + "styles", "styles.xml");
        }

        private static void WriteRelationshipFile(ZipArchive archive, string name, string type, string target)
        {
            using (XmlWriter writer = OpenXmlEntry(archive, name))
            {
                writer.WriteStartDocument();
                writer.WriteStartElement("Relationships", PackageRelationships);
                writer.WriteStartElement("Relationship", PackageRelationships);
                writer.WriteAttributeString("Id", "rId1");
                writer.WriteAttributeString("Type", type);
                writer.WriteAttributeString("Target", target);
                writer.WriteEndElement();
                writer.WriteEndElement();
                writer.WriteEndDocument();
            }
        }

        private static void WriteStyles(ZipArchive archive)
        {
            using (XmlWriter writer = OpenXmlEntry(archive, "word/styles.xml"))
            {
                writer.WriteStartDocument();
                WStart(writer, "styles");
                WriteStyle(writer, "Normal", "Normal", 22, false, false);
                WriteStyle(writer, "Title", "Title", 40, true, true);
                WriteStyle(writer, "Subtitle", "Subtitle", 20, false, false);
                WriteStyle(writer, "Heading1", "heading 1", 30, true, true);
                WriteStyle(writer, "Heading2", "heading 2", 24, true, true);
                WriteStyle(writer, "Demo", "Demo notice", 22, true, false);
                writer.WriteEndElement();
                writer.WriteEndDocument();
            }
        }

        private static void WriteStyle(XmlWriter writer, string id, string name, int halfPoints, bool bold, bool keepNext)
        {
            WStart(writer, "style");
            WAttribute(writer, "type", "paragraph");
            WAttribute(writer, "styleId", id);
            if (id == "Normal") WAttribute(writer, "default", "1");
            WValue(writer, "name", name);
            if (id != "Normal") WValue(writer, "basedOn", "Normal");
            WStart(writer, "pPr");
            if (keepNext) WEmpty(writer, "keepNext");
            WStart(writer, "spacing");
            WAttribute(writer, "after", "140");
            WAttribute(writer, "line", "276");
            WAttribute(writer, "lineRule", "auto");
            writer.WriteEndElement();
            writer.WriteEndElement();
            WStart(writer, "rPr");
            WriteFont(writer);
            if (bold) WEmpty(writer, "b");
            WValue(writer, "sz", halfPoints.ToString(CultureInfo.InvariantCulture));
            WValue(writer, "szCs", halfPoints.ToString(CultureInfo.InvariantCulture));
            writer.WriteEndElement();
            writer.WriteEndElement();
        }

        private static void WriteDocument(ZipArchive archive, List<Paragraph> paragraphs)
        {
            using (XmlWriter writer = OpenXmlEntry(archive, "word/document.xml"))
            {
                writer.WriteStartDocument();
                WStart(writer, "document");
                WStart(writer, "body");
                foreach (Paragraph paragraph in paragraphs)
                {
                    WStart(writer, "p");
                    WStart(writer, "pPr");
                    WValue(writer, "pStyle", paragraph.Style);
                    writer.WriteEndElement();
                    WStart(writer, "r");
                    WStart(writer, "rPr");
                    WValue(writer, "sz", ((int)(paragraph.Size * 2)).ToString(CultureInfo.InvariantCulture));
                    writer.WriteEndElement();
                    WriteRunText(writer, paragraph.Text);
                    writer.WriteEndElement();
                    writer.WriteEndElement();
                }
                WStart(writer, "sectPr");
                WStart(writer, "pgSz");
                WAttribute(writer, "w", "11906");
                WAttribute(writer, "h", "16838");
                writer.WriteEndElement();
                WStart(writer, "pgMar");
                WAttribute(writer, "top", "1134");
                WAttribute(writer, "right", "1134");
                WAttribute(writer, "bottom", "1134");
                WAttribute(writer, "left", "1134");
                WAttribute(writer, "header", "567");
                WAttribute(writer, "footer", "567");
                WAttribute(writer, "gutter", "0");
                writer.WriteEndElement();
                writer.WriteEndElement();
                writer.WriteEndElement();
                writer.WriteEndElement();
                writer.WriteEndDocument();
            }
        }

        private static void WriteRunText(XmlWriter writer, string text)
        {
            int start = 0;
            for (int index = 0; index <= text.Length; index++)
            {
                if (index < text.Length && text[index] != '\n' && text[index] != '\t') continue;
                if (index > start)
                {
                    WStart(writer, "t");
                    writer.WriteAttributeString("xml", "space", "http://www.w3.org/XML/1998/namespace", "preserve");
                    writer.WriteString(text.Substring(start, index - start));
                    writer.WriteEndElement();
                }
                if (index < text.Length) WEmpty(writer, text[index] == '\n' ? "br" : "tab");
                start = index + 1;
            }
        }

        private static void WriteFont(XmlWriter writer)
        {
            WStart(writer, "rFonts");
            WAttribute(writer, "ascii", "Segoe UI");
            WAttribute(writer, "hAnsi", "Segoe UI");
            WAttribute(writer, "cs", "Segoe UI");
            writer.WriteEndElement();
        }

        private static void WStart(XmlWriter writer, string name) { writer.WriteStartElement("w", name, WordNamespace); }
        private static void WAttribute(XmlWriter writer, string name, string value) { writer.WriteAttributeString("w", name, WordNamespace, value); }
        private static void WEmpty(XmlWriter writer, string name) { WStart(writer, name); writer.WriteEndElement(); }
        private static void WValue(XmlWriter writer, string name, string value) { WStart(writer, name); WAttribute(writer, "val", value); writer.WriteEndElement(); }

        private sealed class PrintLayout : IDisposable
        {
            private readonly List<Paragraph> paragraphs;
            private readonly bool isDemo;
            private readonly Dictionary<string, Font> fonts = new Dictionary<string, Font>();
            private readonly Font furnitureFont = new Font("Segoe UI", 9, FontStyle.Regular, GraphicsUnit.Point);
            private readonly StringFormat format;
            private int paragraphIndex;
            private int characterIndex;
            private int pageNumber;

            public PrintLayout(List<Paragraph> paragraphs, bool isDemo)
            {
                this.paragraphs = paragraphs;
                this.isDemo = isDemo;
                format = (StringFormat)StringFormat.GenericTypographic.Clone();
                format.Trimming = StringTrimming.None;
                format.FormatFlags = StringFormatFlags.LineLimit | StringFormatFlags.MeasureTrailingSpaces;
                format.SetTabStops(0, new float[] { 32 });
            }

            public void Reset() { paragraphIndex = 0; characterIndex = 0; pageNumber = 0; }

            private Font FontFor(Paragraph paragraph)
            {
                string key = paragraph.Size.ToString(CultureInfo.InvariantCulture) + (paragraph.Bold ? "b" : "r");
                Font font;
                if (!fonts.TryGetValue(key, out font))
                {
                    font = new Font("Segoe UI", paragraph.Size, paragraph.Bold ? FontStyle.Bold : FontStyle.Regular, GraphicsUnit.Point);
                    fonts.Add(key, font);
                }
                return font;
            }

            public void PrintPage(object sender, PrintPageEventArgs e)
            {
                pageNumber++;
                Graphics graphics = e.Graphics;
                GraphicsState saved = graphics.Save();
                try
                {
                    graphics.PageUnit = GraphicsUnit.Display;
                    graphics.TranslateTransform(-e.PageSettings.HardMarginX, -e.PageSettings.HardMarginY);
                    RectangleF margins = RectangleF.Intersect(e.MarginBounds, e.PageSettings.PrintableArea);
                    float furnitureHeight = furnitureFont.GetHeight(graphics) + 8;
                    RectangleF body = new RectangleF(margins.X, margins.Y + furnitureHeight, margins.Width, margins.Height - 2 * furnitureHeight);
                    if (body.Width < 80 || body.Height < 80)
                        throw new InvalidOperationException("Область печати слишком мала. Измените бумагу или поля принтера.");

                    string header = "SAMRUK KAZYNA · Протокол" + (isDemo ? " · DEMO" : String.Empty);
                    graphics.DrawString(header, furnitureFont, Brushes.DimGray, margins.X, margins.Y);
                    graphics.DrawString("Страница " + pageNumber.ToString(CultureInfo.InvariantCulture), furnitureFont, Brushes.DimGray, margins.X, margins.Bottom - furnitureHeight + 5);
                    float y = body.Y;
                    bool drewBody = false;

                    while (paragraphIndex < paragraphs.Count)
                    {
                        Paragraph paragraph = paragraphs[paragraphIndex];
                        Font font = FontFor(paragraph);
                        float lineHeight = font.GetHeight(graphics);
                        float availableHeight = body.Bottom - y;
                        if (availableHeight < lineHeight + 1) break;

                        string remaining = paragraph.Text.Substring(characterIndex);
                        if (remaining.Length == 0)
                        {
                            paragraphIndex++;
                            characterIndex = 0;
                            y += lineHeight + 6;
                            continue;
                        }

                        if (paragraph.KeepNext && characterIndex == 0 && drewBody && paragraphIndex + 1 < paragraphs.Count)
                        {
                            float measuredHeight = graphics.MeasureString(remaining, font, new SizeF(body.Width, 100000), format).Height;
                            float nextLineHeight = FontFor(paragraphs[paragraphIndex + 1]).GetHeight(graphics);
                            float needed = measuredHeight + nextLineHeight + 8;
                            if (needed <= body.Height && needed > availableHeight) break;
                        }

                        int charactersFitted;
                        int linesFilled;
                        SizeF measured = graphics.MeasureString(remaining, font, new SizeF(body.Width, availableHeight), format, out charactersFitted, out linesFilled);
                        if (charactersFitted <= 0)
                        {
                            if (drewBody) break;
                            throw new InvalidOperationException("Принтер не смог разместить текст на странице. Попробуйте другой размер бумаги или принтер.");
                        }
                        if (charactersFitted < remaining.Length && Char.IsHighSurrogate(remaining[charactersFitted - 1]) && Char.IsLowSurrogate(remaining[charactersFitted]))
                            charactersFitted--;
                        if (charactersFitted <= 0)
                            throw new InvalidOperationException("Принтер не смог разместить символ в доступной области страницы.");

                        string visible = remaining.Substring(0, charactersFitted);
                        graphics.DrawString(visible, font, Brushes.Black, new RectangleF(body.X, y, body.Width, availableHeight), format);
                        drewBody = true;
                        characterIndex += charactersFitted;
                        if (characterIndex < paragraph.Text.Length) break;

                        y += Math.Max(lineHeight, measured.Height) + 7;
                        paragraphIndex++;
                        characterIndex = 0;
                    }
                    e.HasMorePages = paragraphIndex < paragraphs.Count;
                }
                finally { graphics.Restore(saved); }
            }

            public void Dispose()
            {
                foreach (Font font in fonts.Values) font.Dispose();
                furnitureFont.Dispose();
                format.Dispose();
            }
        }
    }
}
