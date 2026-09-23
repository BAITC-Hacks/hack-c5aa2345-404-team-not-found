"""Create a private, local-file listening report; no server or external assets."""
import argparse
import html
import json
import math
import os
from pathlib import Path


def row(start, end, value):
    start, end = float(start), float(end)
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
        raise ValueError("Invalid interval")
    return (f'<tr><td><button onclick="playInterval({start},{end})">'
            f'{start:.2f}–{end:.2f} с</button></td><td>{html.escape(value)}</td></tr>')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--stt", type=Path, required=True)
    parser.add_argument("--diarization", type=Path, required=True)
    args = parser.parse_args()
    stt = json.loads(args.stt.read_text(encoding="utf-8"))
    diar = json.loads(args.diarization.read_text(encoding="utf-8"))
    text_rows = "".join(row(item["start"], item["end"], item["text"]) for item in stt["result"]["segments"])
    speaker_rows = "".join(row(item["start"], item["end"], item["speaker"]) for item in diar["speaker_segments"])
    page = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; media-src file:; connect-src 'none'">
<title>Локальная сверка записи — SAMRUK KAZYNA</title>
<style>body{font:17px system-ui;max-width:1000px;margin:32px auto;padding:0 20px;line-height:1.55}
table{border-collapse:collapse;width:100%}td{padding:10px;border-bottom:1px solid #ddd;vertical-align:top}
button{white-space:nowrap;cursor:pointer;padding:6px}audio{width:100%;position:sticky;top:0;background:white}
.notice{background:#fff4d5;padding:16px}</style>
<h1>Сверка аудио, текста и говорящих</h1>
<p class="notice">Это локальный диагностический отчёт, не готовый протокол. Качество ещё не подтверждено человеком.
Нажимайте интервалы, сверяйте слова, границы и постоянство меток говорящих.
Таблицы STT и diarization показаны отдельно: их объединение в продукте делает backend.
Не публикуйте этот файл: в нём содержится расшифровка записи.</p>
<audio id="audio" controls preload="metadata" src="AUDIO_URI"></audio>
<h2>Распознанный текст</h2><table>TEXT_ROWS</table>
<h2>Границы говорящих</h2><p>SPEAKER_XX — анонимная метка, не имя.</p><table>SPEAKER_ROWS</table>
<h2>Что проверить</h2><ol><li>Пропущенные/выдуманные слова, русский/казахский и технические термины.</li>
<li>Начало и конец фразы относительно аудио.</li><li>Один человек сохраняет метку при возвращении к речи;
разные люди не объединены в одну метку.</li><li>Перекрывающуюся речь проверяйте отдельно.</li></ol>
<p>Для измерений WER/DER нужен размеченный эталон; число сегментов само по себе не показатель точности.</p>
<script>const player=document.getElementById('audio');let stopAt=null;
function playInterval(start,end){stopAt=end;player.currentTime=start;player.play().catch(()=>{});}
player.addEventListener('timeupdate',()=>{if(stopAt!==null&&player.currentTime>=stopAt){player.pause();stopAt=null;}});
player.addEventListener('seeking',()=>{if(stopAt!==null&&player.currentTime>stopAt)stopAt=null;});</script></html>'''
    page = page.replace("AUDIO_URI", html.escape(args.audio.resolve().as_uri(), quote=True)).replace("TEXT_ROWS", text_rows).replace("SPEAKER_ROWS", speaker_rows)
    root = Path(os.environ.get("HACKALEM_AI_HOME", str(Path(os.environ["LOCALAPPDATA"]) / "HackAlemAI")))
    output = root / "results" / "audio-review.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"Private report saved locally: {output}")  # Never print transcript content.
