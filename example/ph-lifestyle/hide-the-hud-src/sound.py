"""The sound: a lo-fi afrobeat groove at the timeline's tempo and every event
in timeline.json as a synthesised effect, all from code. Deterministic.

Run with the studio venv: cache/venv/bin/python src/sound.py
Writes out/sound.wav (48 kHz stereo, peaks under -1 dBFS) and prints the
loudness of every half second.
"""
import json
import os
import wave

import numpy as np
from scipy import signal

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(STUDIO, 'src', 'timeline.json')))
SR = 48000
FPS, BEAT_F = T['FPS'], T['BEAT']
BEAT = BEAT_F / FPS                 # 0.6 s
STEP = BEAT / 4                     # a sixteenth
DUR = T['FRAMES'] / FPS
N = int(round(DUR * SR))
rng = np.random.default_rng(404)


def t_of(frame):
    return (frame - 1) / FPS


def beat_t(b):
    return b * BEAT


def at_beat(name):
    return next(e['f'] for e in T['EVENTS'] if e['kind'] == name)


# ------------------------------------------------------------- building ---

def env(n, a=0.002, d=0.2, curve=1.0):
    """Attack then exponential decay, n samples."""
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-5), 0, 1)
    return att * np.exp(-t / max(d, 1e-5)) ** curve


def noise(n):
    return rng.standard_normal(n)


def band(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lowpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'lowpass', fs=SR, output='sos'), x)


def highpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x)


def sine_sweep(f0, f1, n, tau=0.05):
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


class Bus:
    def __init__(self):
        self.l = np.zeros(N + SR)
        self.r = np.zeros(N + SR)

    def add(self, x, t, gain=1.0, pan=0.0):
        i = int(round(t * SR))
        if i >= N or i + len(x) <= 0:
            return
        if i < 0:
            x, i = x[-i:], 0
        x = x[: len(self.l) - i]
        a = (pan + 1) * np.pi / 4
        self.l[i:i + len(x)] += x * gain * np.cos(a)
        self.r[i:i + len(x)] += x * gain * np.sin(a)

    def stereo(self):
        return np.stack([self.l[:N], self.r[:N]])


music, sfx = Bus(), Bus()

# ---------------------------------------------------------------- music ---

def kick():
    n = int(0.45 * SR)
    x = sine_sweep(150, 46, n, 0.035) * env(n, 0.001, 0.22)
    x += band(noise(n), 1500, 6000) * env(n, 0.0005, 0.006) * 0.4
    return np.tanh(x * 1.6)


def clap():
    n = int(0.3 * SR)
    e = np.zeros(n)
    for k, off in enumerate((0, 0.009, 0.019)):
        i = int(off * SR)
        e[i:] += env(n - i, 0.0005, 0.012 if k < 2 else 0.11)
    return band(noise(n), 900, 5200) * e


def shaker(accent):
    n = int(0.06 * SR)
    return highpass(noise(n), 6000) * env(n, 0.004, 0.018) * (1.0 if accent else 0.55)


def rim():
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 820 * t) * 0.6 + band(noise(n), 1800, 4000) * 0.4) * env(n, 0.0005, 0.018)


def log_drum(hz):
    """The amapiano/afro log drum: a sine that slides down into its note."""
    n = int(0.42 * SR)
    x = sine_sweep(hz * 1.9, hz, n, 0.018) * env(n, 0.002, 0.16)
    return np.tanh(x * 2.2) * 0.8


def pluck(hz, dur=0.5, bright=0.5):
    """Karplus-Strong: the highlife guitar."""
    n = int(dur * SR)
    p = max(2, int(SR / hz))
    buf = noise(p) * 0.5
    buf = lowpass(buf, 2000 + 5000 * bright, 1)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out * env(n, 0.001, dur * 0.6)


def pad(midis, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for det in (-0.07, 0.0, 0.07):
            ph = 2 * np.pi * note_hz(m + det) * t
            x += signal.sawtooth(ph) * 0.25
    x = lowpass(x, 1400)
    a = np.clip(t / 0.25, 0, 1) * np.clip((dur - t) / 0.3, 0, 1)
    return x * a / len(midis)


def talking_drum(t0):
    """A pitch-bent tom phrase, for the dance."""
    for k, (off, f0, f1) in enumerate(((0, 180, 260), (STEP * 1.5, 260, 150), (STEP * 3, 200, 300))):
        n = int(0.25 * SR)
        tt = np.arange(n) / SR
        f = f0 + (f1 - f0) * np.clip(tt / 0.12, 0, 1)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.09)
        music.add(x, t0 + off, 0.5, 0.25)


