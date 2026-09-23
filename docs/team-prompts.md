# Промпты команды SAMRUK KAZYNA

Текущая платформа — **нативный Windows EXE на C# / WinForms**. По решению пользователя это заменяет Android/APK и упаковку веб-фронтенда через pywebview/PyInstaller. Новый клиент не использует браузер или WebView2. Отправь соответствующий промпт в существующую сессию друга; изменение GitHub само по себе не меняет задание в уже работающей сессии.

## Участник Local AI — продолжение установки

```text
Продолжай текущую установку моделей, сохрани загрузки и прогресс. Название проекта теперь SAMRUK KAZYNA; клиент будет Windows EXE. Нас трое: Medet делает backend и интеграцию; ты — Local AI; третий участник — Desktop UI и EXE.

Официальный репозиторий:
https://github.com/BAITC-Hacks/hack-c5aa2345-404-team-not-found

Получай актуальный main через fetch и прочитай AGENTS.md, README.md, docs/team-workflow.md, docs/api-contract.md и base.py в backend/app/services. При незавершённых изменениях сначала сохрани работу; инструкции можно читать через git show <team-remote>/main:<path>. Remote выбирай по URL, не по предположению об имени origin.

Работай в codex/local-ai-setup. Установка и скачивание моделей разрешены предыдущим заданием. Определи железо и настрой faster-whisper/Whisper, pyannote Community-1 и локальную Qwen3 через Ollama. Сверяй официальные требования. Community-1 требует совместимого pyannote.audio 4.x; на Windows проверь TorchCodec и FFmpeg shared DLL. Отключи облачные функции Ollama и необязательную телеметрию pyannote. Условия Hugging Face и токен оформляет владелец аккаунта; секреты не выводи.

Твои пути: scripts/local-ai/, docs/local-ai/, backend/requirements-ai.txt, backend/tests/local_ai/, backend/app/services/{stt,diarization,llm}/local.py. Реализуй адаптеры существующих base.py. Загрузка моделей должна быть явной, а не побочным эффектом импорта. Общие схемы, API, __init__.py, README и desktop-код не переписывай; необходимые изменения предложи Medet.

Backend и модели будут работать на твоём ПК; EXE-клиент может работать там же либо на другом ПК в LAN. Новый отдельный сервер для моделей не создавай. Ollama оставь на loopback; очередь, объединение timestamps и экспорт делает Medet.

Проверь модели на согласованной русско-казахской записи без чувствительных данных. Если записи нет, попроси её и продолжай независимые проверки. Ограниченную видеопамять учитывай последовательным запуском и освобождением моделей. Подтверди локальную обработку после скачивания, не отправляй аудио и текст во внешние сервисы.

В docs/local-ai/handoff.md запиши железо, версии, модели/ревизии, команды установки и запуска, параметры адаптеров, реальные результаты и ограничения. Жюри должны воспроизвести запуск по этим сведениям. Токены, .env, модели, записи и окружения в Git не добавляй.

Разрешаю коммит и push файлов своей роли в codex/local-ai-setup после проверок. Это сохраняет ранее выданное разрешение на отправку своей ветки. В main не сливай, force push не используй. Передай SHA, проверки и блокеры.
```

## Участник Windows Desktop EXE — актуальный native-план

