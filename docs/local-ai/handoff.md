# Local AI — передача Medet

**Срочное обновление 23.09.2026:** на `main` / `46c2c4d` backend запущен без
переустановок; health `ok`, одна реальная запись обработана через native EXE,
статус `completed`, DOCX/PDF сохранены. См. [E2E smoke report](e2e-smoke-46c2c4d.md).
Упоминания scaffold и неподтверждённого E2E ниже описывают предыдущую передачу;
новая проверка подтверждает один сценарий, не качество распознавания.

Проверено 23.09.2026 на компьютере Amankos. Ветка `codex/local-ai-setup`.
Исходная инструкция команды — `68f332b`; повторный fetch обнаружил `fbdd8c6`
(SAMRUK KAZYNA, Windows EXE). Контракты AI не изменились. Эта работа не создаёт
backend/API или клиент: подключение адаптеров выполняет Medet.
При текущей передаче `origin/main` на `a61ed5a` объединён в свою ветку обычным merge,
без конфликтов, reset/clean и force push. Desktop и прежние адаптеры уже в main;
активный клиент — native C# / WinForms, не Streamlit/pywebview.
Общие API, README и desktop в рамках Local AI не редактировались; изменения этих
файлов пришли только с разрешённым merge main. Backend всё ещё scaffold/501.

## Готовность и ограничения

- Установлены Python AI-окружение, FFmpeg shared, Ollama; скачаны Whisper large-v3,
  Qwen3:4b и Community-1. Локальный HF-вход и доступ к gated-модели подтверждены.
- CUDA-вычисления, декодирование WAV и реальный encoder Whisper проверены.
- Три адаптера реализуют существующие `base.py`; импорт/конструкторы не загружают модели.
- Повторно пройдены 43 автономных unit-теста: 29 прежних и 14 новых тестов
  воспроизводимой диагностики. Это моки/синтетика, не новая проверка качества моделей.
  `pip check` и отдельная проверка схемы backend проходят.
- Пропуск `assigned_by` исправлен через проверяемую связь самопредставления,
  speaker ID и исходной реплики. Прежний тест без ослабления проверок проходит **7/7**.
  На семи разных синтетических сценариях по два повтора проверка автора проходит во всех
  14 прогонах. Полный строгий набор: **12/14**, см. ограничения падежа имени и summary ниже.
- Community-1 загружена с диска на CUDA за 6.11 с с блокировкой внешних Python-соединений.
- На первых 90 сек предоставленного владельцем «Совещание №1.mp3» действительно выполнены
  STT (14.70 с) и diarization (9.94 с), последовательно и локально. Проверены структура,
  порядок и попадание интервалов в длительность аудио.
- На полной записи 274.25 с выполнены STT, diarization после преобразования в WAV,
  сравнение текста с PDF и локальный анализ Ollama. Измерения приведены ниже;
  полная запись в текущем обновлении повторно через модели не запускалась.
- Точность слов и реальное соответствие меток людям **не подтверждены ручным прослушиванием**:
  PDF предоставлен, но как дословный эталон не подтверждён; WER/DER не измерены.
  Оценка mixed ru/kk и сквозной EXE/API-сценарий
  остаются отдельными проверками; доминирующий язык этого фрагмента по Whisper — ru.

Исходная папка `C:\Users\Amankos\Downloads\Hakaton` и её незавершённые изменения
сохранены. Работа для команды — в отдельном worktree
`C:\Users\Amankos\Downloads\Hakaton-local-ai`. Установленное окружение и скачивания
используются повторно; ничего не сбрасывалось и не очищалось.

## Железо и версии

Windows 11 Lite x64, build 22631; Ryzen 7 7745HX (8C/16T), RAM 31.3 GiB;
RTX 4060 Laptop, 8188 MiB VRAM, compute capability 8.9. Свободно на C: после
основных установок около 146 GiB (до них около 162 GiB).

| Компонент | Проверенная версия |
| --- | --- |
| Python x64 | 3.11.9 |
| torch / torchaudio | 2.9.1+cu126 |
| CUDA runtime / cuDNN | 12.6 / 9.10.2, DLL из PyTorch |
| TorchCodec | 0.9.1 |
| faster-whisper / CTranslate2 | 1.2.1 / 4.8.2 |
| pyannote.audio / huggingface-hub | 4.0.7 / 0.36.2 |
| httpx / Pydantic | 0.28.1 / 2.10.5 |
| FFmpeg shared | n8.1.3-20260922, BtbN |
| Ollama standalone CLI | 0.34.3 |
| Текущий драйвер NVIDIA | 591.86 |

`backend/requirements-ai.txt` фиксирует основные AI-зависимости;
`scripts/local-ai/requirements-observed.txt` — полный снимок установленного окружения,
включая прежние backend-пакеты, а не рекомендация всех этих версий для production.
Python 3.11.9 — использованный официальный Windows installer, не последняя
security-версия ветки 3.11. Обновление Python и аудит старых backend-пинов согласовать отдельно.
Полный CUDA Toolkit и Docker не устанавливались.

