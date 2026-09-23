"""Diagnostic output safety/validation without real meeting content."""
from pathlib import Path
import runpy
import unittest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "local-ai"


class DiagnosticTest(unittest.TestCase):
    def test_interval_validation(self):
        validate = runpy.run_path(str(SCRIPTS / "check-recording-results.py"))["check_intervals"]
        self.assertTrue(validate([{"start": 0, "end": 89.98}], 90))
        for bad in [{"start": -1, "end": 1}, {"start": 1, "end": 0},
                    {"start": 0, "end": 91}, {"start": 0, "end": float("nan")}]:
            self.assertFalse(validate([bad], 90))

    def test_review_escapes_untrusted_transcript(self):
        row = runpy.run_path(str(SCRIPTS / "make-audio-review.py"))["row"]
        value = row(1, 2, '<script>alert("x")</script> Қазақша')
        self.assertNotIn("<script>", value)
        self.assertIn("&lt;script&gt;", value)
        self.assertIn("Қазақша", value)

    def test_review_rejects_invalid_timestamps(self):
        row = runpy.run_path(str(SCRIPTS / "make-audio-review.py"))["row"]
        with self.assertRaises(ValueError):
            row(float("nan"), 2, "test")


if __name__ == "__main__":
    unittest.main()
