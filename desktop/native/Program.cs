using System;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace SamrukDesktop
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.ThreadException += delegate(object sender, ThreadExceptionEventArgs e)
            {
                ReportError(e.Exception);
            };
            try { Application.Run(new MainForm()); }
            catch (Exception error) { ReportError(error); }
        }

        private static void ReportError(Exception error)
        {
            // Log only technical exception types, never audio, transcripts or URLs.
            try
            {
                Directory.CreateDirectory(Settings.DirectoryPath);
                File.AppendAllText(Path.Combine(Settings.DirectoryPath, "native.log"),
                    DateTime.UtcNow.ToString("o") + " " + error.GetType().FullName + Environment.NewLine);
            }
            catch { }
            MessageBox.Show("Не удалось выполнить действие. Проверьте подключение к backend и повторите.\n" +
                "Технический журнал: %LOCALAPPDATA%\\SAMRUK_KAZYNA\\native.log",
                "SAMRUK KAZYNA", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}
