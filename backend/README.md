# Автопротоколирование совещаний - backend

Локальный FastAPI backend для загрузки аудио, транскрибации, диаризации, извлечения поручений, саммари и экспорта протокола в DOCX/PDF. Данные не отправляются во внешние API: Ollama вызывается только через `127.0.0.1`.

## Быстрый запуск

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Для полного AI-режима установите `faster-whisper`, `pyannote.audio`, задайте `HF_TOKEN`, установите Ollama и выполните `ollama pull qwen2.5:7b-instruct`. Без них API запускается в demo/fallback-режиме.

## API для frontend

- `GET /health`
- `POST /api/meetings` - multipart поле `audio`, ответ содержит `meeting_id`
- `GET /api/meetings/{id}` - JSON результата
- `GET /api/meetings/{id}/download/docx`
- `GET /api/meetings/{id}/download/pdf`

Frontend может показывать `warnings`: это честное объяснение, какие локальные зависимости не были доступны.

