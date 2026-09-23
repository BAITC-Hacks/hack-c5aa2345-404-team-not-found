"""Regression checks for editor drafts, saves, and protocol identity.

Run from the repository root: python -m unittest discover -s tests -v
Only in-memory synthetic meetings are used; no backend/models are required.
"""

from copy import deepcopy
from datetime import date, timedelta
import json
import unittest
from unittest.mock import patch

from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.testing.v1 import AppTest

from frontend import api_client


DEMO_APP = """
import streamlit as st
from frontend.components.dashboard import render_dashboard
render_dashboard(st.session_state['demo_meetings'])
"""
BACKEND_APP = """
from frontend import api_client
from frontend.components.dashboard import render_dashboard
render_dashboard(api_client.list_meetings())
"""
HISTORY_APP = """
import streamlit as st
from frontend.components.history import render_history
render_history(st.session_state['test_meetings'])
"""


def meeting(meeting_id: str, *, demo: bool = False) -> dict:
    today = date.today()
    return {
        "meeting_id": meeting_id, "title": "Одинаковое название",
        "created_at": "2026-09-23T08:00:00+00:00", "revision": 5,
        "is_demo": demo, "summary": ["Синтетический пример."], "transcript": [],
        "tasks": [
            {"description": "Первое поручение", "assignee": "Алия", "deadline": (today - timedelta(days=1)).isoformat(), "status": "В работе", "source_quote": "Первая исходная цитата"},
            {"description": "Второе поручение", "assignee": "Марат", "deadline": (today + timedelta(days=7)).isoformat(), "status": "В работе", "source_quote": "Вторая исходная цитата"},
        ],
    }


def submit_editor(app: AppTest, changes: dict[int, dict]) -> None:
    """Submit the real data-editor wire state with its form button.

    Streamlit 1.41.1 AppTest has no public data_editor.set_value method. This
    pinned-version helper sends the same JSON widget delta as the browser.
    """
    app.button[-1].click()
    states = app._tree.get_widget_states()
    states.widgets.append(WidgetState(
        id=app.dataframe[0].proto.id,
        string_value=json.dumps({"edited_rows": changes, "added_rows": [], "deleted_rows": []}),
    ))
    app._run(states)


class FrontendStateTests(unittest.TestCase):
    def assert_app_ok(self, app: AppTest) -> None:
        self.assertEqual([], [item.message for item in app.exception])

    def test_history_keeps_duplicate_labels_and_opens_correct_id(self) -> None:
        records = [meeting("a" * 32), meeting("b" * 32)]
        app = AppTest.from_string(HISTORY_APP, default_timeout=25)
        app.session_state["test_meetings"] = records
        app.run()
        self.assert_app_ok(app)
        self.assertEqual(2, len(app.selectbox[0].options))
        app.selectbox[0].set_value(records[1]["meeting_id"]).run()
        app.button[0].click().run()
        self.assert_app_ok(app)
        self.assertEqual(records[1]["meeting_id"], app.session_state["active_result"]["meeting_id"])
        self.assertEqual("Новое совещание", app.session_state["navigate_to"])

    def test_demo_save_refreshes_metrics_and_filtered_task_identity(self) -> None:
        record = meeting("demo-one", demo=True)
        original = deepcopy(record)
        app = AppTest.from_string(DEMO_APP, default_timeout=25)
        app.session_state["demo_meetings"] = [record]
        app.session_state["active_result"] = deepcopy(record)
        app.run()
        self.assert_app_ok(app)
        submit_editor(app, {0: {"Статус": "Выполнено"}})
        self.assert_app_ok(app)
        self.assertEqual(["1", "0", "1", "2"], [item.value for item in app.metric])
        self.assertEqual("Выполнено", app.session_state["active_result"]["tasks"][0]["status"])
        app.selectbox[0].set_value("В работе").run()
        self.assertEqual(1, len(app.dataframe[0].value))
        submit_editor(app, {0: {"Поручение": "Уточнённое второе поручение"}})
        self.assert_app_ok(app)
        tasks = app.session_state["demo_meetings"][0]["tasks"]
        self.assertEqual(original["tasks"][0]["description"], tasks[0]["description"])
        self.assertEqual("Уточнённое второе поручение", tasks[1]["description"])
        self.assertEqual(original["tasks"][1]["source_quote"], tasks[1]["source_quote"])
        self.assertEqual(original, record)

    def test_partial_timeout_retains_draft_and_retries_only_failed_meeting(self) -> None:
        original = [meeting("a" * 32), meeting("b" * 32)]
        stored = deepcopy(original)
        calls = []

        def save(meeting_id: str, tasks: list[dict], revision: int | None = None) -> dict:
            calls.append((meeting_id, revision))
            if len(calls) == 2:
                raise api_client.ApiTimeout("Synthetic read timeout")
            position = next(index for index, item in enumerate(stored) if item["meeting_id"] == meeting_id)
            self.assertEqual(stored[position]["revision"], revision)
            stored[position] = {**stored[position], "tasks": deepcopy(tasks), "revision": revision + 1}
            return deepcopy(stored[position])

        with patch.object(api_client, "list_meetings", side_effect=lambda: deepcopy(stored)), patch.object(api_client, "update_tasks", side_effect=save):
            app = AppTest.from_string(BACKEND_APP, default_timeout=25)
            app.session_state["active_result"] = deepcopy(original[0])
            app.run()
            submit_editor(app, {0: {"Поручение": "Правка A"}, 2: {"Поручение": "Правка B"}})
            self.assert_app_ok(app)
            self.assertEqual(1, len(app.error))
            self.assertEqual("Правка A", stored[0]["tasks"][0]["description"])
            self.assertEqual(original[1]["tasks"], stored[1]["tasks"])
            draft = app.session_state["dashboard_drafts"]["Все поручения"]
            self.assertEqual("Правка B", draft["rows"][2]["Поручение"])
            self.assertEqual("Правка B", app.dataframe[0].value.iloc[2]["Поручение"])
            self.assertEqual(6, app.session_state["active_result"]["revision"])
            submit_editor(app, {})
            self.assert_app_ok(app)
            self.assertEqual(0, len(app.error))
            self.assertEqual("Правка B", stored[1]["tasks"][0]["description"])
            self.assertEqual([(original[0]["meeting_id"], 5), (original[1]["meeting_id"], 5), (original[1]["meeting_id"], 5)], calls)
            self.assertEqual(original[1]["tasks"][0]["source_quote"], stored[1]["tasks"][0]["source_quote"])

    def test_blank_description_fails_before_any_backend_write(self) -> None:
        records = [meeting("a" * 32)]
        with patch.object(api_client, "list_meetings", side_effect=lambda: deepcopy(records)), patch.object(api_client, "update_tasks") as save:
            app = AppTest.from_string(BACKEND_APP, default_timeout=25).run()
            submit_editor(app, {0: {"Поручение": "  "}})
            self.assert_app_ok(app)
            self.assertEqual(1, len(app.error))
            save.assert_not_called()
            self.assertEqual("  ", app.session_state["dashboard_drafts"]["Все поручения"]["rows"][0]["Поручение"])


if __name__ == "__main__":
    unittest.main()