# A minor afro-pop loop: Am, F, C, G, one chord a bar.
CHORDS = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]
KICK = (0, 6, 8, 14)
CLAP = (4, 12)
RIM = (3, 7, 11, 15)
BASS = ((0, 0), (3, 7), (6, 12), (10, 0), (13, 7))
GUITAR = (2, 5, 7, 9, 13, 15)
drop_b = (at_beat('pop') - 1) / BEAT_F           # 4
off_b = (at_beat('hud-off') - 1) / BEAT_F         # 20.5
dance_b = (at_beat('dance') - 1) / BEAT_F         # 22
SK, SC, SR_, SSH = kick(), clap(), rim(), None

for bar in range(T['BEATS'] // 4):
    b0 = bar * 4
    root, chord = CHORDS[bar % 4]
    music.add(pad(chord + [chord[0] + 12], 4 * BEAT + 0.3), beat_t(b0), 0.22 if b0 >= drop_b else 0.14)
    for s in range(16):
        b = b0 + s / 4
        t = beat_t(b)
        full = drop_b <= b < off_b or b >= dance_b
        if b < drop_b:
            # Before the pop: only a muffled shaker under the knocks.
            if s % 2 == 1:
                music.add(lowpass(shaker(s % 4 == 2), 2500), t, 0.25, -0.2)
            continue
        if not full:
            # Hide: the drums drop out; a low filtered log drum keeps time.
            if s in (0, 8):
                music.add(lowpass(log_drum(note_hz(root - 12)), 400), t, 0.45)
            continue
        if s in KICK:
            music.add(SK, t, 0.85)
        if s in CLAP:
            music.add(SC, t, 0.45, 0.1)
        if s in RIM:
            music.add(SR_, t, 0.22, -0.35)
        music.add(shaker(s % 2 == 1), t, 0.16, 0.4)
        for step, iv in BASS:
            if s == step:
                music.add(log_drum(note_hz(root - 12 + iv)), t, 0.55)
        if s in GUITAR:
            tone = chord[(s * 7 + bar) % 3] + 12 + (12 if s in (9, 15) else 0)
            music.add(pluck(note_hz(tone), 0.45, 0.6), t, 0.28, 0.3 if s % 2 else -0.3)
    if b0 + 4 > dance_b and b0 <= dance_b + 4:
        talking_drum(beat_t(max(b0, dance_b) + 2))

# The drop: a reversed cymbal into the pop.
n = int(1.2 * SR)
swell = highpass(noise(n), 5000) * np.linspace(0, 1, n) ** 3
music.add(swell, t_of(at_beat('pop')) - 1.2, 0.35)

# --------------------------------------------------------------- effects ---

def knock():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    body = lowpass(noise(n), 900) * env(n, 0.0008, 0.02) * 1.5
    ring = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((2300, 0.3), (3720, 0.2), (5150, 0.1))) * env(n, 0.001, 0.07)
    return body + ring


def peel():
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    x = noise(n)
    crackle = (rng.random(n) < 0.012) * rng.standard_normal(n) * 3
    sweep = np.zeros(n)
    for i in range(0, n, 1024):
        f = 800 + 5000 * (i / n)
        sweep[i:i + 1024] = band(x[i:i + 1024], f, f * 1.8, 1)
    return (sweep + highpass(crackle, 2000)) * np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.35) * 0.9


def shatter():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    out = lowpass(noise(n), 200) * env(n, 0.001, 0.12) * 2.5          # the stomp
    out += sine_sweep(90, 40, n, 0.08) * env(n, 0.001, 0.25) * 1.2
    out += highpass(noise(n), 3000) * env(n, 0.0005, 0.09) * 1.0      # the crack
    for _ in range(70):                                                # the pieces
        i = int(rng.uniform(0, 0.9) ** 1.8 * SR)
        f = rng.uniform(2500, 9000)
        m = int(0.12 * SR)
        tt = np.arange(m) / SR
        tink = np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.01, 0.04)) * rng.uniform(0.05, 0.25)
        out[i:i + m] += tink[: n - i]
    return out


