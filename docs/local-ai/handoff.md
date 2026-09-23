# Local AI — передача Medet

Проверено 23.09.2026 на компьютере Amankos. Ветка `codex/local-ai-setup`.
Исходная инструкция команды — `68f332b`; повторный fetch обнаружил `fbdd8c6`
(SAMRUK KAZYNA, Windows EXE). Контракты AI не изменились. Эта работа не создаёт
backend/API или клиент: подключение адаптеров выполняет Medet.

## Готовность и ограничения

- Установлены Python AI-окружение, FFmpeg shared, Ollama; скачаны Whisper large-v3 и Qwen3:4b.
- CUDA-вычисления, декодирование WAV и реальный encoder Whisper проверены.
- Три адаптера реализуют существующие `base.py`; импорт/конструкторы не загружают модели.
- 14 автономных unit-тестов пройдены; зависимости проходят `pip check`.
- Qwen возвращает JSON по контракту, но строгая проверка смысла прошла **6/7**:
  у поручения проверить PDF пропущен `assigned_by`, хотя говорящий представился.
  Это **не полностью успешная проверка LLM**. Нужны проверка человеком и дальнейшая оценка качества.
- Community-1: библиотека установлена, условия приняты владельцем, но **веса пока не скачаны**:
  требуется локальная авторизация Hugging Face. Загрузка pipeline и diarization ещё не проверены.
- Согласованная запись не предоставлена. Реальные STT/timestamps, speaker segments,
  качество mixed ru/kk и сквозной сценарий пока **не проверены**.

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
| pyannote/speaker-diarization-community-1 | `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` | целевая ревизия, ожидается доступ |

```text
C:\Users\Amankos\Downloads\Hakaton\.venv\Scripts\python.exe
%LOCALAPPDATA%\HackAlemAI\
  tools\ollama\ollama.exe
  tools\ffmpeg-n8.1-latest-win64-gpl-shared-8.1\bin\
  models\faster-whisper-large-v3\
  models\ollama\
  models\speaker-diarization-community-1\   (после загрузки)
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
# Проверять $LASTEXITCODE после КАЖДОЙ команды; llm сейчас возвращает 1 (6/7).
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

### Завершение Community-1

Владелец уже сообщил о принятии условий на
[странице модели](https://huggingface.co/pyannote/speaker-diarization-community-1).
Нужен [HF Read token](https://huggingface.co/settings/tokens) с доступом к этой gated-модели.
Ввод только в собственном интерактивном терминале, символы скрываются:

```powershell
& $env:HACKALEM_PYTHON scripts/local-ai/hf-login.py
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py download-pyannote
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py load-pyannote
```

Скачивание явно отделено от offline-проверок; ревизии по умолчанию зафиксированы.
При повторном запуске Hugging Face использует локальный кеш/прогресс скачивания.

### Когда будет тестовая запись

Нужны 30–90 секунд, два согласившихся говорящих, русский, казахский и смешанная
речь, без чувствительных сведений. Сохранить вне Git и запустить последовательно:

```powershell
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py stt-audio --audio "$env:HACKALEM_AI_HOME\audio\test.wav"
& $env:HACKALEM_PYTHON scripts/local-ai/check-local-ai.py diarize-audio --audio "$env:HACKALEM_AI_HOME\audio\test.wav" --num-speakers 2
```

Полученные JSON сохраняются в `results/adapter-*.json`, содержимое записи не печатается
в консоль. Сверить текст, интервалы и говорящих с записью вручную; успешное исполнение
не является автоматической оценкой качества. Объединение STT и diarization — задача backend.

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
  Проверяются точные цитаты соответствующей реплики и присутствие имён/сроков в тексте.
  Это не доказывает правильность назначения каждого поручения.
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
| Unit-тесты адаптеров | 14/14; моки, не качество моделей |
| `pip check` | нет конфликтов |
| Runtime | PyTorch CUDA matmul; CT2 `int8_float16`; импорт pyannote; TorchCodec декодирует синтетический WAV |
| Whisper через адаптер | загрузка 6.27 с, encoder `[1,1500,1280]`; синтетические нули, не речь |
| Память при encoder | Python RSS 885.4 MiB; nvidia-smi 2031 MiB всего на GPU, снимок, **не пик** и не только модель |
| Qwen через адаптер | 8.94 с; JSON/цитаты валидны, 3 поручения; строгий смысловой тест 6/7, exit 1 |
| Ollama GPU | 37/37 слоёв; оценка журнала 3030 MiB (веса 2375 + context 576 + compute 79), не измеренный пик |
| Loopback | listener `127.0.0.1:11434`; cloud disabled подтверждён в журнале |
| Community-1 / реальная речь | не проверены, блокеры выше |

Ранний LLM-тест записал фразу «Мерзімі айтылған жоқ» в deadline. После уточнения
правил вернул null, но пропуск автора PDF сохранился. Ранний standalone-тест также
имел пропуск автора; thinking с бюджетом 3000 токенов исчерпал лимит до JSON, поэтому
thinking не включён. Эти неудачи не подменялись успешными демоответами.

Диагностические процессы блокируют внешние Python socket-соединения и включают
HF offline; разрешён loopback. Ollama отдельно запущен с `OLLAMA_NO_CLOUD=1`.
Адаптеры не скачивают веса автоматически; STT использует `local_files_only=True`,
pyannote — локальный config и HF offline, LLM запрещает внешние URL, proxy-env,
redirects и remote-модели. Это не системный firewall: полный offline e2e ещё не проверен.

Драйвер 591.86 был установлен **до** просьбы владельца не устанавливать драйвер:
обычный NVIDIA installer завершился ошибкой, ранее настройка была завершена через
подходящие подписанные INF и PnPUtil. После запрета никаких действий с драйвером
не выполняется. Нужные CUDA/cuDNN DLL предоставлены wheel PyTorch, не отдельным Toolkit.

## Что требуется дальше

1. Владелец: скрытый локальный HF login и согласованная тестовая запись.
2. Local AI: загрузить Community-1, проверить offline pipeline и реальные STT/diarization;
   измерить качество и время на записи, повторить анализ реального транскрипта.
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
