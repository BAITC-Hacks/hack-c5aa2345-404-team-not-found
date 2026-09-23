using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace SamrukDesktop
{
    public sealed class MainForm : Form
    {
        private readonly Color navy = Color.FromArgb(20, 43, 56);
        private readonly Color teal = Color.FromArgb(14, 111, 105);
        private readonly Color muted = Color.FromArgb(95, 112, 121);
        private readonly Color canvas = Color.FromArgb(243, 246, 248);
        private readonly CancellationTokenSource lifetime = new CancellationTokenSource();
        private CancellationTokenSource operation;
        private string backendUrl = Settings.LoadUrl();
        private string audioPath;
        private MeetingResult result;
        private string resultTitle;
        private bool isDemo;
        private bool busy;
        private Panel content;
        private Label connection;
        private Label heading;
        private Label fileLabel;
        private Label progressLabel;
        private Label resultBanner;
        private TextBox titleInput;
        private TextBox urlInput;
        private Label settingsStatus;
        private Button uploadButton;
        private Button chooseButton;
        private Button demoButton;
        private Button cancelButton;
        private Button docxButton;
        private Button pdfButton;
        private Button printButton;
        private ProgressBar progress;
        private Panel meetingPage;
        private Panel historyPage;
        private Panel settingsPage;
        private RichTextBox summaryText;
        private DataGridView transcriptGrid;
        private DataGridView tasksGrid;
        private DataGridView historyGrid;
        private Label historyStatus;
        private TabControl resultTabs;

        public MainForm()
        {
            Text = "SAMRUK KAZYNA";
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(1040, 740);
            Size = new Size(1280, 880);
            Font = new Font("Segoe UI", 10F);
            BackColor = canvas;
            ForeColor = navy;
            AutoScaleMode = AutoScaleMode.Dpi;
            Icon = SystemIcons.Application;
            BuildShell();
            BuildMeetingPage();
            BuildHistoryPage();
            BuildSettingsPage();
            ShowPage(meetingPage, "Новое совещание");
            Shown += async delegate { await CheckHealthAsync(false); };
            FormClosing += delegate
            {
                lifetime.Cancel();
                if (operation != null) operation.Cancel();
            };
        }

        private void BuildShell()
        {
            var shell = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
            shell.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 235));
            shell.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            shell.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            Controls.Add(shell);
            var sidebar = new Panel { Dock = DockStyle.Fill, BackColor = navy, Padding = new Padding(20, 30, 20, 20), Margin = Padding.Empty };
            shell.Controls.Add(sidebar, 0, 0);
            var menu = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 9 };
            menu.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            foreach (float height in new float[] { 54, 36, 65, 52, 52, 52, 18 })
                menu.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
            menu.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            menu.RowStyles.Add(new RowStyle(SizeType.Absolute, 95));
            sidebar.Controls.Add(menu);
            var brand = LabelText("SAMRUK", 23, Color.White, true);
            var subBrand = LabelText("K A Z Y N A", 13, Color.FromArgb(218, 183, 100), true);
            menu.Controls.Add(brand, 0, 0);
            menu.Controls.Add(subBrand, 0, 1);
            menu.Controls.Add(LabelText("ПРОТОКОЛЫ СОВЕЩАНИЙ", 8, Color.FromArgb(160, 183, 192), false), 0, 2);
            var newButton = NavButton("＋  Новое совещание");
            newButton.Click += delegate { ShowPage(meetingPage, "Новое совещание"); };
            var historyButton = NavButton("≡  История протоколов");
            historyButton.Click += async delegate
            {
                ShowPage(historyPage, "История протоколов");
                if (!busy) await LoadHistoryAsync();
            };
            var settingsButton = NavButton("⚙  Подключение");
            settingsButton.Click += delegate { ShowPage(settingsPage, "Подключение к backend"); };
            menu.Controls.Add(newButton, 0, 3);
            menu.Controls.Add(historyButton, 0, 4);
            menu.Controls.Add(settingsButton, 0, 5);
            menu.Controls.Add(LabelText("RU / KZ\nЛокальная обработка\nWindows Desktop", 9, Color.FromArgb(160, 183, 192), false), 0, 8);
            var main = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Padding = new Padding(26, 22, 26, 12), Margin = Padding.Empty };
            main.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            main.RowStyles.Add(new RowStyle(SizeType.Absolute, 80));
            main.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            main.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
            shell.Controls.Add(main, 1, 0);
            var header = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1, Margin = Padding.Empty };
            header.RowStyles.Add(new RowStyle(SizeType.Percent, 60));
            header.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
            heading = LabelText("", 23, navy, true);
            connection = LabelText("Проверяем подключение к backend…", 9, muted, false);
            header.Controls.Add(heading, 0, 0);
            header.Controls.Add(connection, 0, 1);
            main.Controls.Add(header, 0, 0);
            content = new Panel { Dock = DockStyle.Fill, Margin = Padding.Empty };
            main.Controls.Add(content, 0, 1);
            main.Controls.Add(LabelText("Аудио обрабатывается backend вашей команды. Облачные AI API не используются.", 8, muted, false), 0, 2);
        }

        private void BuildMeetingPage()
        {
            meetingPage = NewPage();
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 186));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            meetingPage.Controls.Add(layout);
            var card = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 4,
                BackColor = Color.White, Padding = new Padding(18, 10, 18, 12), Margin = new Padding(0, 0, 0, 10) };
            card.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            card.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 170));
            card.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
            card.RowStyles.Add(new RowStyle(SizeType.Absolute, 37));
            card.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
            card.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            var caption = LabelText("Запись встречи → транскрипт → поручения", 11, navy, true);
            card.Controls.Add(caption, 0, 0); card.SetColumnSpan(caption, 2);
            titleInput = new TextBox { Dock = DockStyle.Fill, MaxLength = 160, AccessibleName = "Название совещания", Margin = new Padding(0, 2, 12, 2) };
            card.Controls.Add(titleInput, 0, 1);
            card.Controls.Add(LabelText("Название встречи", 9, muted, false), 1, 1);
            fileLabel = LabelText("Файл ещё не выбран", 9, muted, false);
            card.Controls.Add(fileLabel, 0, 2);
            chooseButton = ActionButton("Выбрать запись", false);
            chooseButton.Click += delegate { ChooseFile(); };
            card.Controls.Add(chooseButton, 1, 2);
            var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false, Margin = Padding.Empty };
            uploadButton = ActionButton("Начать обработку", true);
            uploadButton.Enabled = false;
            uploadButton.Click += async delegate { await UploadAndWaitAsync(); };
            demoButton = ActionButton("Открыть демо", false);
            demoButton.Click += delegate { OpenDemo(); };
            actions.Controls.Add(uploadButton); actions.Controls.Add(demoButton);
            card.Controls.Add(actions, 0, 3); card.SetColumnSpan(actions, 2);
            layout.Controls.Add(card, 0, 0);
            var progressBox = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2, Margin = Padding.Empty };
            progressBox.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            progressBox.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190));
            progressBox.RowStyles.Add(new RowStyle(SizeType.Percent, 65));
            progressBox.RowStyles.Add(new RowStyle(SizeType.Percent, 35));
            progressLabel = LabelText("WAV, MP3, M4A, MP4 · до 500 МБ. Для обработки нужен настроенный backend.", 9, muted, false);
            progress = new ProgressBar { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, Visible = false, Margin = new Padding(0, 4, 14, 8) };
            cancelButton = ActionButton("Остановить ожидание", false);
            cancelButton.Visible = false;
            cancelButton.Click += delegate { if (operation != null) operation.Cancel(); };
            progressBox.Controls.Add(progressLabel, 0, 0);
            progressBox.Controls.Add(cancelButton, 1, 0);
            progressBox.Controls.Add(progress, 0, 1);
            progressBox.SetColumnSpan(progress, 2);
            layout.Controls.Add(progressBox, 0, 1);
            var resultHeader = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Margin = Padding.Empty };
            resultHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            resultHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 320));
            resultHeader.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            resultBanner = LabelText("Результат появится после обработки записи.", 9, muted, false);
            var exports = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false, FlowDirection = FlowDirection.RightToLeft };
            docxButton = ActionButton("DOCX", false); docxButton.Width = 80; docxButton.Enabled = false;
            pdfButton = ActionButton("PDF", false); pdfButton.Width = 65; pdfButton.Enabled = false;
            printButton = ActionButton("Печать / PDF", false); printButton.Width = 130; printButton.Enabled = false;
            docxButton.Click += async delegate { await ExportAsync("docx"); };
            pdfButton.Click += async delegate { await ExportAsync("pdf"); };
            printButton.Click += delegate
            {
                if (result == null) return;
                try { LocalExport.Print(result, resultTitle, isDemo, this); }
                catch (Exception ex) { ShowProblem("Печать недоступна", ex); }
            };
            exports.Controls.Add(pdfButton); exports.Controls.Add(docxButton); exports.Controls.Add(printButton);
            resultHeader.Controls.Add(resultBanner, 0, 0);
            resultHeader.Controls.Add(exports, 1, 0);
            layout.Controls.Add(resultHeader, 0, 2);
            resultTabs = new TabControl { Dock = DockStyle.Fill, Padding = new Point(18, 8) };
            var summaryTab = new TabPage("Резюме") { Padding = new Padding(12), BackColor = Color.White };
            summaryText = new RichTextBox { Dock = DockStyle.Fill, ReadOnly = true, BorderStyle = BorderStyle.None,
                BackColor = Color.White, Font = new Font("Segoe UI", 12), DetectUrls = false, Text = "Выберите запись или откройте явно обозначенный демопротокол." };
            summaryTab.Controls.Add(summaryText);
            var transcriptTab = new TabPage("Транскрипт") { Padding = new Padding(8), BackColor = Color.White };
            transcriptGrid = NewGrid();
            AddColumn(transcriptGrid, "Время", 16); AddColumn(transcriptGrid, "Говорящий", 19); AddColumn(transcriptGrid, "Реплика", 65);
            transcriptTab.Controls.Add(transcriptGrid);
            var tasksTab = new TabPage("Поручения") { Padding = new Padding(8), BackColor = Color.White };
            tasksGrid = NewGrid();
            AddColumn(tasksGrid, "Поручение", 35); AddColumn(tasksGrid, "Ответственный", 18);
            AddColumn(tasksGrid, "Срок", 15); AddColumn(tasksGrid, "Кто поручил", 16); AddColumn(tasksGrid, "Источник", 35);
            tasksTab.Controls.Add(tasksGrid);
            resultTabs.TabPages.Add(summaryTab); resultTabs.TabPages.Add(transcriptTab); resultTabs.TabPages.Add(tasksTab);
            layout.Controls.Add(resultTabs, 0, 3);
        }

        private void BuildHistoryPage()
        {
            historyPage = NewPage();
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
            var refresh = ActionButton("Обновить список", true);
            var open = ActionButton("Открыть результат", false);
            refresh.Click += async delegate { if (!busy) await LoadHistoryAsync(); };
            open.Click += async delegate { if (!busy) await OpenHistoryResultAsync(); };
            actions.Controls.Add(refresh); actions.Controls.Add(open);
            historyStatus = LabelText("История хранится на выбранном backend. Демопример в неё не загружается.", 10, muted, false);
            historyGrid = NewGrid();
            AddColumn(historyGrid, "Название", 45); AddColumn(historyGrid, "Создано", 25); AddColumn(historyGrid, "Состояние", 30);
            historyGrid.CellDoubleClick += async delegate { if (!busy) await OpenHistoryResultAsync(); };
            layout.Controls.Add(actions, 0, 0); layout.Controls.Add(historyStatus, 0, 1); layout.Controls.Add(historyGrid, 0, 2);
            historyPage.Controls.Add(layout);
        }

        private void BuildSettingsPage()
        {
            settingsPage = NewPage();
            var layout = new TableLayoutPanel { Dock = DockStyle.Top, Height = 410, ColumnCount = 1, RowCount = 6,
                Padding = new Padding(22), BackColor = Color.White };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            foreach (float height in new float[] { 70, 32, 40, 52, 100, 66 })
                layout.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
            layout.Controls.Add(LabelText("Backend и модели запускаются отдельно — на этом компьютере или на компьютере команды в локальной сети.", 11, navy, false), 0, 0);
            layout.Controls.Add(LabelText("Адрес API", 10, muted, true), 0, 1);
            urlInput = new TextBox { Dock = DockStyle.Top, Text = backendUrl, AccessibleName = "Адрес backend" };
            layout.Controls.Add(urlInput, 0, 2);
            var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
            var save = ActionButton("Сохранить адрес", true);
            var check = ActionButton("Проверить связь", false);
            save.Click += async delegate
            {
                if (busy) { MessageBox.Show(this, "Сначала завершите действие или остановите ожидание обработки.", Text); return; }
                try
                {
                    backendUrl = Settings.SaveUrl(urlInput.Text);
                    urlInput.Text = backendUrl;
                    ClearResult();
                    historyGrid.Rows.Clear();
                    await CheckHealthAsync(true);
                }
                catch (Exception ex) { ShowProblem("Не удалось сохранить адрес", ex); }
            };
            check.Click += async delegate { if (!busy) await CheckHealthAsync(true); };
            actions.Controls.Add(save); actions.Controls.Add(check);
            layout.Controls.Add(actions, 0, 3);
            settingsStatus = LabelText("По умолчанию: http://127.0.0.1:8000\nДля другого ПК укажите его LAN-адрес и порт API.\nКлиент не скачивает модели и не запускает backend.", 10, muted, false);
            layout.Controls.Add(settingsStatus, 0, 4);
            layout.Controls.Add(LabelText("При смене сервера открытый результат очищается.\nСохраняется только адрес; токены моделей приложению не нужны.", 9, muted, false), 0, 5);
            settingsPage.Controls.Add(layout);
        }

        private void ShowPage(Panel page, string title)
        {
            if (busy) { System.Media.SystemSounds.Beep.Play(); return; }
            heading.Text = title;
            foreach (Control child in content.Controls) child.Visible = child == page;
            page.BringToFront();
        }

        private async Task CheckHealthAsync(bool showDetails)
        {
            string checkedUrl = backendUrl;
            try
            {
                using (var api = new ApiClient(checkedUrl))
                {
                    var health = await api.HealthAsync(lifetime.Token);
                    if (IsDisposed || checkedUrl != backendUrl) return;
                    bool ready = health.status == "ok" && health.local_only;
                    connection.Text = ready ? "●  Backend подключён · " + backendUrl : "○  Backend доступен, обработка ещё не подключена";
                    connection.ForeColor = ready ? teal : Color.FromArgb(164, 103, 22);
                    settingsStatus.Text = ready
                        ? "Backend отвечает: ok. Готовность моделей подтверждается обработкой реальной записи."
                        : "Сервер сообщает: " + health.status + ". Сейчас работает каркас API. Можно проверить интерфейс через «Открыть демо».";
                }
            }
            catch (OperationCanceledException) { }
            catch (Exception ex)
            {
                if (IsDisposed || checkedUrl != backendUrl) return;
                connection.Text = "○  Backend не подключён · интерфейс доступен";
                connection.ForeColor = muted;
                if (showDetails) settingsStatus.Text = "Связь не установлена. " + ex.Message;
            }
        }

        private void ChooseFile()
        {
            using (var picker = new OpenFileDialog { Title = "Выберите запись совещания",
                Filter = "Аудио и видео|*.wav;*.mp3;*.m4a;*.mp4", CheckFileExists = true, Multiselect = false })
            {
                if (picker.ShowDialog(this) != DialogResult.OK) return;
                var info = new FileInfo(picker.FileName);
                if (info.Length == 0 || info.Length > 500L * 1024 * 1024)
                {
                    MessageBox.Show(this, "Выберите непустую запись размером до 500 МБ.", "Файл не подходит");
                    return;
                }
                audioPath = info.FullName;
                fileLabel.Text = info.Name + " · " + (info.Length / 1048576.0).ToString("0.0") + " МБ";
                if (String.IsNullOrWhiteSpace(titleInput.Text)) titleInput.Text = Path.GetFileNameWithoutExtension(info.Name);
                uploadButton.Enabled = true;
            }
        }

        private async Task UploadAndWaitAsync()
        {
            if (busy || String.IsNullOrEmpty(audioPath)) return;
            ClearResult();
            StartOperation("Проверяем готовность backend…");
            string meetingId = null;
            try
            {
                using (var api = new ApiClient(backendUrl))
                {
                    var health = await api.HealthAsync(operation.Token);
                    if (health.status != "ok") throw new InvalidOperationException("Backend сообщает " + health.status + ". Обработка пока не подключена; запись не отправлена.");
                    if (!health.local_only) throw new InvalidOperationException("Backend не подтвердил локальную обработку. Запись не отправлена.");
                    progressLabel.Text = "Загружаем запись на выбранный backend…";
                    var meeting = await api.UploadAsync(audioPath, titleInput.Text.Trim(), operation.Token);
                    meetingId = meeting.id;
                    resultTitle = meeting.title;
                    while (meeting.status != "completed" && meeting.status != "failed")
                    {
                        progressLabel.Text = StageText(meeting);
                        await Task.Delay(2000, operation.Token);
                        meeting = await api.GetAsync(meetingId, operation.Token);
                    }
                    if (meeting.status == "failed") throw new InvalidOperationException(
                        meeting.error == null ? "Backend сообщил об ошибке обработки." : meeting.error.message);
                    var received = await api.ResultAsync(meetingId, operation.Token);
                    RenderResult(received, String.IsNullOrWhiteSpace(meeting.title) ? titleInput.Text : meeting.title, false);
                    progressLabel.Text = "Обработка завершена.";
                }
            }
            catch (OperationCanceledException)
            {
                if (!IsDisposed) progressLabel.Text = meetingId == null
                    ? "Ожидание остановлено. Если загрузка уже началась, проверьте историю перед повтором."
                    : "Ожидание остановлено. Обработка на backend может продолжаться; результат появится в истории.";
            }
            catch (Exception ex)
            {
                if (!IsDisposed)
                {
                    progressLabel.Text = "Действие не завершено. Демоданные автоматически не подставляются.";
                    ShowProblem("Не удалось обработать запись", ex);
                }
            }
            finally { FinishOperation(); }
        }

        internal static MeetingResult ReadDemo()
        {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("SamrukDesktop.Demo.json"))
            using (var reader = new StreamReader(stream))
                return new JavaScriptSerializer().Deserialize<MeetingResult>(reader.ReadToEnd());
        }

        private void OpenDemo()
        {
            if (busy) return;
            RenderResult(ReadDemo(), "Демонстрационное совещание", true);
            progressLabel.Text = "ДЕМО: синтетический пример. Выбранный файл не обрабатывается и не отправляется.";
        }

        private void RenderResult(MeetingResult received, string title, bool demo)
        {
            result = received; resultTitle = title; isDemo = demo;
            resultBanner.Text = demo ? "ДЕМО · синтетические данные" : "Готово · " + title;
            resultBanner.ForeColor = demo ? Color.FromArgb(158, 96, 18) : teal;
            summaryText.Text = (demo ? "ДЕМОНСТРАЦИОННЫЙ ПРИМЕР\n\n" : "") + (received.summary ?? "Резюме не получено.");
            transcriptGrid.Rows.Clear();
            foreach (var segment in received.transcript ?? new List<Segment>())
                transcriptGrid.Rows.Add(TimeText(segment.start) + "–" + TimeText(segment.end), segment.speaker, segment.text);
            tasksGrid.Rows.Clear();
            foreach (var task in received.tasks ?? new List<MeetingTask>())
                tasksGrid.Rows.Add(Known(task.task), Known(task.assignee), Known(task.deadline), Known(task.assigned_by), Known(task.source_text));
            var formats = received.exports ?? new List<string>();
            docxButton.Enabled = demo || formats.Contains("docx");
            pdfButton.Enabled = !demo && formats.Contains("pdf");
            printButton.Enabled = true;
            resultTabs.SelectedIndex = 0;
        }

        private void ClearResult()
        {
            result = null;
            transcriptGrid.Rows.Clear(); tasksGrid.Rows.Clear();
            summaryText.Text = "Выберите запись или откройте явно обозначенный демопротокол.";
            resultBanner.Text = "Результат появится после обработки записи.";
            docxButton.Enabled = pdfButton.Enabled = printButton.Enabled = false;
        }

        private async Task LoadHistoryAsync()
        {
            StartOperation("Загружаем историю…");
            historyStatus.Text = "Запрашиваем встречи на выбранном backend…";
            historyGrid.Rows.Clear();
            try
            {
                using (var api = new ApiClient(backendUrl))
                {
                    var meetings = await api.ListAsync(operation.Token);
                    foreach (var meeting in meetings)
                    {
                        int index = historyGrid.Rows.Add(meeting.title, meeting.created_at, StageText(meeting));
                        historyGrid.Rows[index].Tag = meeting;
                    }
                    historyStatus.Text = meetings.Count == 0 ? "Сохранённых встреч пока нет." : "Встреч: " + meetings.Count + ". Выберите завершённую встречу и откройте результат.";
                }
            }
            catch (OperationCanceledException) { }
            catch (Exception ex) { if (!IsDisposed) historyStatus.Text = "История недоступна. " + ex.Message; }
            finally { FinishOperation(); }
        }

        private async Task OpenHistoryResultAsync()
        {
            if (historyGrid.CurrentRow == null) return;
            var meeting = historyGrid.CurrentRow.Tag as Meeting;
            if (meeting == null) return;
            if (meeting.status != "completed")
            {
                historyStatus.Text = StageText(meeting) + ". Обновите список, когда обработка завершится.";
                return;
            }
            StartOperation("Получаем протокол…");
            bool loaded = false;
            try
            {
                using (var api = new ApiClient(backendUrl))
                    RenderResult(await api.ResultAsync(meeting.id, operation.Token), meeting.title, false);
                loaded = true;
            }
            catch (OperationCanceledException) { }
            catch (Exception ex) { if (!IsDisposed) ShowProblem("Результат недоступен", ex); }
            finally { FinishOperation(); }
            if (loaded && !IsDisposed) ShowPage(meetingPage, "Протокол совещания");
        }

        private async Task ExportAsync(string format)
        {
            if (result == null || busy) return;
            using (var picker = new SaveFileDialog { Title = "Сохранить протокол", Filter = format.ToUpperInvariant() + "|*." + format,
                DefaultExt = format, AddExtension = true, OverwritePrompt = true, FileName = isDemo ? "SAMRUK-DEMO." + format : "SAMRUK-Protocol." + format })
            {
                if (picker.ShowDialog(this) != DialogResult.OK) return;
                StartOperation("Сохраняем протокол…");
                try
                {
                    if (isDemo) LocalExport.SaveDocx(result, resultTitle, picker.FileName, true);
                    else
                    {
                        byte[] bytes;
                        using (var api = new ApiClient(backendUrl))
                            bytes = await api.ExportAsync(result.meeting_id, format, operation.Token);
                        string temp = picker.FileName + "." + Guid.NewGuid().ToString("N") + ".tmp";
                        try
                        {
                            File.WriteAllBytes(temp, bytes);
                            if (File.Exists(picker.FileName)) File.Replace(temp, picker.FileName, null);
                            else File.Move(temp, picker.FileName);
                        }
                        finally { if (File.Exists(temp)) File.Delete(temp); }
                    }
                    progressLabel.Text = "Протокол сохранён: " + Path.GetFileName(picker.FileName);
                }
                catch (OperationCanceledException) { }
                catch (Exception ex) { if (!IsDisposed) ShowProblem("Экспорт не выполнен", ex); }
                finally { FinishOperation(); }
            }
        }

        private void StartOperation(string message)
        {
            operation = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
            busy = true;
            uploadButton.Enabled = chooseButton.Enabled = demoButton.Enabled = false;
            progress.Visible = cancelButton.Visible = true;
            progressLabel.Text = message;
        }

        private void FinishOperation()
        {
            busy = false;
            if (operation != null) { operation.Dispose(); operation = null; }
            if (IsDisposed) return;
            progress.Visible = cancelButton.Visible = false;
            uploadButton.Enabled = !String.IsNullOrEmpty(audioPath);
            chooseButton.Enabled = demoButton.Enabled = true;
        }

        private void ShowProblem(string title, Exception error)
        {
            if (!IsDisposed) MessageBox.Show(this, error.Message, title, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private Panel NewPage()
        {
            var page = new Panel { Dock = DockStyle.Fill, Visible = false };
            content.Controls.Add(page);
            return page;
        }

        private Label LabelText(string text, float size, Color color, bool bold)
        {
            return new Label { Text = text, Dock = DockStyle.Fill, Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                ForeColor = color, TextAlign = ContentAlignment.MiddleLeft, AutoEllipsis = true, Margin = Padding.Empty };
        }

        private Button NavButton(string text)
        {
            var button = new Button { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft,
                FlatStyle = FlatStyle.Flat, BackColor = navy, ForeColor = Color.White, Cursor = Cursors.Hand, Margin = new Padding(0, 3, 0, 3) };
            button.FlatAppearance.BorderSize = 0;
            button.FlatAppearance.MouseOverBackColor = Color.FromArgb(34, 66, 80);
            return button;
        }

        private Button ActionButton(string text, bool primary)
        {
            var button = new Button { Text = text, Width = 172, Height = 34, FlatStyle = FlatStyle.Flat,
                BackColor = primary ? teal : Color.White, ForeColor = primary ? Color.White : navy,
                Cursor = Cursors.Hand, Margin = new Padding(0, 3, 10, 3), AutoEllipsis = true };
            button.FlatAppearance.BorderColor = primary ? teal : Color.FromArgb(211, 221, 226);
            return button;
        }

        private DataGridView NewGrid()
        {
            var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false,
                AllowUserToDeleteRows = false, AllowUserToResizeRows = false, RowHeadersVisible = false,
                BackgroundColor = Color.White, BorderStyle = BorderStyle.None, GridColor = Color.FromArgb(232, 237, 240),
                SelectionMode = DataGridViewSelectionMode.FullRowSelect, MultiSelect = false,
                AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                EnableHeadersVisualStyles = false, ColumnHeadersHeight = 42, CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal };
            grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(233, 239, 242);
            grid.ColumnHeadersDefaultCellStyle.ForeColor = navy;
            grid.ColumnHeadersDefaultCellStyle.Font = new Font("Segoe UI", 9, FontStyle.Bold);
            grid.DefaultCellStyle.Padding = new Padding(7, 9, 7, 9);
            grid.DefaultCellStyle.WrapMode = DataGridViewTriState.True;
            grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(217, 238, 235);
            grid.DefaultCellStyle.SelectionForeColor = navy;
            return grid;
        }

        private static void AddColumn(DataGridView grid, string title, int weight)
        {
            grid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = title, FillWeight = weight,
                MinimumWidth = 80, SortMode = DataGridViewColumnSortMode.NotSortable });
        }

        private static string Known(string value) { return String.IsNullOrWhiteSpace(value) ? "Не указано" : value; }
        private static string TimeText(double seconds)
        {
            var time = TimeSpan.FromSeconds(Math.Max(0, seconds));
            return ((int)time.TotalMinutes).ToString("00") + ":" + time.Seconds.ToString("00");
        }
        private static string StageText(Meeting meeting)
        {
            if (meeting.status == "completed") return "Завершено";
            if (meeting.status == "failed") return "Ошибка обработки";
            if (meeting.status == "queued") return "В очереди";
            switch (meeting.stage)
            {
                case "preprocessing": return "Подготовка записи…";
                case "transcribing": return "Распознавание речи…";
                case "diarizing": return "Определение говорящих…";
                case "analyzing": return "Составление протокола…";
                default: return "Обработка…";
            }
        }
    }
}
