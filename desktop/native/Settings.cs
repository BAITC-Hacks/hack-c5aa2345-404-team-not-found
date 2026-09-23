using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace SamrukDesktop
{
    public static class Settings
    {
        public const string DefaultUrl = "http://127.0.0.1:8000";

        public static string DirectoryPath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SAMRUK_KAZYNA");
            }
        }

        public static string ValidateUrl(string value)
        {
            if (String.IsNullOrWhiteSpace(value))
                throw new ArgumentException("Введите адрес backend, например http://127.0.0.1:8000.");
            value = value.Trim();
            if (value.Length > 2048)
                throw new ArgumentException("Адрес backend слишком длинный.");
            foreach (char character in value)
                if (Char.IsWhiteSpace(character) || Char.IsControl(character))
                    throw new ArgumentException("Адрес backend не должен содержать пробелы и управляющие символы.");
            Uri parsed;
            if (!Uri.TryCreate(value, UriKind.Absolute, out parsed) ||
                (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps) ||
                String.IsNullOrEmpty(parsed.Host) || parsed.Port < 1 || parsed.Port > 65535)
                throw new ArgumentException("Укажите HTTP(S)-адрес backend с корректным портом.");
            if (!String.IsNullOrEmpty(parsed.UserInfo) || value.IndexOf('?') >= 0 || value.IndexOf('#') >= 0 ||
                value.IndexOf('\\') >= 0 || parsed.Host.IndexOf('%') >= 0)
                throw new ArgumentException("Не добавляйте логин, токен, параметры или фрагмент в адрес backend.");
            // Save a server origin only: a path can hide a token, while API v1 has fixed routes.
            if (parsed.AbsolutePath != "/")
                throw new ArgumentException("Введите только адрес и порт сервера, без пути /api и секретных ссылок.");
            return parsed.GetLeftPart(UriPartial.Authority).TrimEnd('/');
        }

        public static string LoadUrl()
        {
            string path = Path.Combine(DirectoryPath, "native-settings.json");
            try
            {
                if (File.Exists(path) && new FileInfo(path).Length <= 8192)
                {
                    JavaScriptSerializer serializer = new JavaScriptSerializer { MaxJsonLength = 8192 };
                    var saved = serializer.DeserializeObject(File.ReadAllText(path, Encoding.UTF8))
                        as Dictionary<string, object>;
                    object value;
                    if (saved != null && saved.TryGetValue("backend_url", out value) && value is string)
                        return ValidateUrl((string)value);
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            catch (ArgumentException) { }
            catch (InvalidOperationException) { }
            try { return ValidateUrl(Environment.GetEnvironmentVariable("MEETING_API_URL")); }
            catch (ArgumentException) { return DefaultUrl; }
        }

        public static string SaveUrl(string value)
        {
            string normalized = ValidateUrl(value);
            Directory.CreateDirectory(DirectoryPath);
            string target = Path.Combine(DirectoryPath, "native-settings.json");
            string temporary = Path.Combine(DirectoryPath, Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                var serializer = new JavaScriptSerializer();
                var payload = new Dictionary<string, string> { { "backend_url", normalized } };
                File.WriteAllText(temporary, serializer.Serialize(payload), new UTF8Encoding(false));
                if (File.Exists(target)) File.Replace(temporary, target, null);
                else File.Move(temporary, target);
            }
            finally
            {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
            return normalized;
        }
    }
}
