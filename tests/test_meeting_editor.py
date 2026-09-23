"""Regression checks for protocol row identity and the offline entry point."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.testing.v1 import AppTest

from frontend import api_client
from frontend.api_mock import process_meeting

APP = """
import streamlit as st
from frontend.components.meeting import render_result
render_result(st.session_state['active_result'])
"""


class MeetingEditorTests(unittest.TestCase):
    def app(self, result):
        app = AppTest.from_string(APP, default_timeout=30)
        app.session_state["active_result"] = deepcopy(result)
        app.session_state["demo_meetings"] = [deepcopy(result)]
        app.run()
        self.assertEqual([], [item.message for item in app.exception])
        return app

    def submit(self, app, delta):
        next(button for button in app.button if button.label == "Сохранить правки").click()
        states = app._tree.get_widget_states()
        states.widgets.append(WidgetState(id=app.dataframe[0].proto.id, string_value=json.dumps(delta)))
        app._run(states)
        self.assertEqual([], [item.message for item in app.exception])

    def test_deleting_row_preserves_quote_and_exports_saved_revision(self):
        result = process_meeting(delay=0)
        app = self.app(result)
        self.submit(app, {
            "edited_rows": {"1": {"Поручение": "Исправленная формулировка"}},
            "added_rows": [], "deleted_rows": [0],
        })
        saved = app.session_state["active_result"]
        self.assertEqual(result["tasks"][1]["source_quote"], saved["tasks"][0]["source_quote"])
        self.assertEqual("Исправленная формулировка", saved["tasks"][0]["description"])
        self.assertEqual(2, saved["revision"])
        next(button for button in app.button if button.label == "Подготовить файлы").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual(0, len(app.error))
        files = next(value for key, value in app.session_state.filtered_state.items() if key.startswith("export_"))
        self.assertTrue(files["pdf"].startswith(b"%PDF-"))
        with ZipFile(BytesIO(files["docx"])) as archive:
            xml = archive.read("word/document.xml").decode()
            self.assertIn("Исправленная формулировка", xml)

    def test_empty_tasks_allow_manual_addition_without_fabricated_quote(self):
        result = process_meeting(delay=0)
        result["tasks"] = []
        app = self.app(result)
        self.submit(app, {
            "edited_rows": {}, "deleted_rows": [],
            "added_rows": [{"Поручение": "Подготовить смету", "Ответственный": "Служба охраны труда",
                            "Срок": "Не указан", "Статус": "В работе"}],
        })
        tasks = app.session_state["active_result"]["tasks"]
        self.assertEqual(1, len(tasks))
        self.assertEqual("", tasks[0]["source_quote"])
        self.assertEqual("Подготовить смету", tasks[0]["description"])

    def test_entrypoint_survives_health_timeout_and_demo_needs_no_backend(self):
        root = Path(__file__).resolve().parents[1]
        with patch.object(api_client, "health", side_effect=api_client.ApiTimeout("Synthetic timeout")), \
             patch.object(api_client, "create_meeting") as upload:
            app = AppTest.from_file(str(root / "frontend/app.py"), default_timeout=30).run()
            self.assertEqual([], [item.message for item in app.exception])
            next(button for button in app.button if button.label == "Посмотреть демо-протокол").click().run()
            self.assertEqual([], [item.message for item in app.exception])
            self.assertTrue(app.session_state["active_result"]["is_demo"])
            upload.assert_not_called()
            app.radio[0].set_value("Дашборд поручений").run()
            self.assertEqual([], [item.message for item in app.exception])
            self.assertEqual("6", app.metric[-1].value)
            app.toggle[0].set_value(True).run()
            self.assertEqual([], [item.message for item in app.exception])
            self.assertTrue(app.session_state["dark_theme"])


if __name__ == "__main__":
    unittest.main()
