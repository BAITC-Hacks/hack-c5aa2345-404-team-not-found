# Работа команды SAMRUK KAZYNA

## Ответственность

| Участник | Ветка | Результат | Изменяемые пути |
| --- | --- | --- | --- |
| Medet: backend и интеграция | `codex/backend` | API, очередь, хранение, STT/diarization, DOCX/PDF | `backend/`, кроме файлов Local AI; общая документация и конфиги |
| Друг: Local AI | `codex/local-ai-setup` | проверенные модели и адаптеры | `scripts/local-ai/`, `docs/local-ai/`, `backend/requirements-ai.txt`, `backend/app/services/{stt,diarization,llm}/local.py`, `backend/tests/local_ai/` |
| Друг: Windows Desktop | `codex/desktop-app` | native WinForms UI, API-клиент, один EXE | `desktop/native/`, `desktop/build-native.ps1`, `docs/desktop/`, `docs/screenshots/`; сохранённый `frontend/` только при отдельной задаче |

**Последний выбор пользователя — нативный Windows EXE на C# 5 / WinForms, без
веб-фронтенда и WebView2.** Это заменяет прежние Android/APK и
pywebview/PyInstaller-варианты. Не возвращайте браузерный стек ради упаковки.

Streamlit UI из `codex/streamlit-frontend` уже включён в main через merge
`7f341e8`; его код и предыдущие эксперименты сохранены. Новая native-реализация
использует целевой [API-контракт](api-contract.md), а не legacy endpoints
Streamlit. Старые расхождения описаны в [integration-notes.md](integration-notes.md).

## Git и синхронизация

1. Проверь `git status`, ветку и URL remote. Официальный репозиторий —
   `BAITC-Hacks/hack-c5aa2345-404-team-not-found`; имя remote может отличаться.
2. Выполни `git fetch <team-remote>`. Начинай новую работу в своей ветке от
   актуального main, сохраняя незавершённые изменения.
3. При незавершённой работе читай обновлённые инструкции через
   `git show <team-remote>/main:AGENTS.md` и docs. Скачивания моделей не останавливай.
4. Сохраняй прежние Android/Streamlit/pywebview-наработки и историю. Не применяй
   reset/clean, force push или удаление чужой работы ради нового стека.
5. Коммить конкретные файлы своей роли. После проверок отправь свою ветку
   в рамках разрешения владельца сессии, передай SHA и ограничения. main
   объединяет координатор.
6. Изменения общих API, схем, зависимостей и README согласуй с Medet.

Одна репа не означает автоматически общую папку. Чужие изменения появляются
после fetch и интеграции ветки. Разделение путей уменьшает конфликты; совместимость
проверяется при объединении.

## Параллельная работа

- Local AI настраивает модели на своём ПК и пишет `local.py` по `base.py`.
  Конструкторы, версии и результаты — в `docs/local-ai/handoff.md`.
- AI-зависимости — `backend/requirements-ai.txt`. Community-1 использует
  pyannote.audio 4.x; старый constraint `<4.0` к нему не применять.
- Desktop создаёт нативный клиент по [API](api-contract.md) и
  [синтетическому примеру](../samples/api/meeting-completed.json). Деморежим
  включается явно, сетевые ошибки не подменяются демо.
- Backend интегрирует очередь, хранение, модели и экспорт. Сейчас активный API
  остаётся `scaffold`/501; документация не должна обещать завершённую обработку.

## Размещение и сборка

Backend и модели сначала работают на компьютере Local AI. EXE запускается там
же или на другом Windows-ПК в LAN. Адрес по умолчанию — `http://127.0.0.1:8000`,
для другого ПК используется согласованный LAN-адрес. Ollama остаётся на
loopback сервера; клиент обращается только к API.

Основной стек: **C# 5, Windows Forms, системный .NET Framework 4.8+**.
Команда сборки из корня: `.\desktop\build-native.ps1`.
Результат — **один** `desktop/release/SAMRUK-KAZYNA.exe`.
Python, Node.js, браузер, WebView2 и `_internal` клиенту не нужны.
.NET Framework на другом компьютере может потребовать установки; на текущей
машине он обнаружен. Backend и модели не входят в EXE.

`desktop/build.ps1` — обёртка основной native-сборки. Эксперимент PyInstaller
сохранён в `desktop/build-webview-experiment.ps1`. Не используйте эксперимент как
основную сборку и не возвращайте WebView2, Electron или Streamlit-сервер без
нового решения пользователя.

Для LAN-демо адрес и доступ согласуются при интеграции; публичные туннели не
нужны. Промышленный доступ требует отдельной проработки HTTPS и аутентификации.

## Критерии передачи

**Local AI — `docs/local-ai/handoff.md`:** железо, версии, модели/ревизии,
команды, параметры адаптеров, реальное время/память, mixed ru/kk и ограничения.
Секреты и чувствительные записи не включать.

**Desktop — `docs/desktop/handoff.md`:** стек, .NET/Windows, команда сборки,
один EXE, размер и SHA-256, подпись, настройки API, выполненные проверки и
реальные скриншоты. Проверять именно новый native EXE; прежние Streamlit-тесты
не считать его приёмкой. На ПК Medet сборка и запуск подтверждены, прошли
21/21 native-проверок; остаются другой Windows-ПК и реальный AI-backend.

**Backend:** совместимость контракта и полный сценарий:
EXE → запись → загрузка → состояния → результат → DOCX/PDF.

EXE, окружения, модели и ключи подписи не добавляются в Git. Release согласуется
отдельно. Скриншоты — `docs/screenshots/`, с явной пометкой демо при его
использовании. Координатор обновляет README по фактическим результатам.
Требования организаторов — [hackathon-checklist.md](hackathon-checklist.md).
