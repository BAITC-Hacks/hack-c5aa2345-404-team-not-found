# Автопротоколирование совещаний - backend

Локальный FastAPI backend для загрузки аудио, транскрибации, диаризации, извлечения поручений, саммари и экспорта протокола в DOCX/PDF. Данные не отправляются во внешние API: Ollama вызывается только через `127.0.0.1`.

## Быстрый запуск

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Для полного AI-режима установите `faster-whisper`, `pyannote.audio` и заранее разместите веса локально. `WHISPER_MODEL_PATH` задаёт каталог Whisper, `PYANNOTE_PIPELINE_PATH` — локальный YAML pyannote со всеми весами. Для анализа запустите Ollama с заранее подготовленной моделью `qwen2.5:7b-instruct`. Во время обработки загрузка весов из сети отключена. Без зависимостей API возвращает fallback с предупреждениями.

Используйте один worker Uvicorn: обработка выполняется в фоновой очереди одного процесса. Подробный запуск frontend описан в `../frontend/README.md`.

## API для frontend

- `GET /health`
- `POST /api/meetings` - multipart поле `audio`, ответ содержит `meeting_id`
- `GET /api/meetings/{id}` - JSON результата
- `GET /api/meetings/{id}/status` - статус и реальные этапы фоновой обработки
- `GET /api/meetings` - история последних протоколов
- `PUT /api/meetings/{id}/tasks` - сохранить исправленные поручения и пересобрать экспорт
- `GET /api/meetings/{id}/download/docx`
- `GET /api/meetings/{id}/download/pdf`

Backend принимает аудио/видеофайлы до 500 МБ. Список допустимых форматов проверяется при загрузке. Для on-premise режима модели Whisper и pyannote должны быть предварительно размещены в локальном кеше: автоматическая загрузка из публичного хранилища отключена.

Frontend может показывать `warnings`: это честное объяснение, какие локальные зависимости не были доступны.

