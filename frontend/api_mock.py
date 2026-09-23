"""Explicit offline backend substitute; never reads or transcribes an upload."""

from copy import deepcopy
from time import sleep
from typing import Callable

from frontend.demo_data import make_demo_result


def process_meeting(progress_callback: Callable[[int, str], None] | None = None, delay: float = 0.25) -> dict:
    """Return a synthetic protocol with deterministic simulated milestones."""
    for progress, label in [
        (10, "Демо · имитация загрузки записи…"),
        (30, "Демо · транскрибация…"),
        (55, "Демо · диаризация спикеров…"),
        (80, "Демо · извлечение поручений…"),
        (100, "Демонстрационный протокол готов"),
    ]:
        if progress_callback:
            progress_callback(progress, label)
        if delay:
            sleep(delay)
    result = make_demo_result()
    result["revision"] = 1
    return result


def update_tasks(result: dict, tasks: list[dict]) -> dict:
    updated = deepcopy(result)
    updated["tasks"] = deepcopy(tasks)
    updated["revision"] = result.get("revision", 0) + 1
    return updated
