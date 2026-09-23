# Local AI: установка и проверка адаптеров

Этот раздел предназначен для компьютера, на котором работают модели. Для демо
Windows-клиента установка AI не нужна: начните с [корневого README](../../README.md).

Реализованы и подключены к HTTP backend три адаптера: распознавание речи,
диаризация и анализ текста. Backend реализует очередь, хранение, объединение
временных меток и экспорт DOCX/PDF. `/health` сообщает `ok` либо `not_ready`;
при неготовности зависимостей загрузка возвращает HTTP 503. Полный запуск описан
в [backend-launch.md](../backend-launch.md). Команды ниже проверяют адаптеры
напрямую; сквозной GPU-сценарий EXE → API → настоящие модели ещё не подтверждён.

Инструкция составлена по исходникам и [отчёту участника от 23.09.2026](handoff.md).
В рамках обновления документации установка и проверки повторно не выполнялись.
Пути `C:\Users\Amankos\...` из отчёта относятся только к компьютеру участника;
для нового компьютера используйте команды ниже из корня репозитория.

## 1. Окружение и версии

Проверенная конфигурация: Windows 11 x64, Python 3.11.9 x64, Ryzen 7 7745HX,
31.3 GiB RAM, RTX 4060 Laptop с 8188 MiB VRAM. Это описание запуска, а не
измеренные минимальные требования. Модели запускались последовательно.
Для CUDA нужен совместимый установленный NVIDIA-драйвер; скрипты его не устанавливают.
CUDA/cuDNN DLL предоставлены PyTorch wheel, полный Toolkit не использовался.
CPU доступен через `--device cpu`, но его скорость в отчёте не измерялась.

Основные пакеты закреплены в [requirements-ai.txt](../../backend/requirements-ai.txt).
[requirements-observed.txt](../../scripts/local-ai/requirements-observed.txt) — снимок
окружения участника, включая прежние backend-пакеты. Он используется как constraints
для воспроизведения; это не аудит зависимостей и не рекомендация для production.
Повторная установка на чистом втором ПК пока не подтверждена.

Если `backend/.venv` уже содержит рабочее AI-окружение, не пересоздавайте его.
Для новой установки выполните по очереди:

```powershell
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install torch==2.9.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu126
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-ai.txt -r backend/requirements-api.txt -c scripts/local-ai/requirements-observed.txt
.\backend\.venv\Scripts\python.exe -m pip check
. .\scripts\local-ai\ai-env.ps1
```

После каждой Python/CLI-команды проверяйте `$LASTEXITCODE`: продолжайте установку
только при `0`. PowerShell сам по себе не останавливает последовательность при
ошибке внешней программы. При конфликте пакетов сохраните сообщение и версии,
не заменяйте закреплённые версии произвольными ради продолжения.

Для другого существующего окружения добавьте к `ai-env.ps1` параметр
`-VenvPath 'D:\AI\venv'`, заменив пример своим путём. В каждой новой оболочке
повторяйте dot-source `ai-env.ps1`: он настраивает только текущую сессию. Скрипт задаёт
`HACKALEM_PYTHON`, локальные пути моделей, DLL, loopback Ollama и отключение
облачных функций/телеметрии. Он не подключает модели к API и не читает `.env`.

## 2. Подготовка инструментов и весов с доступом к сети

Установка пакетов, инструментов и первая загрузка моделей требуют сети.
На этом этапе записи совещаний не нужны. По умолчанию данные размещаются вне Git:

```text
%LOCALAPPDATA%\HackAlemAI\
  tools\ollama\ollama.exe
  tools\ffmpeg-n8.1-latest-win64-gpl-shared-8.1\bin\
  models\faster-whisper-large-v3\
  models\speaker-diarization-community-1\
  models\ollama\
  huggingface\       кеш и приватный HF-токен
  audio\             согласованные локальные записи
  results\           результаты диагностики
  logs\
  downloads\
```

Для другого диска задайте `$env:HACKALEM_AI_HOME = 'D:\HackAlemAI'` **до** запуска
`ai-env.ps1` и используйте тот же корень при загрузке и inference.

### Инструменты

Скачайте и распакуйте архивы так, чтобы итоговые пути совпали с деревом выше:

- [Ollama 0.34.3 Windows CLI](https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-windows-amd64.zip).
  Зафиксированный в handoff SHA-256:
  `306ce9e81e3491d147f558e60d7a389499f244d10f71859c6e4e899241d1b4ae`.
