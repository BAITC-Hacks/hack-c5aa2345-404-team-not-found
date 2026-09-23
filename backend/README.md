# Backend SAMRUK KAZYNA

FastAPI API, SQLite, одна последовательная очередь локальных моделей,
подготовка mono PCM16 WAV 16 kHz, Whisper → Community-1 → Ollama и DOCX/PDF.
Native EXE работает с целевым HTTP API. Связка EXE → настоящие маршруты, worker,
SQLite и экспорт прошла 10/10 проверок с синтетическими моделями. Реальный
GPU-прогон всей системы на ПК Local AI ещё требуется.

## Быстрый запуск на готовом компьютере Local AI

Полная [инструкция](../docs/backend-launch.md) сохраняет существующий venv и
модели. Ollama уже должна работать. Из корня репозитория:

```powershell
. .\scripts\local-ai\ai-env.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
& $env:HACKALEM_PYTHON -m pip install -r .\backend\requirements-runtime.txt
& $env:HACKALEM_PYTHON -m pip check
.\scripts\start-backend.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
```

Не переустанавливайте Torch, CUDA и модели. Entrypoint — `app.main:app`, один
worker, без access logs; остановка — Ctrl+C. Swagger: <http://127.0.0.1:8000/docs>.

## Запуск API на новом компьютере без моделей

Нужен Python 3.11. Из корня репозитория:

```powershell
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-runtime.txt
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

На Linux/macOS используйте `python3.11` и `backend/.venv/bin/python`.
Без ресурсов модели не скачиваются автоматически: health будет `not_ready`,
загрузка — 503. Для серверного окружения следуйте [Local AI README](../docs/local-ai/README.md).

## Реализованные методы

| Запрос | Результат |
| --- | --- |
| `GET /health` | `ok` при готовых ресурсах, иначе `not_ready`; `local_only=true`, `processing_modules` |
| `POST /api/meetings` | multipart `file`/`title`, 202 Meeting со статусом queued |
| `GET /api/meetings` | история в `items`, SQLite |
| `GET /api/meetings/{id}` | queued/processing/completed/failed, stage и безопасная ошибка |
| `GET /api/meetings/{id}/result` | результат после completed, иначе 409 |
| `GET /api/meetings/{id}/export?format=docx` или `pdf` | серверный протокол, до готовности 409 |

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 6
```

Health проверяет локальные файлы моделей, пакеты, FFmpeg, шрифт PDF и Ollama.
Он не загружает модели и не доказывает качество распознавания. При неготовности
изучите `processing_modules`; демоподмены нет. Поля и ошибки: [API-контракт](../docs/api-contract.md).

## Зависимости

| Файл | Назначение |
| --- | --- |
| `requirements-runtime.txt` | фиксированные лёгкие API/export зависимости для готового AI-окружения |
| `requirements-api.txt` | входной файл API-зависимостей текущего backend |
| `requirements-ai.txt` | фиксированные версии адаптеров; GPU/Torch/FFmpeg готовятся отдельно |
| `requirements.txt` | общий список; не использовать для массового обновления рабочего AI-окружения |
| Корневой `requirements.txt` | прежний Streamlit-стек; native EXE его не требует |

## Настройки, хранение и LAN

Конфигурация читается из переменных окружения в `app/core/config.py`;
`.env.example` показывает имена, сам `.env` автоматически не загружается.
Приватное хранилище по умолчанию — `%LOCALAPPDATA%/SAMRUK_KAZYNA/meetings`.
Статусы и история находятся в SQLite, записи/результаты — в UUID-каталогах.
Прерванные задания после перезапуска получают failed.

Обычный запуск слушает loopback. Для согласованной LAN передайте
`-BindAddress <LAN-IP-сервера>` скрипту или `--host <LAN-IP-сервера>` Uvicorn.
Укажите тот же адрес/порт в EXE. Ollama остаётся на loopback сервера.
Аутентификация, публичное размещение и роли пользователей ещё не реализованы.

## Проверки

Из каталога backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/local_ai -v
```

Из корня после сборки native EXE:

```powershell
.\backend\.venv\Scripts\python.exe backend/tests/run_native_api_check.py
```

Подтверждены **22 backend-теста**, **43 автономных AI-теста** и
**10 native→real API проверок**. В автоматических сценариях модели синтетические;
маршруты, очередь, SQLite и экспорт настоящие. Реальный GPU-прогон всей
системы выполняется отдельно по [Local AI handoff](../docs/local-ai/handoff.md).

Прежний `backend/app/agent/` доступен в истории `160d1e0` и не является активным
сервером. Legacy-тесты корневого `tests/` не использовать для подтверждения
нового backend. Навигация по проверкам — [verification.md](../docs/verification.md),
общий статус — [README](../README.md).