def whoosh(dur=0.5, up=True, lo=400, hi=3000):
    n = int(dur * SR)
    x = noise(n)
    out = np.zeros(n)
    k = 1024
    for i in range(0, n, k):
        p = i / n
        c = lo + (hi - lo) * (p if up else 1 - p)
        out[i:i + k] = band(x[i:i + k], c * 0.7, c * 1.4, 1)
    tt = np.arange(n) / SR
    return out * np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.5


def land(z):
    n = int(0.3 * SR)
    lo = {'world': 70, 'hud': 110, 'phone': 150, 'bus': 85}.get(z, 110)
    x = sine_sweep(lo * 2, lo, n, 0.02) * env(n, 0.001, 0.07)
    x += band(noise(n), 1500, 5000) * env(n, 0.0005, 0.008) * 0.6
    return np.tanh(x * 1.5)


def click():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    a = np.sin(2 * np.pi * 1900 * t) * env(n, 0.0003, 0.008)
    b = np.sin(2 * np.pi * 1300 * t) * env(n, 0.0003, 0.03)
    b = np.concatenate([np.zeros(int(0.035 * SR)), b])[:n]
    return a * 0.8 + b * 0.6


def ding(midi):
    """An FM bell: a need filling."""
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    f = note_hz(midi)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t / 0.15)
    return np.sin(2 * np.pi * f * t + mod) * env(n, 0.002, 0.35)


def horn():
    """The danfo's two short honks."""
    out = np.zeros(int(0.7 * SR))
    for off in (0.0, 0.26):
        n = int(0.18 * SR)
        t = np.arange(n) / SR
        x = signal.square(2 * np.pi * 415 * t) * 0.5 + signal.square(2 * np.pi * 523 * t) * 0.5
        x = lowpass(x, 2200) * np.clip(t / 0.01, 0, 1) * np.clip((0.18 - t) / 0.02, 0, 1)
        i = int(off * SR)
        out[i:i + n] += x
    return out


def engine(dur, rev):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 38 + 22 * (t / dur if rev else np.sin(np.pi * t / dur))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = signal.sawtooth(ph) + 0.5 * signal.sawtooth(ph * 2.02)
    x = lowpass(x, 500) + lowpass(noise(n), 300) * 0.6
    return x * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7


def clang():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((310, 0.5), (742, 0.35), (1290, 0.2), (2010, 0.1)))
    x = x * env(n, 0.001, 0.14)
    th = land('bus')
    x[:len(th)] += th * 0.6
    return x


def note_flick():
    n = int(0.09 * SR)
    return band(noise(n), 1500, 7000) * env(n, 0.001, 0.02)


def power_down():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 1600 * np.exp(-t / 0.08) + 90
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.12)
    return x + highpass(noise(n), 4000) * env(n, 0.0005, 0.01) * 0.3


def shimmer(midis):
    n = int(2.4 * SR)
    out = np.zeros(n)
    for k, m in enumerate(midis):
        d = ding(m)
        i = int(k * 0.06 * SR)
        out[i:i + len(d)] += d[: n - i]
    return out


def pan_of(x_px):
    return float(np.clip((x_px - 960) / 960, -1, 1)) * 0.6