```text
Последнее решение пользователя: нужен нативный SAMRUK KAZYNA для Windows — один EXE без подключения веб-фронтенда, WebView2, браузера, Python и Node.js на компьютере клиента. Стек: C# 5, Windows Forms, системный .NET Framework 4.8+. Не возвращай pywebview/PyInstaller, Electron или Streamlit как основной клиент.

Репозиторий:
https://github.com/BAITC-Hacks/hack-c5aa2345-404-team-not-found

Medet отвечает за backend/API и интеграцию, другой участник — за локальные модели, ты — за Windows-приложение. Получи свежий main, сохрани незавершённую работу. Прочитай AGENTS.md, README.md, docs/team-workflow.md, docs/api-contract.md, docs/desktop/README.md, docs/desktop/handoff.md, docs/hackathon-checklist.md и samples/api/meeting-completed.json. Проверяй remote по URL.

Основная работа уже начата в desktop/native/. Сначала изучи текущую реализацию и её handoff; не создавай параллельно второй клиент. Работай в codex/desktop-app. Твои пути — desktop/native/, desktop/build-native.ps1, docs/desktop/, docs/screenshots/. Общие backend-схемы, маршруты, корневой README и конфиги не переписывай; изменения предложи Medet.

Сохрани прежний Streamlit UI в frontend/ и эксперимент pywebview/PyInstaller вместе с историей. Streamlit уже включён в main через merge 7f341e8. Он не входит в новый EXE и использует прежний API; не копируй эти endpoints. desktop/build.ps1 теперь вызывает native-сборку; эксперимент сохранён как desktop/build-webview-experiment.ps1. Текущая команда — .\desktop\build-native.ps1, итог — desktop/release/SAMRUK-KAZYNA.exe.

Используй стандартные WinForms-контролы и системный C# csc/.NET Framework. Нужен один рабочий EXE, без _internal, UI-сервера и скрытого браузера. На текущем ПК .NET Framework4.8+ обнаружен; на другой машине он является системным требованием. Не выдавай наличие .NET на машине сборки за проверку всех пользовательских компьютеров. Название окна и интерфейса — SAMRUK KAZYNA. Если сертификата нет, явно укажи, что EXE не подписан.

Доведи desktop-интерфейс: список встреч, выбор аудио/видео, загрузка, состояние обработки, резюме, транскрипт с говорящими/временными метками, поручения с источниками, сохранение DOCX/PDF и настройки backend URL. Учитывай изменение размера окна, клавиатуру, русский/казахский текст, длинные реплики, пустые состояния и ошибки. Новые серверные функции вроде правок задач сначала согласуй, не изобретай отсутствующий API.

Строго следуй docs/api-contract.md: multipart file, необязательный title, Meeting с id, список items, состояние GET /api/meetings/{id}, результат /result, экспорт /export?format=docx или pdf. Не используй прежние /status, /download/{format} или multipart audio из Streamlit.

В backend 0.2.0 маршруты и очередь реализованы: health ok либо not_ready, при неготовности загрузка 503. Покажи неготовность явно. Пока моделей нет, отдельная кнопка может открывать синтетический пример с видимой пометкой деморежима. Ошибки сервера не маскируй демоданными. Процент прогресса не придумывай, показывай stage/status.

Адрес по умолчанию для того же ПК — http://127.0.0.1:8000; для другого — пользовательский LAN-адрес. Backend и AI-модели запускаются отдельно на ПК Local AI. Клиент обращается к backend, а не к Ollama напрямую. Валидируй URL и запрещай автоматическое перенаправление загрузок на другой адрес. Не открывай ссылки из транскриптов автоматически. Аудио и производные данные во внешние API не отправляй.

Проверь компиляцию и реальный запуск итогового native EXE. Проверь настройки и перезапуск, отключённый сервер/scaffold, явное демо, выбор файла, состояния, результат и экспорт. Различай тесты с заглушками и живой backend. Старые 14 Streamlit-тестов не являются проверкой нового WinForms-клиента. Реальный запуск на ПК Local AI выполняется по docs/backend-launch.md; не считай синтетические тесты проверкой качества моделей.

В docs/desktop/handoff.md укажи Windows/.NET, команду сборки, путь/размер/SHA-256 EXE, наличие подписи, настройки, выполненные проверки и ограничения. Сделай реальные скриншоты собственного Windows-окна в docs/screenshots/, без персональных данных, с пометкой демо при его использовании.

Разрешаю коммит и push файлов своей роли в codex/desktop-app после проверок. В main не сливай, force push не используй. Модели, записи, окружения, .env, ключи и EXE в Git не добавляй. Передай бинарник как артефакт; публикацию Release согласуем отдельно. Сообщи SHA, результаты и блокеры.
```

## Официальные источники для native Desktop

- [Microsoft: Windows Forms для .NET Framework](https://learn.microsoft.com/en-us/dotnet/desktop/winforms/overview/?view=netframeworkdesktop-4.8).
- [Microsoft: требования .NET Framework](https://learn.microsoft.com/en-us/dotnet/framework/get-started/system-requirements).
- [Microsoft: параметры компилятора C#](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-options/).
