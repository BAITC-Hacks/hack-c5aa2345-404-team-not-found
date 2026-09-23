# Согласованный целевой API v1 для Windows Desktop MVP

**Статус: маршруты реализованы в backend 0.2.0.** Проверены с настоящим native ApiClient и синтетическими адаптерами; реальный GPU-прогон выполняется на ПК Local AI. Владелец контракта — backend (Medet).

Base URL задаётся в настройках приложения: `http://127.0.0.1:8000` для backend на том же ПК или `http://<server-lan-ip>:8000` для другого ПК в LAN. Все JSON используют UTF-8, timestamps — ISO 8601 UTC, ID встречи — непрозрачная строка. Время сегментов — секунды от начала записи. EXE-клиент не вызывает модели напрямую.

## Методы

| Метод | Запрос | Успешный ответ |
| --- | --- | --- |
| `GET /health` | — | 200, `status=ok|not_ready`, `local_only`, `processing_modules`; health проверяет наличие ресурсов, но не выполняет inference |
| `POST /api/meetings` | multipart: обязательный `file`, необязательный `title` | 202, Meeting из описания ниже, `status=queued`; `Location: /api/meetings/{id}` |
| `GET /api/meetings` | — | 200, `{"items": [Meeting, ...]}`, новые первыми; в MVP без пагинации |
| `GET /api/meetings/{id}` | — | 200, Meeting; клиент опрашивает примерно каждые 2 секунды, прекращает при completed/failed или уходе с экрана |
| `GET /api/meetings/{id}/result` | — | 200, Result после completed; до готовности 409 |
| `GET /api/meetings/{id}/export?format=docx` | `format`: docx или pdf | 200, бинарный файл с корректным MIME и Content-Disposition; до готовности 409 |

Принимаемые форматы MVP: WAV, MP3, M4A, MP4. Backend проверяет содержимое и лимит размера, не доверяет имени файла. Ошибки: 413 (слишком большой файл), 415 (неподдерживаемый формат), 422 (неверные поля), 404 (неизвестный ID), 503 (сервис обработки недоступен). Повторный POST создаёт новую встречу: клиент не повторяет загрузку автоматически при неопределённом результате сетевого запроса.

## Meeting

Все поля присутствуют:

```json
{
  "id": "example-meeting-001",
  "title": "Тестовое совещание",
  "created_at": "2026-09-23T10:00:00Z",
  "status": "queued",
  "stage": null,
  "error": null
}
```

- `status`: `queued | processing | completed | failed`.
- `stage`: `preprocessing | transcribing | diarizing | analyzing` или null. Стадии могут пропускаться; при completed/failed — null.
- `error`: null или `{"code": "processing_failed", "message": "..."}` с безопасным сообщением без внутренних путей, токенов и содержимого записи.
- `title`: пользовательское значение, либо безопасное название, выбранное сервером. `created_at` — дата загрузки, не доказанная дата совещания.
- Не показывать выдуманный процент выполнения. Достаточно текущей стадии.

## Result

Пример всех полей: [samples/api/meeting-completed.json](../samples/api/meeting-completed.json).

- `meeting_id`: ID встречи.
- `processing_state`: `completed`.
- `local_only`: true.
- `summary`: string.
- `transcript`: массив `{speaker, start, end, text, detected_languages}`.
- `tasks`: массив `{assignee, task, deadline, assigned_by, source_speaker, source_text}`.
- `exports`: массив доступных форматов, подмножество `["docx", "pdf"]`. Для завершённого целевого MVP нужны оба; клиент скрывает недоступные действия во время разработки.

Схемы реплик и поручений соответствуют существующим Pydantic-моделям. `end >= start >= 0`; `detected_languages` — список кодов (например, ru/kk/en), может быть пустым. `speaker` — анонимный стабильный ID, а не установленное по голосу имя. `assignee`, `deadline`, `assigned_by` допускают null. `source_speaker` и `source_text` — строки для проверки происхождения поручения. Если источник определить невозможно, вернуть пустую строку и отметить ограничение, не выдумывать цитату или говорящего. Относительный срок вроде «завтра» сохранять как исходный текст, если дата встречи неизвестна.

## Ошибки и поведение клиента

Прикладная HTTP-ошибка: `{"detail": {"code": "not_ready", "message": "Результат ещё не готов"}}`. При failed клиент читает `Meeting.error`. При этом FastAPI может возвращать стандартный массив `detail` для 422, а старый scaffold — строковый `detail` для 501; клиент должен безопасно отображать все три формы.

Деморежим включается явно, помечается на экранах и использует те же типы. Сетевые ошибки никогда не переключают приложение в деморежим автоматически. Токены Hugging Face и настройки доступа к моделям не встраиваются в EXE и не передаются в UI. Нативный Windows-клиент использует HttpClient; автоматические перенаправления загрузки отключены.