## Модели и размещение

Корень данных: `%LOCALAPPDATA%\HackAlemAI` (сохранённое техническое имя каталога).

| Модель | Ревизия / digest | Состояние |
| --- | --- | --- |
| Systran/faster-whisper-large-v3 | `edaa852ec7e145841d8ffdb056a99866b5f0a478` | скачана, CUDA `int8_float16` |
| qwen3:4b, Q4_K_M | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` | скачана, 2 497 293 931 bytes |
| pyannote/speaker-diarization-community-1 | `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` | скачана, CUDA offline-load и inference проверены |

```text
C:\Users\Amankos\Downloads\Hakaton\.venv\Scripts\python.exe
%LOCALAPPDATA%\HackAlemAI\
  tools\ollama\ollama.exe
  tools\ffmpeg-n8.1-latest-win64-gpl-shared-8.1\bin\
  models\faster-whisper-large-v3\
  models\ollama\
  models\speaker-diarization-community-1\
  huggingface\    (кеш и приватный токен)
  audio\          (согласованные записи)
  results\        (результаты диагностики, не Git)
  logs\
  downloads\      (сохранённые архивы)
```

Ни веса, ни токены, ни записи/результаты не коммитятся. Токен не нужен для inference
после полной загрузки Community-1. Нельзя передавать его клиенту или вводить в чат.

## Запуск на этом компьютере

Из PowerShell; не пересоздавать уже установленную `.venv`:

```powershell
cd C:\Users\Amankos\Downloads\Hakaton-local-ai
. ./scripts/local-ai/ai-env.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
& ./scripts/local-ai/start-ollama.ps1
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py runtime
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py load-whisper
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py llm
# Проверять $LASTEXITCODE после КАЖДОЙ команды; исходный llm теперь проходит 7/7.
& $env:HACKALEM_PYTHON scripts/local-ai/check-llm-cases.py --repeat 2
# Полный расширенный набор пока возвращает 1 (12/14), не скрывать это.
Push-Location backend
& $env:HACKALEM_PYTHON -m unittest discover -s tests/local_ai -v
Pop-Location
& $env:HACKALEM_PYTHON -m pip check
```

Скрипт окружения добавляет torch/lib и FFmpeg DLL в PATH. Он задаёт настройки
текущей оболочки, но не подключает адаптеры в backend автоматически.
`start-ollama.ps1` запускает процесс скрыто, без автозапуска при входе Windows.
Если Ollama уже работает, его настройки не меняются: проверить журнал
`logs/ollama.stderr.log` на `Ollama cloud disabled: true` и listener на 127.0.0.1.

### Переменные окружения для backend

Dot-source `ai-env.ps1` нужно выполнять в той же PowerShell-оболочке, из которой
Medet запускает backend. Наличие переменных не выбирает сервисы автоматически:
пути и параметры нужно передать конструкторам `Local*Service` явно.

| Переменная | Значение после `ai-env.ps1` / назначение |
| --- | --- |
| `HACKALEM_VENV`, `HACKALEM_PYTHON` | существующая `.venv` и её `Scripts/python.exe` |
| `HACKALEM_AI_HOME` | `%LOCALAPPDATA%/HackAlemAI`, можно задать до dot-source |
| `WHISPER_MODEL_PATH`, `PYANNOTE_MODEL_PATH` | локальные каталоги моделей под `HACKALEM_AI_HOME/models` |
| `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | `cuda`, `int8_float16`; backend должен явно применить эти значения |
| `HF_HOME` | приватный кеш/токен вне Git, токен для inference не нужен |
| `HF_HUB_DISABLE_TELEMETRY`, `DO_NOT_TRACK`, `PYANNOTE_METRICS_ENABLED` | `1`, `1`, `0` |
| `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_MODELS` | `127.0.0.1:11434`, `qwen3:4b`, внешний каталог моделей |
| `OLLAMA_NO_CLOUD`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS` | `1`, `1`, `1`; применяются к процессу Ollama при запуске |
| `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_KEEP_ALIVE` | `4096`, `0`; диагностические запросы задают собственный context |
| `PYTHONUTF8`, `PATH` | UTF-8; torch/lib, FFmpeg shared DLL и Ollama CLI |

Для запуска только inference, **после** загрузки всех весов:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
```

Диагностический скрипт задаёт offline-флаги и запрещает внешние Python
`socket.connect/connect_ex`; это не firewall для всего компьютера и не настройка
backend. Тот должен отдельно соблюдать локальный режим. HF-токен в API/EXE не передавать.

### Доступ Community-1 на новом компьютере

