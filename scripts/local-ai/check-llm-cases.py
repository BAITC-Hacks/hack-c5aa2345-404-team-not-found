"""Real local Qwen regression suite. Only synthetic text; no cloud calls.

Expected answers are assertions only and are NEVER sent to the model.
JSON/source validation in the production adapter remains enabled.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import runpy
import time
from unittest.mock import patch

helpers = runpy.run_path(str(Path(__file__).with_name("check-local-ai.py")))
helpers["local_network_only"]()

from app.services.llm import local


CASES = [
    {
        "id": "original_pdf",
        "text": """SPEAKER_00: Меня зовут Айгуль. Тимур, подготовь API для загрузки аудио к 25 сентября 2026 года.
SPEAKER_01: Я Тимур. Жақсы, API-ді дайындаймын.
SPEAKER_00: Айжанға қазақша интерфейсті тексеруді тапсырамын. Мерзімі айтылған жоқ.
SPEAKER_00: Ещё нужно проверить экспорт PDF, ответственный и срок пока не назначены.
SPEAKER_01: Мен келісемін. Бүгін тек демо деректерін қолданамыз.""",
        "expected": [("SPEAKER_00", "API", "Тимур", "25 сентября 2026 года", "Айгуль"),
                     ("SPEAKER_00", "қазақша", "Айжан", None, "Айгуль"),
                     ("SPEAKER_00", "PDF", None, None, "Айгуль")],
    },
    {
        "id": "different_name_and_artifact",
        "text": """VOICE_9: Меня зовут Раушан.
VOICE_2: Сегодня обсуждаем тестирование приложения.
VOICE_9: Нужно проверить экспорт DOCX. Исполнитель и срок пока не назначены.""",
        "expected": [("VOICE_9", "DOCX", None, None, "Раушан")],
    },
    {
        "id": "two_confirmed_authors",
        "text": """Speaker A: Меня зовут Мария.
Speaker B: Меня зовут Павел.
Speaker A: Антон, проверь загрузку завтра.
Speaker B: Елена, подготовь презентацию в пятницу.""",
        "expected": [("Speaker A", "загрузку", "Антон", "завтра", "Мария"),
                     ("Speaker B", "презентацию", "Елена", "в пятницу", "Павел")],
    },
    {
        "id": "kazakh_self_introduction",
        "text": """[K7] Менің атым Дана.
[K7] Ерланға есепті дайындауды тапсырамын. Мерзімі айтылған жоқ.
[K2] Түсінікті.""",
        "expected": [("K7", "есепті", "Ерлан", None, "Дана")],
    },
    {
        "id": "unknown_author_not_assignee",
        "text": """SPEAKER_07: Светлана, проверь таблицу завтра.
SPEAKER_08: Хорошо.""",
        "expected": [("SPEAKER_07", "таблицу", "Светлана", "завтра", None)],
    },
    {
        "id": "conflicting_speaker_identity",
        "text": """VOICE_1: Меня зовут Ольга.
VOICE_1: Меня зовут Дарья.
VOICE_1: Нужно проверить архив. Исполнитель и срок пока не назначены.""",
        "expected": [("VOICE_1", "архив", None, None, None)],
    },
    {
        "id": "reported_task_not_narrator",
        "text": """A: Меня зовут Мария.
A: Олег попросил Антона проверить резервную копию завтра.""",
        # This conservative adapter does not resolve indirect-speech authors yet.
        "expected": [("A", "копию", "Антона", "завтра", None)],
    },
]


def run(case):
    raw_authors = []
    raw_attempts = []
    original_ground = local._ground

    def observe(answer, transcript):
        raw_authors.append([item.assigned_by for item in answer.tasks])
        raw_attempts.append(answer.model_dump())
        return original_ground(answer, transcript)

    started = time.monotonic()
    try:
        with patch.object(local, "_ground", side_effect=observe):
            summary, tasks = local.LocalMeetingAnalysisService().analyze(case["text"])
        checks = {"nonempty_summary": bool(summary.strip()), "task_count": len(tasks) == len(case["expected"])}
        for index, (speaker, fragment, assignee, deadline, author) in enumerate(case["expected"]):
            matching = [task for task in tasks if task.source_speaker == speaker and fragment.casefold() in task.source_text.casefold()]
            checks[f"task_{index}_unique_source"] = len(matching) == 1
            if len(matching) == 1:
                task = matching[0]
                checks[f"task_{index}_assignee"] = task.assignee == assignee
                checks[f"task_{index}_deadline"] = task.deadline == deadline
                checks[f"task_{index}_assigned_by"] = task.assigned_by == author
        result = {"id": case["id"], "passed": all(checks.values()), "checks": checks,
                  "output": {"summary": summary, "tasks": [asdict(task) for task in tasks]},
                  "raw_model_authors_by_attempt": raw_authors}
    except Exception as exc:
        result = {"id": case["id"], "passed": False, "error_type": type(exc).__name__, "error": str(exc),
                  "validation_cause": str(exc.__cause__) if exc.__cause__ else None}
    result["raw_attempts"] = raw_attempts  # Synthetic fixtures only; never actual meeting data.
    result["seconds"] = round(time.monotonic() - started, 2)
    print(json.dumps({key: result[key] for key in ("id", "passed", "seconds")}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[case["id"] for case in CASES])
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    results = []
    for iteration in range(args.repeat):
        for case in CASES:
            if not args.case or case["id"] == args.case:
                result = run(case)
                result["iteration"] = iteration + 1
                results.append(result)
    report = {"synthetic_text_only": True, "external_python_network_blocked": True,
              "passed": all(result["passed"] for result in results), "results": results}
    helpers["save"]("adapter-llm-cases" + ("-" + args.case if args.case else ""), report)
    if not report["passed"]:
        raise SystemExit(1)
