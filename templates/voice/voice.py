"""The voiceover: one WAV per timeline VO line from Kokoro (kokoro-onnx, Apache
2.0, runs locally), plus their lengths for the timeline.

    cache/tts-venv/bin/python -I src/voice.py [voice] [speed]       # every T.VO line
    cache/tts-venv/bin/python -I src/voice.py --samples "A line."   # one line in ~8 voices
    cache/tts-venv/bin/python -I src/voice.py --list                # every voice in the model

Then run python3 src/timeline.py again, so the captions and the sound get the
real line lengths. -I keeps a stray bisect.py (or any stdlib name) in the
working directory from shadowing the standard library.

Writes cache/vo/<voice>/<id>.wav (the model's 24 kHz, silence trimmed) and
cache/vo/<voice>/lines.json {voice, speed, sr, lines: [{id, text, secs, file}]};
--samples writes out/voice-samples/<voice>.wav. Each line reads `say` when the
timeline gives one (the spelling the voice gets right), else `text`.
Models: cache/tts/kokoro-v1.0.onnx and cache/tts/voices-v1.0.bin (setup-tts.sh).
"""
import json
import os
import sys

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(STUDIO, 'src'))

TTS = os.path.join(STUDIO, 'cache', 'tts')
MODEL, VOICES = os.path.join(TTS, 'kokoro-v1.0.onnx'), os.path.join(TTS, 'voices-v1.0.bin')
RELEASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
SAMPLE_VOICES = ['af_heart', 'af_bella', 'af_nicole', 'am_michael', 'am_fenrir', 'bf_emma', 'bm_george', 'bm_fable']
# Kokoro voice prefix -> espeak language: a American, b British, then es, fr, hi, it, ja, pt, zh.
LANG = dict(a='en-us', b='en-gb', e='es', f='fr-fr', h='hi', i='it', j='ja', p='pt-br', z='cmn')

missing = [p for p in (MODEL, VOICES) if not os.path.exists(p)]
if missing:
    sys.exit('voice.py: missing ' + ', '.join(os.path.relpath(p, STUDIO) for p in missing) + '\n'
             f'  run templates/voice/setup-tts.sh <studio>, or download into {TTS}/:\n'
             f'    {RELEASE}kokoro-v1.0.onnx   (~325 MB)\n'
             f'    {RELEASE}voices-v1.0.bin    (~28 MB)')
try:
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
except ImportError as err:
    sys.exit(f'voice.py: {err}. Use the TTS venv: cache/tts-venv/bin/python -I src/voice.py '
             '(templates/voice/setup-tts.sh makes it)')

k = Kokoro(MODEL, VOICES)
AVAILABLE = set(k.get_voices())


def say(text, voice, speed):
    """Synthesise one line and trim the model's leading and trailing silence
    (10 ms kept before the first sound, 100 ms after the last)."""
    s, sr = k.create(text, voice=voice, speed=speed, lang=LANG.get(voice[0], 'en-us'))
    s = np.asarray(s, dtype=np.float32)
    loud = np.flatnonzero(np.abs(s) > 0.01)
    if len(loud):
        s = s[max(0, loud[0] - sr // 100):loud[-1] + sr // 10]
    return s, sr


def check(voice):
    if voice not in AVAILABLE:
        sys.exit(f'voice.py: no voice {voice!r} in voices-v1.0.bin. Try: {", ".join(sorted(AVAILABLE))}')


args = sys.argv[1:]
if args[:1] == ['--list']:
    print(' '.join(sorted(AVAILABLE)))
    sys.exit()

if args[:1] == ['--samples']:
    line = args[1] if len(args) > 1 else 'This is how the film will sound, line by line.'
    speed = float(args[2]) if len(args) > 2 else 1.0
    out = os.path.join(STUDIO, 'out', 'voice-samples')
    os.makedirs(out, exist_ok=True)
    voices = [v for v in SAMPLE_VOICES if v in AVAILABLE]
    skipped = [v for v in SAMPLE_VOICES if v not in AVAILABLE]
    for v in voices:
        s, sr = say(line, v, speed)
        sf.write(os.path.join(out, f'{v}.wav'), s, sr)
        print(f'{v:11} {len(s) / sr:5.2f}s  {os.path.relpath(os.path.join(out, v + ".wav"), STUDIO)}')
    if skipped:
        print('not in this voices file:', ', '.join(skipped))
    print(f'"{line}" at speed {speed}. Pick one: set VOICE in src/timeline.py, then run src/voice.py')
    sys.exit()

import timeline as T  # noqa: E402

voice = args[0] if args else T.VOICE
speed = float(args[1]) if len(args) > 1 else getattr(T, 'VOICE_SPEED', 1.0)
check(voice)
if voice != T.VOICE:
    print(f'note: rendering {voice}, but the timeline reads cache/vo/{T.VOICE}/ (set VOICE in src/timeline.py)')
out = os.path.join(STUDIO, 'cache', 'vo', voice)
os.makedirs(out, exist_ok=True)
meta, sr = [], 24000
for i, line in enumerate(T.VO):
    s, sr = say(line.get('say') or line['text'], voice, speed)
    path = os.path.join(out, f"{line['id']}.wav")
    sf.write(path, s, sr)
    meta.append(dict(id=line['id'], text=line['text'], secs=round(len(s) / sr, 3), file=os.path.relpath(path, STUDIO)))
    print(f"{i:2} {line['id']:12} {len(s) / sr:5.2f}s  {line['text']}")
json.dump(dict(voice=voice, speed=speed, sr=sr, lines=meta), open(os.path.join(out, 'lines.json'), 'w'), indent=1)
print(f'{len(meta)} lines, {sum(m["secs"] for m in meta):.2f} s -> {os.path.relpath(out, STUDIO)}/  '
      '(now run python3 src/timeline.py again)')