На этом компьютере вход, принятие условий и скачивание завершены. На новом компьютере
владелец самостоятельно принимает условия на
[странице модели](https://huggingface.co/pyannote/speaker-diarization-community-1).
Нужен [HF Read token](https://huggingface.co/settings/tokens) того же аккаунта с доступом к gated-модели.
Ввод только в собственном интерактивном терминале, символы скрываются:

```powershell
& $env:HACKALEM_PYTHON scripts/local-ai/hf-login.py
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py download-pyannote
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py load-pyannote
```

Скачивание явно отделено от offline-проверок; ревизии по умолчанию зафиксированы.
При повторном запуске Hugging Face использует локальный кеш/прогресс скачивания.

### Проверка предоставленной записи

Владелец указал `C:\Users\Amankos\Downloads\Совещание №1.mp3` и «минимум 2 человека».
Файл: mono MP3, 48 kHz, 274.25 с. Исходник не изменён; для ограниченного теста
FFmpeg создал `audio/meeting1-first90-20260923.wav`: первые 90 секунд, mono PCM16, 16 kHz.
SHA-256 фрагмента: `90c6b9d36a375eb1700ca433a478084c2c1d522b17fffea7e2a401ed07d88031`.
Число говорящих не фиксировалось: «минимум 2» не значит «ровно 2», а число людей
в полном файле не гарантирует число в его первом фрагменте.

```powershell
$sample = "$env:HACKALEM_AI_HOME\audio\meeting1-first90-20260923.wav"
$sttResult = "$env:HACKALEM_AI_HOME\results\adapter-stt-audio.json"
$diarResult = "$env:HACKALEM_AI_HOME\results\adapter-diarize-audio.json"
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py stt-audio --audio $sample
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py diarize-audio --audio $sample
& $env:HACKALEM_PYTHON scripts/local-ai/check-recording-results.py --audio $sample --stt $sttResult --diarization $diarResult
& $env:HACKALEM_PYTHON scripts/local-ai/make-audio-review.py --audio $sample --stt $sttResult --diarization $diarResult
```

Полученные JSON сохраняются в `results/adapter-*.json`, содержимое записи не печатается
в консоль. `recording-checks.json` содержит только метрики; `audio-review.html` —
приватный локальный отчёт с аудиоплеером и кнопками интервалов для ручного прослушивания.
Открыть его локально в браузере, не публиковать и не отправлять в облако. HTML-отчёт
сгенерирован, но его воспроизведение в браузере ещё не проверено.
В нём STT и speaker turns показаны отдельно: объединение для продукта — задача backend.
Нужна ручная сверка слов/меток/границ; без неё успешный inference не доказывает качество.

## Воспроизведение окружения на другом Windows-компьютере

Нужны Python 3.11 x64 и совместимый существующий NVIDIA-драйвер. **Скрипты драйвер
не устанавливают.** Для CPU явно указать `--device cpu`, STT использует `int8`;
этот режим здесь не бенчмаркался.

Из корня репозитория:

```powershell
py -3.11 -m venv backend/.venv
& ./backend/.venv/Scripts/python.exe -m pip install torch==2.9.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu126
& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-ai.txt -r backend/requirements-api.txt -c scripts/local-ai/requirements-observed.txt
& ./backend/.venv/Scripts/python.exe -m pip check
. ./scripts/local-ai/ai-env.ps1
```

Установить/распаковать внешние инструменты в описанные выше каталоги:

- [Ollama 0.34.3 Windows CLI](https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-windows-amd64.zip),
  SHA-256 `306ce9e81e3491d147f558e60d7a389499f244d10f71859c6e4e899241d1b4ae`.
- [FFmpeg shared BtbN](https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-gpl-shared-8.1.zip),
  использованный SHA-256 `393c050bd6515986c7ce6559c5bf69489d831b37b6cd68eb99ecfab4200688f6`.
  URL `latest` изменяемый: для точного повтора использовать сохранённый архив этого хеша,
  либо отдельно проверить совместимость новой сборки; статическая сборка без DLL не подходит TorchCodec.

Хеши архивов при установке сверены с release assets. Затем:

```powershell
& ./scripts/local-ai/start-ollama.ps1
ollama pull qwen3:4b
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py download-whisper
# Далее локальный HF login, download-pyannote и проверки, описанные выше.
```

Тег Ollama также изменяемый. Сверить digest через `/api/tags`; для точного повторения
сохранить текущую папку `models/ollama`. Команды чистой установки документированы,
но второе чистое окружение повторно не создавалось.

## Интерфейсы для Medet

Прямые импорты из `local.py`, без изменений общих `__init__.py`:

```python
import os
from app.services.stt.local import LocalSTTService
from app.services.diarization.local import LocalDiarizationService
from app.services.llm.local import LocalMeetingAnalysisService

stt = LocalSTTService(os.environ["WHISPER_MODEL_PATH"])
diarization = LocalDiarizationService(os.environ["PYANNOTE_MODEL_PATH"])
analysis = LocalMeetingAnalysisService()
# Инициализация выше ещё ничего не загружает. Затем последовательно:
# transcript = stt.transcribe(local_audio_path)
# turns = diarization.diarize(local_audio_path)
# labeled_text = ...  # объединение временных меток делает backend
# summary, tasks = analysis.analyze(labeled_text)
```

- STT: `model_path`, `device='cuda'`, `compute_type='int8_float16'`, `cpu_threads=8`,
  `beam_size=5`, `language=None`, `release_after_call=True`. `transcribe(Path)` →
  `TranscriptResult`. `task='transcribe'`, `multilingual=True` при автоматическом языке;
  не переводит речь в английский. Для CPU явно `device='cpu', compute_type='int8'`.
- Языки отдельных STT-сегментов — `[]`: API faster-whisper не даёт надёжной per-turn
  метки для mixed речи. `TranscriptResult.detected_languages` содержит только
  доминирующий язык записи, а не обещание обнаружить все языки.
- Diarization: `model_path`, `device='cuda'`, `exclusive=False`, `num_speakers=None`,
  `min_speakers=None`, `max_speakers=None`, `release_after_call=True`.
  `diarize(Path)` → отсортированный `list[DiarizationTurn]`.
  `exclusive=True` выбирает `output.exclusive_speaker_diarization` Community-1;
  обычный режим сохраняет перекрытия. Число 2 задавать только для известного теста,
  не всех встреч. `SPEAKER_00` — анонимный ID, не имя человека.
- LLM: `base_url='http://127.0.0.1:11434'`, `model='qwen3:4b'`,
  `timeout_seconds=180`, `num_ctx=4096`, `max_transcript_chars=6000`, `retries=1`
  (повтор только некорректного JSON/источника). Вход: `SPEAKER_00: текст` либо
  `[SPEAKER_00] текст`; выход: `tuple[str, list[MeetingTask]]`.
  Строгая схема, `think=False`, `temperature=0`, `num_predict=1800`, `keep_alive=0`.
  Генерация source-полей ограничена enum исходных полных реплик и speaker ID;
  затем независимо проверяется соответствие пары speaker/quote и присутствие имён/сроков в тексте.
  Это не доказывает правильность назначения каждого поручения.
- `assigned_by` больше не берётся на доверии из LLM. Имя связано со спикером только
  явным самопредставлением в начале реплики (`Меня зовут`, `Моё имя`, `Менің атым`,
  `Менің есімім`, `My name is`) с одним–тремя словами имени. В коде нет имён из теста.
  После проверки цитаты все прямые поручения этого спикера получают это имя,
  даже если assignee неизвестен. Противоречивые представления, цитирование/косвенная речь,
  отсутствующий источник и неподдержанные формы представления дают null.
  Это намеренно консервативная эвристика, не распознавание личности по голосу.
  Голое `Я ...` не используется: оно может обозначать профессию/состояние.
- Срок сохраняется исходной фразой. `created_at` нельзя считать датой совещания.
  Неизвестные значения допускают `None`; источник без доказательств — `""`/`""`
  с общим предупреждением в локальном логе. Отдельного warnings-поля в общем
  интерфейсе нет; необходимость его добавления согласовать с Medet.
- Превышение лимита текста вызывает ошибку, не молчаливое усечение. Лимит символов
  не равен токенам: 4096 context не гарантирует вместимость любой строки до 6000 символов.
  Длинные встречи требуют chunking/сведения поручений в backend и отдельной оценки.
  Автоматического переключения на demo, CPU или облако нет.

В первой интеграции использовать **один worker обработки** и последовательные этапы:
блокировки отдельных адаптеров не являются глобальной очередью GPU. STT/pyannote
освобождают модели после вызова, Ollama — после ответа. При `release_after_call=False`
предусмотрен `close()`. Несколько Uvicorn workers не должны запускать модели параллельно.
Ошибки маппить в безопасный `processing_failed`; пользователю не выдавать внутренние
traceback/пути. EXE обращается только к backend, не к Ollama. API/экспорт здесь не подключались.

## Наблюдаемые проверки

| Проверка | Результат |
| --- | --- |
| Unit-тесты адаптеров и диагностики | 43/43 после merge a61ed5a; моки/синтетические данные, не качество моделей |
| `pip check` | нет конфликтов |
| Runtime | PyTorch CUDA matmul; CT2 `int8_float16`; импорт pyannote; TorchCodec декодирует синтетический WAV |
| Whisper через адаптер | загрузка 6.27 с, encoder `[1,1500,1280]`; синтетические нули, не речь |
| Память при encoder | Python RSS 885.4 MiB; nvidia-smi 2031 MiB всего на GPU, снимок, **не пик** и не только модель |
| Qwen, прежний тест через адаптер | 9.20 с, строгие прежние проверки 7/7, exit 0 |
| Qwen, 7 разных примеров × 2 | 12/14 полностью прошли, 3.70–9.31 с/пример; все проверки assigned_by прошли |
| Ollama GPU | 37/37 слоёв; оценка журнала 3030 MiB (веса 2375 + context 576 + compute 79), не измеренный пик |
| Loopback | listener `127.0.0.1:11434`; cloud disabled подтверждён в журнале |
| Community-1 load | 6.11 с, Python RSS 916.2 MiB; снимок GPU 157 MiB до inference, не пик |
| Реальное STT, 90 с | 14.70 с, RTF 0.1633, 11 сегментов, границы 0.00–89.98 с, 1293 символа |
| Реальная diarization, 90 с | 9.94 с, 21 интервал, 4 анонимные метки; не доказательство четырёх реальных людей |
| Сверка времени | все интервалы внутри 90 с, STT упорядочены; смысл слов/личности/DER вручную не подтверждены |

Ранний тест 6/7 действительно пропускал автора PDF: raw Qwen выдавал null даже при
правильном SPEAKER_00. Исправление — связь с самопредставлением после проверки источника,
а не имя, зашитое под тест. Прежние 7 проверок и исходный транскрипт не ослаблялись.
Дополнительные тесты меняют имена, speaker ID, язык представления и тип поручения;
отдельно проверяют неизвестного автора, конфликт и косвенную речь.

Найденные дополнительные проблемы и ограничения:

- Qwen искажал цитаты (`DOCX` → `DOC:`, повреждал слова). Теперь source_text выбирается
  из исходных реплик ограниченной схемой; проверка пары speaker/quote не отключена.
- Фраза об отсутствии срока попадала в deadline. Явные русские/казахские формулировки
  отсутствия теперь нормализуются в null после проверки их наличия в исходном тексте;
  «не позднее пятницы» не считается отсутствием срока (отдельный тест).
- Расширенный набор оставлен строгим и возвращает exit 1: в примере косвенной речи
  ожидалось буквальное `Антона`, модель возвращает именительный `Антон`. Это расхождение
  формы имени, не доказанная подмена человека; ожидаемые значения ради зелёного теста не менялись.
  При этом в summary того же примера наблюдается испорченное `Анто:`. Контроль источников
  не устраняет все ошибки свободного текста summary/task; требуется просмотр человеком.
- В косвенной речи адаптер воздерживается от назначения автора (null), даже если Qwen
  предлагает имя третьего лица. Автоматическое подтверждение автора пересказа пока не реализовано.
- Community-1 сначала вернула 403: вход был выполнен, но новый аккаунт не принял условия.
  Владелец принял условия лично; повторное скачивание завершилось успешно.
- На inference pyannote предупредил об отключении TF32 ради воспроизводимости и
  `std(): degrees of freedom <= 0` для короткого фрагмента pooling. Вызов завершился,
  интервалы корректны по форме; влияние предупреждения на качество без эталона неизвестно.
- Thinking с бюджетом 3000 токенов ранее исчерпал лимит до JSON, поэтому выключен.

Диагностические процессы блокируют внешние Python socket-соединения и включают
HF offline; разрешён loopback. Ollama отдельно запущен с `OLLAMA_NO_CLOUD=1`.
Адаптеры не скачивают веса автоматически; STT использует `local_files_only=True`,
pyannote — локальный config и HF offline, LLM запрещает внешние URL, proxy-env,
redirects и remote-модели. STT/diarization на предоставленном фрагменте и загрузка
Community-1 прошли при этом запрете внешней сети. Это не системный firewall и не проверка
всего EXE/API при физически отключённом интернете.

Драйвер 591.86 был установлен **до** просьбы владельца не устанавливать драйвер:
обычный NVIDIA installer завершился ошибкой, ранее настройка была завершена через
подходящие подписанные INF и PnPUtil. После запрета никаких действий с драйвером
не выполняется. Нужные CUDA/cuDNN DLL предоставлены wheel PyTorch, не отдельным Toolkit.

## Полная запись: сверка с PDF и анализ Ollama

Локальная проверка 2026-09-23 выполнена на полной записи длительностью 274.25 с
и предоставленном владельцем четырёхстраничном PDF. Все исходники, извлечённый текст,
расшифровки, ответы модели и HTML-отчёты остались вне Git, в локальном каталоге
`%LOCALAPPDATA%/HackAlemAI/results/meeting1-pdf-evaluation/`.
Это отдельная проверка, не замена приведённого выше теста первых 90 секунд.

| Этап | Наблюдаемый результат |
| --- | --- |
| STT полной записи | 41.48 с; 48 сегментов, 4101 символ; границы 0.00–274.22 с |
| Diarization полной записи после преобразования в WAV | 16.09 с; 65 интервалов, 4 анонимные метки; последний конец 274.013 с |
| Нормализованное сравнение текста | PDF: 928 слов; STT: 559 слов; 501 совпадение, 41 замена, 386 удалений, 17 вставок относительно PDF |
| Ollama: анализ только распознанной речи | 18.84 с; 7 поручений; проверка источников адаптера прошла |
| Ollama: отдельная смысловая сверка PDF/STT | 6.77 с; тип документа не определён моделью, 2 неопределённых наблюдения; уверенная сверка не получена |

Использованы именно модели и ревизии из таблицы выше. STT: CUDA `int8_float16`,
8 CPU threads, beam 5, автоязык/multilingual, VAD и word timestamps; транскрипция,
не перевод. Community-1: CUDA, `exclusive=False`, без заданного количества людей,
`release_after_call=True`. Qwen3:4b Q4_K_M: loopback Ollama 0.34.3,
`think=False`, temperature 0, keep_alive 0. Анализ: context 8192, максимум
10000 символов, num_predict 1800, timeout 180 с, один повтор при неверном ответе.
Смысловая сверка: context 12288, num_predict 3500, timeout 300 с.
PDF извлечён через `pypdf==6.10.0`, `extraction_mode="layout"`, без OCR.

Приведённое время STT/diarization/анализа измерялось вокруг вызова адаптера,
включая его ленивую загрузку и освобождение; это не GPU-only latency. Для
смысловой сверки измерен локальный запрос с проверкой модели и ответа.
Отдельное время извлечения PDF, FFmpeg, выравнивания слов, генерации HTML и
полное end-to-end время **не измерены в исходном прогоне**. Не суммировать
отдельные времена в обещание полного времени обработки. Новый скрипт дополнительно
сохраняет `stage_wall_seconds`; это новая метрика, не подмена прежних измерений.

Сравнение слов использует NFKC, приведение регистра, `ё` → `е`, игнорирование
пунктуации и выравнивание Левенштейна с единичной стоимостью операций.
Совпало 89.62% слов распознавания и 53.99% слов PDF; доля операций редактирования
относительно PDF — 47.84%. **Это не подтверждённая точность распознавания и не
эталонный WER:** документ имеет структуру протокола, его дословное соответствие
аудио не проверено. Дополнительные слова PDF могут быть редакторским оформлением
или пропусками STT; без прослушивания отделить одно от другого нельзя.

Прямой запуск pyannote на MP3 завершился ошибкой длины декодированного фрагмента:
для первых 10 с ожидалось 480000 отсчётов, получено 478895. Диагностический обход —
создание отдельной полной копии PCM WAV, mono, 16 kHz, signed 16-bit через FFmpeg,
после чего diarization завершилась. Исходный MP3 не изменялся. Автоматическая
нормализация входного аудио в production-адаптер пока не добавлена; Medet следует
учесть этот случай при подготовке аудио и обработке ошибок.

Для локального анализа реплики диагностически сопоставлены со спикерами по
перекрытию интервалов; две неоднозначные реплики получили неопределённые метки.
Это не production-объединение и не подтверждение личности или числа людей.
Ollama получила только распознанную речь, без подстановки текста PDF;
использованы `num_ctx=8192`, `max_transcript_chars=10000`.
Все 7 поручений имеют `assigned_by=null`: подтверждённого самопредставления
для назначения автора не найдено. Наличие исполнителей и сроков в ответе
не означает, что их смысловое назначение проверено человеком.

Отдельная смысловая сверка (`num_ctx=12288`) проверяла существование ссылок
на исходные блоки, но не подтвердила семантическую правильность выводов.
Её неопределённый результат нельзя выдавать за успешную проверку полноты.
Ручная сверка аудио, временных меток, mixed ru/kk и DER остаётся незавершённой.
Приватный сводный отчёт: `results/meeting1-pdf-evaluation/report.html` под
локальным корнем HackAlemAI. Отчёт сгенерирован; визуальная проверка в браузере
не зафиксирована. В текущей передаче код адаптеров не менялся; повторены автономные
тесты, но новые модельные прогоны на записи не выполнялись. Сохранённые числовые
результаты исходного прогона перечитаны локально; содержимое встречи не выводилось.

**Граница ручной проверки:** ручное прослушивание, исправление расшифровки,
подтверждение личностей и числа людей, оценка RU/KK, поручений и сроков не выполнены.
Автоматически проверялись успешность вызовов, форма/границы интервалов, наличие
источников, операции выравнивания и ссылки на существующие фрагменты. Это не
равнозначно проверке смысла человеком. В отчётах отсутствует подтверждённый DER/WER.

## Воспроизводимая проверка полной записи

`scripts/local-ai/evaluate-meeting.py` перенесён из локального диагностического
скрипта исходной проверки. Запись, PDF и каталог результата теперь передаются
аргументами; приватных примеров в исходнике нет. Все восемь этапов запускаются
раздельно: `extract`, `normalize`, `speech`, `diarize`, `compare`, `analyze`,
`semantic-compare`, `report`. `speech` обрабатывает исходную запись, `diarize` —
полную PCM WAV-копию. Обе временные шкалы начинаются с нуля; это не обрезка.

На текущем ПК PDF-пакет уже есть в отдельном bundled Python. Следующие команды
не требуют переустановки AI-окружения, повторного входа или скачивания моделей:

```powershell
Set-Location 'C:\Users\Amankos\Downloads\Hakaton-local-ai'
. ./scripts/local-ai/ai-env.ps1 -VenvPath 'C:\Users\Amankos\Downloads\Hakaton\.venv'
& ./scripts/local-ai/start-ollama.ps1
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$evaluationPdfPython = 'C:\Users\Amankos\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
# Локальные пути вводятся только в своём терминале. Кавычки в ответ не включать.
$evaluationAudio = Read-Host 'Полный путь к согласованной записи'
$evaluationPdf = Read-Host 'Полный путь к PDF'
$evaluationOutput = Join-Path $env:HACKALEM_AI_HOME ('results\evaluation-' + [guid]::NewGuid().ToString('N'))
$evaluationArgs = @('--audio', $evaluationAudio, '--reference', $evaluationPdf, '--output-dir', $evaluationOutput)
& $evaluationPdfPython scripts/local-ai/evaluate-meeting.py extract @evaluationArgs
if ($LASTEXITCODE -ne 0) { throw 'PDF extraction failed; inspect private output locally.' }
foreach ($evaluationStage in @('normalize', 'speech', 'diarize', 'compare', 'analyze', 'semantic-compare', 'report')) {
    & $env:HACKALEM_PYTHON scripts/local-ai/evaluate-meeting.py $evaluationStage @evaluationArgs
    if ($LASTEXITCODE -ne 0) { throw "Local stage failed: $evaluationStage; inspect private output locally." }
}
# Открыть $evaluationOutput\report.html локально, не публиковать.
```

Это команды **для осознанного нового реального прогона**, а не требование повторить
модели при каждом обновлении документации. Любой этап можно вызвать отдельно с
теми же аргументами после его зависимостей. На другом ПК для `extract` нужен
Python с `scripts/local-ai/requirements-evaluation.txt` (только `pypdf==6.10.0`);
можно использовать отдельное окружение. Оно не заменяет AI runtime.

Меры сохранности и пределы скрипта:

- `--output-dir` должен быть вне Git (проверяется `.git`-каталог или файл worktree
  у всех родителей и разрешённый физический путь). `.gitignore` не считается защитой.
- `inputs.json` связывает этапы с SHA-256 обоих входных файлов. Повторное использование
  каталога с другими входами запрещено. Выходные файлы/логи этапа не перезаписываются;
  после частичной ошибки выбирать новый каталог, прежний сохранять для разбора.
- Содержимое и traceback остаются в приватных `*.log`/JSON/HTML вне Git. Консоль
  сообщает этап, статус, тип ошибки и время, а не исходные реплики. Эти логи тоже
  нельзя отправлять во внешние сервисы без удаления чувствительных данных.
- FFmpeg запускается без перезаписи и с разрешёнными протоколами `file,pipe`;
  его ошибка не заменяется демо. В PDF без извлекаемого текста OCR не выполняется.
- Выравнивание имеет предел 4 млн ячеек `(N+1)*(M+1)`; это диагностический алгоритм
  для коротких документов, не масштабируемый анализ многочасовых встреч.
- Смысловая сверка ограничена 16000 символов PDF и 10000 символов распознанных
  реплик. Проверка существования evidence ID не доказывает истинность вывода.
  Успешный exit 0 означает завершение этапа, не успешную смысловую верификацию.
- Сгенерированный HTML экранирует текст, запрещает сетевой контент через CSP;
  это локальный артефакт, не опубликованная страница. Визуальная QA не заявляется.

Перенесённый CLI проверен автономно, но полный реальный восьмиэтапный запуск именно
его новой версии ещё не выполнялся. Исторические времена выше относятся к
исходному локальному скрипту с теми же адаптерами и параметрами, не к новому замеру.

### Проверки этой передачи

Из корня, после `ai-env.ps1`:

```powershell
Push-Location backend
try {
    & $env:HACKALEM_PYTHON -m unittest discover -s tests/local_ai -v
    if ($LASTEXITCODE -ne 0) { throw 'Local AI unit tests failed' }
    & $env:HACKALEM_PYTHON -c "import runpy; runpy.run_path('tests/test_contracts.py')['test_empty_analysis_is_explicitly_planned'](); print('Backend schema test: PASS')"
    if ($LASTEXITCODE -ne 0) { throw 'Backend schema test failed' }
} finally { Pop-Location }
& $env:HACKALEM_PYTHON -m pip check
& $env:HACKALEM_PYTHON scripts/local-ai/evaluate-meeting.py --help
git diff --check
```

Результат: **43/43 unit-теста**, отдельная проверка схемы backend, `pip check`,
CLI `--help` и `git diff --check` прошли. Новые 14 проверок используют только
синтетику и моки PDF/FFmpeg/LLM: Unicode, выравнивание/предел размера, пути вне Git,
манифест входов, сохранность файлов, HTML escaping/CSP, неоднозначные спикеры,
некорректные интервалы, приватные ошибки и ненулевой exit при неудачном анализе.
Эти тесты не требуют моделей, Ollama, FFmpeg или pypdf. Реальные длительности
повторно не измерялись; установки, драйверы и скачивания не выполнялись.

## Что подключить Medet

Передача готова к code review/слиянию как **диагностика и инструкции Local AI**,
а не как приёмка сквозного продукта. Изменять API ради этой передачи не требуется.

1. В конфигурации backend явно выбрать `LocalSTTService`, `LocalDiarizationService`
   и `LocalMeetingAnalysisService`, передать пути и параметры из этого handoff.
   Не подключать старые cloud/placeholder-пути и не делать автоматический fallback.
2. Декодировать вход в полный mono PCM16 WAV 16 kHz, сохранив исходник и временную
   шкалу; обработать ошибку/таймаут FFmpeg. В продукте предпочтительно подавать один
   и тот же нормализованный файл STT и diarization, отдельно проверив этот вариант:
   исторический STT полной записи был на MP3, diarization — на WAV.
3. Использовать одну общую очередь GPU, не несколько параллельных Uvicorn workers
   с независимыми моделями. Выполнять STT → diarization → LLM последовательно,
   освобождать веса; `release_after_call=True` и Ollama `keep_alive=0` уже поддержаны.
4. Реализовать production-совмещение timestamps. Диагностическая эвристика максимального
   перекрытия не решает надёжно одновременную речь/смену говорящего внутри STT-сегмента.
   Анонимные метки не равны именам; не заполнять `assigned_by` догадкой.
5. Для длинных встреч разработать разбиение по репликам/токенам, перенос только
   подтверждённых speaker identities и сведение поручений с неизменными источниками.
   У адаптера default: 6000 символов/context 4096; полный тест: 10000/8192. Лимит
   символов не гарантирует вместимость prompt + source enum + ответа в context.
   Превышение символьного лимита даёт ошибку; backend не должен молча отрезать текст.
6. Связать очередь, хранение, безопасные состояния/ошибки, результат и DOCX/PDF с
   `docs/api-contract.md`, проверить native EXE с реальным API. Ollama оставить на
   `127.0.0.1:11434`, LAN-клиенту отдавать только backend API, не AI-порты/токен.
7. Совместно с владельцем подтвердить текст, авторов, сроки и разметку говорящих;
   получить дословный RU/KK эталон, затем измерить WER/DER и сквозной offline-сценарий.
   До этого ограничения качества и неуверенную смысловую сверку показывать явно.

## Что требуется дальше

1. Владелец: прослушать локальный `results/audio-review.html` и подтвердить/исправить
   текст, границы и соответствие speaker ID людям; предоставить эталон для WER/DER.
   Присланный ранее в чат токен следует отозвать, пользоваться только новым локальным.
2. Local AI: после получения эталона измерить качество mixed ru/kk и diarization;
   при необходимости проверить другой 30–90-секундный фрагмент с подтверждённой смешанной речью.
3. Medet: подключить адаптеры и одну очередь, совместить timestamps, обработать длинные
   транскрипты/ограничения LLM, проверить экспорт и согласованный API. Не переносить
   старые Whisper small / Qwen2.5 / pyannote 3.x настройки из UI-ветки автоматически.
4. Координатор: объединение в main и обновление общего README после проверки.

## Официальные источники совместимости

- [faster-whisper: CUDA/cuDNN и загрузка](https://github.com/SYSTRAN/faster-whisper).
- [PyTorch CUDA wheels](https://pytorch.org/get-started/previous-versions/),
  [TorchCodec: совместимость PyTorch и FFmpeg](https://github.com/meta-pytorch/torchcodec).
- [pyannote.audio и telemetry](https://github.com/pyannote/pyannote-audio),
  [Community-1: gated-доступ и offline-загрузка](https://huggingface.co/pyannote/speaker-diarization-community-1).
- [FFmpeg: официальные ссылки на Windows-сборки](https://ffmpeg.org/download.html).
- [Ollama Windows](https://docs.ollama.com/windows),
  [local-only и cloud disable](https://docs.ollama.com/faq),
  [структурированный JSON](https://docs.ollama.com/capabilities/structured-outputs),
  [Qwen3 4B](https://ollama.com/library/qwen3:4b).
- [Python Windows](https://docs.python.org/3.11/using/windows.html).