hop_by_t1 = {h['t1']: h for h in T['HOPS']}
hop_by_t0 = {h['t0']: h for h in T['HOPS']}
NEED_NOTES = [72, 76, 79, 84]           # C E G C: each need a step up
for e in T['EVENTS']:
    k, t = e['kind'], t_of(e['f'])
    if k == 'knock':
        sfx.add(knock(), t, 0.9)
    elif k == 'peel':
        sfx.add(peel(), t, 0.55)
    elif k == 'pop':
        sfx.add(shatter(), t, 0.85)
    elif k == 'takeoff':
        h = hop_by_t0[e['f']]
        dur = (h['t1'] - h['t0']) / FPS
        sfx.add(whoosh(min(0.6, dur + 0.1), True, 500, 2500), t, 0.22 + 0.06 * h['apex'],
                pan_of(h['to'][0]) if isinstance(h['to'], list) else 0)
    elif k == 'land':
        h = hop_by_t1[e['f']]
        sfx.add(land(e['z']), t, 0.7, pan_of(h['to'][0]) if isinstance(h['to'], list) else 0)
    elif k == 'need-fill':
        sfx.add(ding(NEED_NOTES[e['note']]), t + 0.03, 0.32, -0.45)
    elif k == 'press':
        sfx.add(click(), t, 0.55)
    elif k == 'bus-arrive':
        sfx.add(engine(5.4, False), t - 0.8, 0.5, -0.2)
        sfx.add(horn(), t + 0.2, 0.32, -0.4)
    elif k == 'land-bus':
        sfx.add(clang(), t, 0.45, -0.5)
    elif k == 'bus-leave':
        sfx.add(engine(1.4, True), t, 0.35, 0.6)
        sfx.add(horn(), t + 0.15, 0.22, 0.7)
    elif k == 'kick-spray':
        for i in range(e['notes']):
            sfx.add(note_flick(), t + i * 2 / FPS, 0.5, 0.3 + 0.03 * i)
    elif k == 'whoosh':
        sfx.add(whoosh(1.0, True, 300, 4500), t, 0.5)
    elif k == 'phone-rise':
        sfx.add(whoosh(0.45, True, 1200, 6000), t, 0.25, 0.1)
        sfx.add(ding(88), t + 0.25, 0.12, 0.1)
    elif k == 'hud-off':
        for i, delay in enumerate((0.0, 0.07, 0.13, 0.2, 0.28, 0.36, 0.45)):
            sfx.add(power_down(), t + delay, 0.28 * (1 - i * 0.08), (-1) ** i * 0.15 * i)
    elif k == 'land-world':
        sfx.add(land('world'), t, 1.0)
    elif k == 'dance':
        sfx.add(whoosh(0.4, False, 800, 3000), t - 0.05, 0.2)
    elif k == 'endcard':
        sfx.add(shimmer([69, 72, 76, 81, 84]), t, 0.22)

# ------------------------------------------------------------------ mix ---

def compress(x, thresh_db=-18, ratio=3.0, attack=0.005, release=0.12, makeup_db=4):
    mono = np.max(np.abs(x), axis=0)
    a_a, a_r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    lvl = signal.lfilter([1 - a_r], [1, -a_r], mono)        # a smooth level, then gain
    lvl_db = 20 * np.log10(np.maximum(lvl, 1e-6))
    over = np.maximum(lvl_db - thresh_db, 0)
    gain_db = -over * (1 - 1 / ratio) + makeup_db
    g = 10 ** (gain_db / 20)
    g = signal.lfilter([1 - a_a], [1, -a_a], g)
    return x * g


def limit(x, ceiling_db=-1.0, look=0.004):
    ceil = 10 ** (ceiling_db / 20)
    la = int(look * SR)
    peak = np.max(np.abs(x), axis=0)
    # The gain each sample needs, held over the lookahead and smoothed.
    need = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))
    held = -signal.convolve(np.pad(-need, (la, 0), mode='edge'), np.ones(1), 'same')[la:]
    from scipy.ndimage import minimum_filter1d
    held = minimum_filter1d(need, size=2 * la + 1)
    rel = np.exp(-1 / (0.05 * SR))
    g = np.empty_like(held)
    cur = 1.0
    for i in range(len(held)):
        cur = held[i] if held[i] < cur else held[i] + (cur - held[i]) * rel
        g[i] = cur
    y = x * g
    return np.clip(y, -ceil, ceil)


mix = compress(music.stereo(), -16, 2.5, 0.01, 0.2, 2) * 0.9 + sfx.stereo() * 1.0
# Fade from the fade event to the end.
fade_t = t_of(at_beat('fade'))
tt = np.arange(N) / SR
mix *= np.clip(1 - (tt - fade_t) / (DUR - fade_t), 0, 1) ** 1.5
mix = compress(mix, -14, 2.0, 0.003, 0.1, 3)
mix /= max(1e-6, np.max(np.abs(mix))) / 0.98
mix = limit(mix * 1.15, -1.0)

out_dir = os.path.join(STUDIO, 'out')
os.makedirs(out_dir, exist_ok=True)
path = os.path.join(out_dir, 'sound.wav')
pcm = (np.clip(mix, -1, 1) * 32767).astype('<i2').T.copy()
with wave.open(path, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

peak = 20 * np.log10(np.max(np.abs(mix)))
print(f'{path}  {DUR:.1f} s  peak {peak:.2f} dBFS')
half = SR // 2
for i in range(0, N, half):
    seg = mix[:, i:i + half]
    rms = 20 * np.log10(max(1e-9, np.sqrt(np.mean(seg ** 2))))
    print(f'{i / SR:5.1f}s  {rms:6.1f} dB  ' + '#' * max(0, int((rms + 40) / 1.5)))