- [FFmpeg shared BtbN](https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-gpl-shared-8.1.zip).
  Хеш использованного архива:
  `393c050bd6515986c7ce6559c5bf69489d831b37b6cd68eb99ecfab4200688f6`.
  Нужна сборка **shared с DLL**: одной статической `ffmpeg.exe` для TorchCodec недостаточно.

Хеш локального архива можно получить командой
`Get-FileHash 'D:\Downloads\archive.zip' -Algorithm SHA256`, подставив свой путь.
Адрес FFmpeg содержит `latest` и изменяется: для точного воспроизведения нужен
сохранённый архив указанного хеша. Новый архив с другим хешем требует отдельной
проверки совместимости; его нельзя считать той же проверенной сборкой.

После распаковки повторно загрузите окружение и проверьте доступность инструментов:

```powershell
. .\scripts\local-ai\ai-env.ps1
ffmpeg -version
ollama --version
.\scripts\local-ai\start-ollama.ps1
```

`start-ollama.ps1` запускает Ollama скрыто на `127.0.0.1:11434`; журналы —
`$env:HACKALEM_AI_HOME\logs\ollama.stdout.log` и `ollama.stderr.log`.
Если сервер уже работает, скрипт **не меняет настройки существующего процесса**.
Проверьте его адрес и журнал (`Ollama cloud disabled: true`) до работы с записью.
Автозапуск при входе Windows скрипт не создаёт.

### Модели

| Модель | Зафиксированная ревизия / digest |
| --- | --- |
| `Systran/faster-whisper-large-v3` | `edaa852ec7e145841d8ffdb056a99866b5f0a478` |
| `pyannote/speaker-diarization-community-1` | `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` |
| `qwen3:4b` | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |

```powershell
ollama pull qwen3:4b
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py download-whisper --revision edaa852ec7e145841d8ffdb056a99866b5f0a478
```

