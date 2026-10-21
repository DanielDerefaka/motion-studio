"""The voiceover: one WAV per timeline VO clip from Kokoro (kokoro-onnx, Apache 2.0,
local), plus their lengths for the timeline. Writes cache/vo/<voice>/<id>.wav
and cache/vo/<voice>/lines.json.

cache/tts-venv/bin/python -I src/voice.py [voice] [speed]
"""
import json
import os
import sys

import soundfile as sf
from kokoro_onnx import Kokoro

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDIO, 'src'))
import timeline as T  # noqa: E402

voice = sys.argv[1] if len(sys.argv) > 1 else T.VOICE
speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.1
k = Kokoro(os.path.join(STUDIO, 'cache', 'tts', 'kokoro-v1.0.onnx'), os.path.join(STUDIO, 'cache', 'tts', 'voices-v1.0.bin'))
out = os.path.join(STUDIO, 'cache', 'vo', voice)
os.makedirs(out, exist_ok=True)
meta = []
for i, line in enumerate(T.VO):
    text = line['text']
    s, sr = k.create(line.get('say', text), voice=voice, speed=speed, lang='en-gb' if voice[0] == 'b' else 'en-us')
    # Trim the model's leading and trailing silence.
    loud = [j for j, v in enumerate(s) if abs(v) > 0.01]
    s = s[max(0, loud[0] - 240):loud[-1] + 2400]
    path = os.path.join(out, f"{line['id']}.wav")
    sf.write(path, s, sr)
    meta.append(dict(id=line['id'], text=text, secs=round(len(s) / sr, 3), file=os.path.relpath(path, STUDIO)))
    print(f'{i} {len(s) / sr:5.2f}s {text}')
json.dump(dict(voice=voice, speed=speed, sr=sr, lines=meta), open(os.path.join(out, 'lines.json'), 'w'), indent=1)
print('total', round(sum(m['secs'] for m in meta), 2))
