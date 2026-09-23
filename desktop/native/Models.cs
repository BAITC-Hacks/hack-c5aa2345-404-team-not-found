using System.Collections.Generic;

namespace SamrukDesktop
{
    // Property names intentionally match the agreed JSON API contract.
    public sealed class ApiErrorInfo
    {
        public string code { get; set; }
        public string message { get; set; }
    }

    public sealed class Meeting
    {
        public string id { get; set; }
        public string title { get; set; }
        public string created_at { get; set; }
        public string status { get; set; }
        public string stage { get; set; }
        public ApiErrorInfo error { get; set; }
    }

    public sealed class MeetingResult
    {
        public string meeting_id { get; set; }
        public string processing_state { get; set; }
        public bool local_only { get; set; }
        public string summary { get; set; }
        public List<Segment> transcript { get; set; }
        public List<MeetingTask> tasks { get; set; }
        public List<string> exports { get; set; }
    }

    public sealed class HealthResult
    {
        public string status { get; set; }
        public bool local_only { get; set; }
    }

    public sealed class Segment
    {
        public string speaker { get; set; }
        public double start { get; set; }
        public double end { get; set; }
        public string text { get; set; }
        public List<string> detected_languages { get; set; }
    }

    public sealed class MeetingTask
    {
        public string assignee { get; set; }
        public string task { get; set; }
        public string deadline { get; set; }
        public string assigned_by { get; set; }
        public string source_speaker { get; set; }
        public string source_text { get; set; }
    }
}
