# Архитектура HackAlem

## Цель MVP

Локально обработать загруженную запись совещания и вернуть транскрипт с анонимными говорящими, summary и список поручений. В MVP нет интеграций с Teams, Zoom, Google Meet, мобильного клиента или напоминаний.

## Целевой поток данных

```text
audio/video
    -> FFmpeg preprocessing
    -> local STT (faster-whisper)
    -> local diarization (pyannote)
    -> merge by timestamps
    -> local LLM (Ollama or llama.cpp)
    -> transcript + summary + tasks
    -> DOCX/PDF protocol
```

Каждый этап работает внутри инфраструктуры заказчика. Аудио, транскрипт, промпты и результаты не отправляются в OpenAI, Google, Anthropic и другие внешние AI API.

## Смешанная речь

Ключевой критерий качества — сохранение исходных казахских, русских и английских технических слов в одной реплике. Система не должна принудительно переводить или нормализовать весь текст в один язык. Проверка на шала-қазақша входит в план оценки STT.

## Границы модулей

| Модуль | Контракт | Реализация сейчас |
| --- | --- | --- |
| STT | `STTService.transcribe(audio_path)` -> `TranscriptResult` | Placeholder |
| Diarization | `DiarizationService.diarize(audio_path)` -> turns | Placeholder |
| Analysis | `MeetingAnalysisService.analyze(transcript)` -> summary, tasks | Placeholder |
| Export | `ProtocolExportService.export(result, output_dir)` -> file | Interface only |

## Безопасность

- исходные записи и результаты хранятся локально и исключены из Git;
- чувствительные данные и токены размещаются только в локальном `.env`;
- перед загрузкой файлов будет добавлена проверка формата, размера и безопасного имени;
- до появления аутентификации доступ к API не считается production-ready;
- удаление исходной записи после обработки должно стать настройкой deployment.

## Будущая инфраструктура

MVP: Python/FastAPI + локальная файловая система + SQLite. После проверки сценария: Docker Compose, PostgreSQL и развёртывание в закрытом контуре. Точные модели, GPU-профиль и параметры inference будут выбраны после замеров на согласованных тестовых записях.
