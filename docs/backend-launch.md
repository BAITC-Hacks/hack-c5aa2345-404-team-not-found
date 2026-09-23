# Запуск backend на компьютере Local AI

Эта инструкция для компьютера Amankos, где модели и GPU-окружение уже подготовлены.
Существующий venv: `C:\Users\Amankos\Downloads\Hakaton\.venv`.
Ollama уже должна быть запущена. Не пересоздавайте окружение и не скачивайте
модели повторно. Реальный сквозной сценарий **ещё ожидает запуска на этом ПК**.

## 1. Получить код команды без потери работы

В существующем клоне проверьте рабочее дерево и URL remote:

```powershell
git status --short
git remote -v
```

Используйте remote с URL
`https://github.com/BAITC-Hacks/hack-c5aa2345-404-team-not-found`.
В командах ниже замените `<team-remote>` его настоящим именем; не предполагайте,
что оно обязательно `origin`.

```powershell
git fetch <team-remote>
```

Если рабочее дерево чистое и main не используется другим worktree:

```powershell
git switch main
git merge --ff-only <team-remote>/main
git log -1 --oneline
```

Если есть незавершённые изменения, main расходится с сервером или уже открыт в
другом worktree, сохраняйте текущую работу и запускайте свежий main в отдельном
свободном каталоге:

```powershell
git worktree add --detach ..\Hakaton-backend-run <team-remote>/main
Set-Location ..\Hakaton-backend-run
git log -1 --oneline
```

Если такой каталог уже существует, выберите другое свободное имя. Не выполняйте
`reset --hard`, `clean`, force push или принудительное переключение. Отдельный
worktree использует тот же уже готовый venv по абсолютному пути; модели не теряются.
Перед установкой проверьте, что получили переданный координатором SHA с
`backend/requirements-runtime.txt` и `scripts/start-backend.ps1`.

## 2. Подключить существующее окружение и установить только runtime API

Из корня актуального checkout:

```powershell
. .\scripts\local-ai\ai-env.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
& $env:HACKALEM_PYTHON -m pip freeze | Set-Content -Encoding utf8 "$env:TEMP\samruk-before-runtime.txt"
& $env:HACKALEM_PYTHON -m pip install -r .\backend\requirements-runtime.txt
& $env:HACKALEM_PYTHON -m pip check
```

Runtime-файл закрепляет только FastAPI, Starlette, Uvicorn, multipart, Pydantic,
HTTPX, python-docx и ReportLab. Pydantic 2.10.5 и HTTPX 0.28.1 совпадают с
наблюдённым AI-окружением. Команда не использует `--upgrade`; Torch, pyannote,
faster-whisper, CUDA и модели устанавливать или обновлять здесь не нужно.
Не заменяйте runtime-файл полным `requirements.txt` или `requirements-ai.txt`.

Если `pip check` сообщает конфликт, сохраните текст ошибки и сообщите
координатору. Не лечите его массовым обновлением AI-пакетов. Снимок прежних
версий находится вне Git, во временном файле Windows.

## 3. Запустить backend

Для EXE и backend на одном ПК:

```powershell
.\scripts\start-backend.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
```

Скрипт сам dot-source'ит `ai-env.ps1`, подключает локальные пути моделей и DLL,
включает offline-режим Hugging Face и запускает **один worker Uvicorn** на
`127.0.0.1:8000`, без access logs и без hot reload. Не запускает новую Ollama,
не устанавливает пакеты и не скачивает модели. Окно оставьте открытым;
остановка — Ctrl+C.

Если EXE работает на другом компьютере в той же согласованной локальной сети:

```powershell
.\scripts\start-backend.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv' -BindAddress 0.0.0.0
```

Можно вместо `0.0.0.0` передать конкретный IP LAN-интерфейса. Клиенту нужен
настоящий LAN-IP сервера, например `http://192.168.1.20:8000`, а не `0.0.0.0`.
Для другого порта доступен параметр `-Port`. Доступ к серверному порту должен
быть разрешён для согласованной локальной сети; Ollama оставляйте на loopback.

## 4. Проверить готовность перед записью

Во втором PowerShell-окне:

```powershell
$backendHealth = Invoke-RestMethod 'http://127.0.0.1:8000/health'
$backendHealth | ConvertTo-Json -Depth 6
if ($backendHealth.status -ne 'ok') {
    $backendHealth.processing_modules | ConvertTo-Json -Depth 6
}
```

Ожидается **`status: "ok"`** и `local_only: true`. Если status отличается,
прочитайте `processing_modules` и окно сервера. `scaffold`, 501 или статус
неготовности не означают работающие модели. Передайте координатору status,
модули и безопасный текст ошибки без токенов и содержимого записи.

Успешный health — предварительная проверка, а не доказательство качества
распознавания. Реальный результат подтверждается обработкой согласованной записи.

## 5. Запустить native EXE и проверить весь сценарий

Из корня актуального checkout:

```powershell
.\desktop\build-native.ps1
.\desktop\release\SAMRUK-KAZYNA.exe
```

Сборка использует системный C# `csc` и .NET Framework. Если компилятора на этом ПК
нет, возьмите готовый EXE у координатора. Python/Node/WebView2 клиенту не нужны.
Backend в своём окне продолжает работать.

1. Откройте «Подключение», задайте `http://127.0.0.1:8000` на этом же ПК либо LAN-IP.
2. Проверьте подключение; при неготовности сервера изучите health.
3. Выберите согласованную запись WAV/MP3/M4A/MP4 с двумя говорящими и RU/KK-речью.
4. Запустите настоящую обработку. Кнопка демо показывает отдельный синтетический
   пример и не проверяет модели.
5. Дождитесь completed или зафиксируйте сообщение failed. Сверьте summary,
   текст, timestamps, говорящих, ответственных, сроки и источники поручений.
6. Сохраните DOCX/PDF через backend, откройте файлы и проверьте кириллицу/казахские
   буквы и содержимое. Таблица поручений в EXE пока только для просмотра.

В передачу координатору включите SHA, версию EXE, health, длительность записи,
время обработки, фактический результат и ошибки. Не публикуйте сами записи,
транскрипты, модели, токены, окружение и файлы встреч в Git. До этого запуска
**AI E2E остаётся неподтверждённым**, даже если native-проверки и тесты адаптеров прошли.