Для Community-1 владелец аккаунта самостоятельно принимает условия на
[странице модели](https://huggingface.co/pyannote/speaker-diarization-community-1),
создаёт [HF Read token](https://huggingface.co/settings/tokens) того же аккаунта
и вводит его в своём интерактивном терминале:

```powershell
& $env:HACKALEM_PYTHON scripts/local-ai/hf-login.py
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py download-pyannote --revision 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee
```

Ввод токена скрыт. Не вставляйте его в команды, чат, EXE или Git. После полной
загрузки Community-1 токен для локального inference не нужен. Ошибка `403`
обычно требует проверить принятие условий и соответствие аккаунта токену.

Скрипт сохраняет ревизии в `hackalem-model.json` внутри каталога модели и
`results/download-*.json`. Тег Ollama изменяемый; сравните digest:

```powershell
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models | Select-Object name, digest
```

Для точного повторения сохраняйте проверенный каталог `models/ollama`; другой
digest фиксируйте как новую версию с отдельными результатами проверок.

## 3. Локальный запуск после скачивания

Далее сеть для загрузки пакетов/весов не требуется. Запустите отдельные проверки
по очереди из корня репозитория:

```powershell
. .\scripts\local-ai\ai-env.ps1
.\scripts\local-ai\start-ollama.ps1
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py runtime
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py load-whisper --device cuda
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py load-pyannote --device cuda
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py llm
& $env:HACKALEM_PYTHON scripts/local-ai/check-llm-cases.py --repeat 2
```

Проверяйте `$LASTEXITCODE` после каждого вызова и открывайте соответствующий JSON
в `$env:HACKALEM_AI_HOME\results`. Повторный вызов перезаписывает отчёт с тем же
именем: сохраните нужные результаты отдельно до следующего прогона.

| Команда | Что проверяет | Основной результат |
| --- | --- | --- |
| `runtime` | Версии, CUDA/CT2, декодирование синтетического WAV | `runtime.json`, `requirements-freeze.txt` |
| `load-whisper` | Загрузка весов и encoder на синтетических нулях | `adapter-load-whisper.json` |
| `load-pyannote` | Загрузка Community-1 с диска | `adapter-load-pyannote.json` |
| `llm` | Один синтетический RU/KK-текст, семь строгих проверок | `adapter-llm.json` |
| `check-llm-cases.py --repeat 2` | Семь синтетических случаев по два раза | `adapter-llm-cases.json` |

Расширенная LLM-проверка в handoff завершилась с `exit 1`: полностью прошли
**12 из 14** прогонов. Не скрывайте этот результат: обнаружено расхождение формы
имени «Антона»/«Антон», а также повреждение имени в summary. Схема JSON и проверки
источников не гарантируют правильность свободного текста. Для одного случая
поддерживается, например, `--case reported_task_not_narrator --repeat 2`.

Диагностика, кроме `download-*`, включает HF offline и блокирует внешние
`socket.connect/connect_ex` в своём Python-процессе, разрешая loopback.
Ollama работает отдельным процессом с `OLLAMA_NO_CLOUD=1`. Это **не системный
firewall** и не доказательство автономности всего EXE/API. После выполненной
серверной интеграции полную проверку без внешней сети ещё нужно подтвердить.

## 4. Проверка согласованной записи

В репозитории нет эталонной реальной записи. Подготовьте разрешённый локальный
WAV-фрагмент и присвойте путь переменной (замените пример существующим файлом):

```powershell
$localAiAudio = 'D:\Recordings\meeting-check.wav'
$localAiStt = Join-Path $env:HACKALEM_AI_HOME 'results\adapter-stt-audio.json'
$localAiDiar = Join-Path $env:HACKALEM_AI_HOME 'results\adapter-diarize-audio.json'
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py stt-audio --audio $localAiAudio --device cuda
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py diarize-audio --audio $localAiAudio --device cuda
& $env:HACKALEM_PYTHON scripts/local-ai/check-recording-results.py --audio $localAiAudio --stt $localAiStt --diarization $localAiDiar
& $env:HACKALEM_PYTHON scripts/local-ai/make-audio-review.py --audio $localAiAudio --stt $localAiStt --diarization $localAiDiar
```

Для CPU замените `--device cuda` на `--device cpu` у обеих моделей: STT выберет
`int8`. Не запускайте этапы параллельно на ограниченной VRAM. Параметр
`--num-speakers 2` допустим у `diarize-audio` только при известном числе говорящих
именно в этом фрагменте; «минимум два» не означает «ровно два».

`recording-checks.json` проверяет структуру, границы, порядок сегментов и совпадение
пути записи. Он не измеряет точность. `audio-review.html` — приватный локальный
отчёт для прослушивания интервалов: откройте файл из `results` в браузере и
сверьте слова, языки, timestamps и постоянство speaker ID. Отчёт ссылается на
локальный аудиофайл; не публикуйте его и не переносите отдельно от записи.
В handoff генерация HTML зафиксирована, его воспроизведение в браузере ещё не проверено.

Прямые диагностические команды выводят текст и интервалы говорящих раздельно.
В backend их объединение в единый транскрипт уже реализовано. Для WER нужен выверенный текст,
для DER — эталонная временная разметка говорящих. Метка `SPEAKER_00` не определяет
имя человека; четыре метки сами по себе не доказывают участие четырёх людей.

По handoff на 90-секундном фрагменте выполнены STT за **14.70 с** и диаризация
за **9.94 с**. Это результаты конкретного компьютера и записи, не гарантированная
скорость. Качество слов, mixed RU/KK и соответствие меток людям без эталона не подтверждены.

### Полная запись и сравнение с PDF

Новый [evaluate-meeting.py](../../scripts/local-ai/evaluate-meeting.py) принимает
свои входные файлы и сохраняет приватный отчёт вне Git. Для этапа `extract`
нужен `pypdf==6.10.0`: **на этапе подготовки с сетью** установите необязательную
зависимость (или используйте отдельное Python-окружение с ней):

```powershell
& $env:HACKALEM_PYTHON -m pip install -r scripts/local-ai/requirements-evaluation.txt
```

После установки инструментов/весов, загрузки `ai-env.ps1` и запуска локальной
Ollama выполните осознанный новый прогон. CLI использует CUDA для STT/диаризации;
параметра `--device cpu` у этого скрипта нет.

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$evaluationAudio = Read-Host 'Полный путь к согласованной записи'
$evaluationPdf = Read-Host 'Полный путь к PDF'
$evaluationOutput = Join-Path $env:HACKALEM_AI_HOME ('results\evaluation-' + [guid]::NewGuid().ToString('N'))
$evaluationArgs = @('--audio', $evaluationAudio, '--reference', $evaluationPdf, '--output-dir', $evaluationOutput)
foreach ($evaluationStage in @('extract', 'normalize', 'speech', 'diarize', 'compare', 'analyze', 'semantic-compare', 'report')) {
    & $env:HACKALEM_PYTHON scripts/local-ai/evaluate-meeting.py $evaluationStage @evaluationArgs
    if ($LASTEXITCODE -ne 0) { throw "Stage failed: $evaluationStage; inspect the private local log." }
}
```

`normalize` создаёт полный mono PCM16 WAV 16 kHz; `speech` читает исходную запись,
`diarize` — WAV-копию. `compare` сопоставляет тексты, `analyze` извлекает поручения
только из распознанной речи, `semantic-compare` отдельно сопоставляет её с PDF.
Откройте `$evaluationOutput\report.html` локально. PDF без извлекаемого текста
не поддерживается (OCR нет). При отдельном FFmpeg-пути добавьте `--ffmpeg`.

Каталог должен находиться вне любого Git-репозитория. SHA-256 входов записываются
в `inputs.json`; результаты и логи не перезаписываются. После неудачного этапа
сохраните его каталог для разбора и используйте новый каталог для повторного
полного прогона. Содержимое записи и traceback остаются в приватных файлах.

В обновлённом handoff зафиксирован исторический прогон полной записи **274.25 с**:
STT **41.48 с**, диаризация **16.09 с**, анализ Ollama **18.84 с**, семь поручений.
Смысловая сверка PDF/STT дала неопределённый результат; текстовое совпадение
не является точностью распознавания, PDF не подтверждён как дословный эталон.
Полный запуск именно новой переносимой версии CLI ещё не выполнен: эти времена
относятся к исходному локальному скрипту. `exit 0` означает завершение этапа,
а не подтверждение качества. Пределы текста, диагностическая привязка спикеров
и подробности — в [handoff](handoff.md#воспроизводимая-проверка-полной-записи).

## 5. Автономные тесты и граница интеграции

Тесты адаптеров используют заглушки; они не скачивают модели и не заменяют
проверки inference выше. Команда из корня репозитория после `ai-env.ps1`:

```powershell
Push-Location backend
try {
    & $env:HACKALEM_PYTHON -m unittest discover -s tests/local_ai -v
} finally {
    Pop-Location
}
```

В обновлённом handoff зафиксировано **43/43** теста: 29 прежних адаптерных и
14 новых проверок диагностики с синтетикой/моками. При интеграции также пройдены
22 backend-проверки и 10 проверок native-клиента с настоящим API и подменёнными
моделями. Сквозной запуск API на GPU с реальной записью пока не подтверждён.
[Общий отчёт проверок](../verification.md) отделяет UI, API и AI-сценарии.

Исходники: [LocalSTTService](../../backend/app/services/stt/local.py),
[LocalDiarizationService](../../backend/app/services/diarization/local.py),
[LocalMeetingAnalysisService](../../backend/app/services/llm/local.py).
Они загружают модели явно при вызове. STT возвращает доминирующий язык записи,
а не надёжные языковые метки каждой реплики. LLM по умолчанию ограничен 6000
символами входа; автоматического разбиения длинных встреч нет. Автор поручения
выводится из проверяемого самопредставления в тексте, а не определяется по голосу.
Очередь, хранение, совмещение timestamps и маршруты результата/экспорта уже
реализованы. Остаются обработка длинного текста и сквозная GPU-проверка с EXE
и настоящими моделями; подготовка сервера — [backend-launch.md](../backend-launch.md).
Параметры конструкторов — в [handoff](handoff.md#интерфейсы-для-medet).

## Если запуск не проходит

| Симптом | Что проверить |
| --- | --- |
| `Python environment missing` | Наличие `backend/.venv/Scripts/python.exe` или правильный `-VenvPath` |
| Ошибка TorchCodec / DLL | FFmpeg **shared**, каталог `bin`, повторный dot-source `ai-env.ps1`, версии Torch/TorchCodec |
| CUDA недоступна / недостаточно VRAM | Вывод `runtime`, существующий драйвер, последовательный запуск; `--device cpu` для диагностики без GPU |
| `Local ... weights are missing` | Полноту загрузки, одинаковый `HACKALEM_AI_HOME`, локальные `model.bin` / `config.yaml` |
| HF `403` | Условия Community-1 приняты тем же аккаунтом, которому принадлежит Read token |
| Ollama недоступна / модель отсутствует | `start-ollama.ps1`, локальные журналы, `/api/tags`, выполненный `ollama pull` на этапе подготовки |
| Непрохождение LLM-кейса | Сохранить JSON и digest; проверить источник и содержание вручную, не ослаблять критерий ради exit 0 |
| Health `not_ready`, загрузка HTTP `503` | Проверьте пути моделей, FFmpeg, локальную Ollama и зависимости по [backend-launch.md](../backend-launch.md) |
| EXE получает `501` | Запущена старая версия каркаса; обновите код и перезапустите backend по актуальной инструкции |

Модели, окружения, записи, транскрипты, локальные результаты и токены остаются вне
Git. Источники совместимости и исходные параметры машины собраны в
[подробном handoff](handoff.md#официальные-источники-совместимости).
