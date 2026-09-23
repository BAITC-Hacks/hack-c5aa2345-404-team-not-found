import json
import os
import httpx
from .models import Task

def _ollama(prompt: str) -> str | None:
    try:
        response = httpx.post("http://127.0.0.1:11434/api/generate", json={"model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct"), "prompt": prompt, "stream": False}, timeout=180)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception:
        return None

def analyze(transcript: str) -> tuple[list[Task], list[str], list[str]]:
    prompt = f"""Ты помощник протоколиста. Верни строго JSON без markdown: {{\"summary\":[\"...\"],\"tasks\":[{{\"assignee\":\"\",\"deadline\":\"\",\"description\":\"\",\"source_quote\":\"\"}}]}}. Язык русский. Если поручений нет, tasks пустой. Транскрипт:\n{transcript}"""
    raw = _ollama(prompt)
    if raw:
        try:
            data = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
            tasks = [Task(**x) for x in data.get("tasks", [])]
            return tasks, data.get("summary", []), []
        except Exception as exc:
            return [], ["Не удалось разобрать ответ локальной LLM."], [f"Ollama вернул некорректный JSON: {exc}"]
    return [], ["Обработка завершена в demo-режиме.", "Для автоматического саммари запустите Ollama и модель qwen2.5:7b-instruct."], ["Ollama недоступен: поручения и саммари требуют локальной LLM."]

