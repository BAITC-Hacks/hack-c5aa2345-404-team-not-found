# SAMRUK KAZYNA · сохранённый Streamlit-прототип

Этот каталог содержит прежний веб-интерфейс, включённый в main через merge
`7f341e8`. Он сохранён вместе с полезными наработками и тестами.
**По новому выбору пользователя основной Windows EXE разрабатывается на C# /
WinForms в `desktop/native/`. Streamlit, pywebview, PyInstaller и WebView2 в него
не входят.** Основная инструкция: [Desktop README](../docs/desktop/README.md).

## Что умеет отдельная демонстрация

Просмотр синтетического русско-казахского протокола, редактирование поручений,
история сессии, дашборд сроков и локальный экспорт DOCX/PDF. Деморежим включается
явно; загруженный файл не распознаётся, сетевые ошибки не подменяются демоданными.

## Запуск прежнего UI для разработки

Нужен Python 3.12. Из корня репозитория:

```powershell
py -3.12 -m venv frontend/.venv
.\frontend\.venv\Scripts\python.exe -m pip install -r frontend/requirements.txt
.\frontend\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Откройте `http://127.0.0.1:8501`, нажмите «Посмотреть демо-протокол». Проверьте
транскрипт, поручения и экспорт через «Подготовить файлы». Демо сохраняется только
в текущей сессии. Этот запуск не нужен пользователю native EXE.

Зависимости UI отделены от AI в `frontend/requirements.txt`. Сборочные
`desktop/build-webview-experiment.ps1` и `desktop/requirements-lock.txt` относятся
к сохранённому эксперименту PyInstaller; активный путь — `desktop/build-native.ps1`.
`desktop/build.ps1` теперь вызывает native-сборку.

## Структура и настройки прежнего UI

- `app.py`, `components/` — страницы, редактор, история, дашборд и темы.
- `api_client.py` — прежний HTTP-клиент Streamlit-ветки.
- `desktop_settings.py` — URL без секретов, валидация и сохранение вне bundle.
- `api_mock.py`, `demo_data.py` — явно обозначенные синтетические данные.
- `exporters.py` — локальные DOCX/PDF демо.

Адрес в боковой панели сохраняется в
`%LOCALAPPDATA%/SAMRUK_KAZYNA/desktop-settings.json`. До сохранения учитывается
`MEETING_API_URL`, иначе используется `http://127.0.0.1:8000`. Это настройки
прежнего UI; параметры нового native-клиента описываются отдельно.

## Ограничения HTTP-клиента

Текущий Streamlit-клиент использует legacy endpoints:

| Операция | Запрос |
| --- | --- |
| Загрузка | `POST /api/meetings`, multipart `audio`, ожидает `meeting_id` |
| Статус | `GET /api/meetings/{id}/status` |
| Результат | `GET /api/meetings/{id}` |
| История | `GET /api/meetings?limit=100&offset=0`, поля `meetings`/`next_offset` |
| Правки | `PUT /api/meetings/{id}/tasks`, поля `tasks`/`revision` |
| Экспорт | `GET /api/meetings/{id}/download/{docx,pdf}` |

Они расходятся с [целевым API](../docs/api-contract.md), по которому
разрабатывается новый native-клиент. Активный backend сейчас возвращает
`status=scaffold` и 501 на загрузку. Не выдавайте прежний UI за завершённую
интеграцию: [сопоставление API](../docs/integration-notes.md).

## Ранее зафиксированные проверки прежнего UI

```powershell
.\frontend\.venv\Scripts\python.exe -m unittest discover -s tests -p test_desktop_settings.py -v
.\frontend\.venv\Scripts\python.exe -m unittest discover -s tests -p test_frontend_state.py -v
.\frontend\.venv\Scripts\python.exe -m unittest discover -s tests -p test_meeting_editor.py -v
```

По [отчёту Desktop](../docs/desktop/handoff.md) в подготовленном `desktop/.venv`
прошли **14/14** (7 настроек + 4 состояния UI + 3 редактора): URL, persistence, повреждённый
JSON, независимость сессий, scaffold/timeout, история, черновики, правки строк,
источники поручений, PDF/DOCX демо и тема. Использованы синтетические данные и
HTTP-заглушки. Эти тесты не проверяют native EXE, настоящие модели или живой API.

При обновлении документации эти проверки не запускались. Они отличаются от
старого набора из коммита `160d1e0`, где семь проверок относились к прежнему backend.
`tests/test_backend_api.py` всё ещё импортирует удалённый `backend.app.agent`:
используйте перечисленные точные шаблоны, а не общий discovery всех legacy-тестов.
Границы результатов: [verification.md](../docs/verification.md).
