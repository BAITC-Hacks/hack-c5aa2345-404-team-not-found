# Интеграция клиентов и backend

## Текущее состояние

- Streamlit включён в main через `7f341e8`; его серверная реализация из `160d1e0`
  заменена каркасом команды при слиянии. Прежние endpoints в main отсутствуют.
- Основной Windows-клиент из `46d7f09` — C# / WinForms. Он использует целевой API v1.
- Local AI включён через `f7176a6`; адаптеры доступны в `services/*/local.py`.
- Обновление `408d349` добавляет CLI оценки и отчёт полной записи; в main оно
  учтено к `30d2de3`, но активные HTTP-маршруты не меняет.
- Backend 0.2.0 подключает все методы v1, SQLite и один worker `app/pipeline.py`, нормализацию WAV и Local AI. Экспорт — `app/services/export/local.py`.

Связка native ApiClient → настоящий FastAPI/worker/SQLite/экспорт прошла 10/10 проверок с синтетическими моделями. Реальный прогон на ПК Local AI ещё требуется; запуск — [backend-launch.md](backend-launch.md).

## Два клиентских контракта

| Операция | Сохранённый Streamlit | Основной WinForms / целевой v1 |
| --- | --- | --- |
| Загрузка | multipart `audio`, `meeting_id` | multipart `file`, Meeting с `id` |
| Статус | `/api/meetings/{id}/status` | `/api/meetings/{id}` |
| Результат | `/api/meetings/{id}` | `/api/meetings/{id}/result` |
| История | `meetings`, `next_offset` | `items` |
| Экспорт | `/download/{format}` | `/export?format=...` |
| Правки | PUT задач с revision | Не входят в контракт |
| Резюме/задачи | список summary, description/source_quote | строка summary, task/source_text |

Демо Streamlit остаётся отдельной демонстрацией. Для native EXE используйте
[его инструкцию](desktop/README.md), а не корневой Streamlit requirements.
Эксперимент `desktop/launcher.py`/PyInstaller также не входит в native-сборку.

## Реализованная интеграция и оставшаяся проверка

1. Backend реализует [API v1](api-contract.md), включая очередь/статусы/результаты.
2. Создаёт экземпляры Local AI по параметрам [handoff](local-ai/handoff.md), явно
   управляет загрузкой и освобождением моделей.
3. Совмещает интервалы STT и диаризации, передаёт LLM размеченный транскрипт.
4. Валидирует и хранит результат, создаёт экспорт и реализует его выдачу.
5. Команда выполняет сценарий EXE → запись → Result → DOCX/PDF.

Редактирование задач и их жизненный цикл потребуют отдельного расширения API;
прежний PUT из Streamlit не считается автоматически согласованным.

## Несовпадения схем, важные при реализации

`MeetingAnalysisResponse` сейчас не включает все поля HTTP Result (`meeting_id`,
`exports`), а отдельной серверной схемы Meeting нет. У `start` и `end` есть
проверка неотрицательности, но отношение `end >= start` пока не проверяется
серверной Pydantic-схемой. Контракт задаёт целевые требования, клиент проверяет
ответ независимо. HTTP-поля meeting_id/exports добавляет pipeline, Meeting формирует Store. Pipeline проверяет порядок границ и лимит длительности перед экспортом; клиент дополнительно проверяет ответ. Общие модели Local AI сохранены совместимыми.

Legacy `tests/test_backend_api.py` в корне ссылается на удалённый `backend.app.agent`.
Общий запуск всех legacy-тестов из корня не является доступной приёмкой нынешнего
сервера. Используйте разделённые команды из [verification.md](verification.md).

Новые API-тесты находятся в `backend/tests/test_backend_api.py`, алгоритмы —
`backend/tests/test_pipeline.py`; они запускаются из папки backend. Native-интеграция —
`backend/tests/run_native_api_check.py` из корня репозитория.
