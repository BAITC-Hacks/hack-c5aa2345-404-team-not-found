# SAMRUK KAZYNA — backend

FastAPI API, SQLite, одна последовательная очередь локальных моделей, подготовка WAV,
Whisper → Community-1 → Ollama и экспорт DOCX/PDF. Клиент — отдельный native Windows EXE.

Запуск на готовом компьютере Local AI: [инструкция](../docs/backend-launch.md).
Установить только `requirements-runtime.txt` в существующее AI-окружение;
модели и CUDA повторно не устанавливать. Entrypoint: `app.main:app`, один worker.
`.env` автоматически не читается, конфигурация задаётся переменными окружения.

Приватное хранилище по умолчанию: `%LOCALAPPDATA%/SAMRUK_KAZYNA/meetings`.
Статусы и история — SQLite, запись и результаты — отдельные UUID-каталоги.
Health `ok` проверяет наличие ресурсов и локальную Ollama, но не запускает inference.
Без ресурсов health `not_ready`, загрузка возвращает 503 без демоподмены.

Проверки из папки backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/local_ai -v
```

Из корня репозитория, после сборки EXE:

```powershell
.\backend\.venv\Scripts\python.exe backend/tests/run_native_api_check.py
```

Тесты используют синтетические модели; настоящий GPU-прогон всего приложения
проводится на ПК Local AI. Контракт и ограничения: [API](../docs/api-contract.md),
[README](../README.md), [Local AI handoff](../docs/local-ai/handoff.md).
