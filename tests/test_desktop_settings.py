"""Settings and optional Streamlit UI checks; no backend, models or network."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from frontend.desktop_settings import (
    DEFAULT_BACKEND_URL, load_backend_url, save_backend_url, settings_path, validate_backend_url,
)


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": self.temporary.name, "MEETING_API_URL": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_default_and_environment_before_user_choice(self):
        self.assertEqual(DEFAULT_BACKEND_URL, load_backend_url())
        os.environ["MEETING_API_URL"] = "http://192.168.1.20:8000/"
        self.assertEqual("http://192.168.1.20:8000", load_backend_url())

    def test_saved_user_choice_survives_restart_and_overrides_initial_environment(self):
        os.environ["MEETING_API_URL"] = "http://localhost:8000"
        self.assertEqual("https://meeting-server:8443", save_backend_url(" https://meeting-server:8443/ "))
        self.assertEqual("https://meeting-server:8443", load_backend_url())
        expected = Path(self.temporary.name) / "SAMRUK_KAZYNA" / "desktop-settings.json"
        self.assertEqual(expected, settings_path())
        self.assertEqual({"backend_url": "https://meeting-server:8443"}, json.loads(expected.read_text()))
        self.assertEqual([expected], list(expected.parent.iterdir()))

    def test_malformed_or_invalid_settings_fall_back_to_environment(self):
        os.environ["MEETING_API_URL"] = "http://192.168.1.20:8000"
        target = settings_path()
        target.parent.mkdir(parents=True)
        for content in ("{bad json", "[]", '{"backend_url": null}', '{"backend_url":"file:///secret"}', "\ufeffbroken"):
            with self.subTest(content=content):
                target.write_text(content, encoding="utf-8")
                self.assertEqual("http://192.168.1.20:8000", load_backend_url())

    def test_credentials_and_non_base_urls_are_rejected_before_writing(self):
        for address in ("", "ftp://localhost", "http://", "localhost:8000", "http://user:secret@localhost",
                        "http://localhost?token=secret", "http://localhost#fragment", "http://localhost?",
                        "http://local host", "http://localhost:abc", "http://localhost:65536", "http://localhost:0",
                        "http://localhost:", "http://localhost\\evil", "http://localhost\n/health"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    save_backend_url(address)
        self.assertFalse(settings_path().exists())

    def test_ipv6_and_base_path_are_supported(self):
        self.assertEqual("http://[::1]:8000", validate_backend_url("http://[::1]:8000/"))
        self.assertEqual("https://meeting.local/service", validate_backend_url("https://meeting.local/service/"))


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit is not installed")
class DesktopSettingsUITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        environment = patch.dict(os.environ, {"LOCALAPPDATA": self.temporary.name,
                                              "MEETING_API_URL": DEFAULT_BACKEND_URL})
        environment.start()
        self.addCleanup(environment.stop)

    def test_two_sessions_keep_their_own_server_after_one_saves(self):
        from streamlit.testing.v1 import AppTest

        script = "from frontend.components.sidebar import render_sidebar\nrender_sidebar(False)"
        first = AppTest.from_string(script).run()
        second = AppTest.from_string(script).run()
        first.session_state["active_result"] = {"meeting_id": "old", "is_demo": False}
        first.session_state["dashboard_drafts"] = {"old": "draft"}
        first.text_input[0].set_value("http://192.168.1.20:8000")
        next(button for button in first.button if button.label == "Сохранить адрес").click().run()
        self.assertEqual([], [item.message for item in first.exception])
        self.assertEqual("http://192.168.1.20:8000", first.session_state["backend_url"])
        self.assertNotIn("active_result", first.session_state.filtered_state)
        self.assertNotIn("dashboard_drafts", first.session_state.filtered_state)
        second.run()
        self.assertEqual(DEFAULT_BACKEND_URL, second.session_state["backend_url"])
        new_session = AppTest.from_string(script).run()
        self.assertEqual("http://192.168.1.20:8000", new_session.session_state["backend_url"])

    def test_scaffold_backend_is_visible_and_settings_rerun_refreshes_health(self):
        from streamlit.testing.v1 import AppTest
        from frontend import api_client

        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        with patch.object(api_client, "health", return_value={"status": "scaffold"}) as health, \
             patch.object(api_client, "list_meetings") as meetings:
            app = AppTest.from_file(str(app_path)).run()
            self.assertEqual([], [item.message for item in app.exception])
            self.assertFalse(app.session_state["backend_online"])
            self.assertIn("scaffold", app.session_state["backend_error"])
            self.assertTrue(any("каркас" in item.value for item in app.markdown))
            next(item for item in app.text_input if item.key == "backend_url_input").set_value("http://192.168.1.22:8000")
            next(button for button in app.button if button.label == "Сохранить адрес").click().run()
            self.assertEqual([], [item.message for item in app.exception])
            self.assertEqual("http://192.168.1.22:8000", app.session_state["backend_url"])
            self.assertGreaterEqual(health.call_count, 2)
            meetings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
