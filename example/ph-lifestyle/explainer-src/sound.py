"""The sound of the explainer: the first film's lo-fi afrobeat palette (kick,
clap, shaker, log drum, highlife plucks, pads, talking drum and a synthesised
effect for every timeline event), re-arranged around the voiceover, then the
voice itself mixed on top with the bed ducked under it. All from code.
Deterministic.

Run with the studio venv: cache/venv/bin/python src/sound.py
Writes
  out/explainer/sound.wav        the final mix, 48 kHz stereo 24-bit, exactly FRAMES/FPS long
  out/explainer/music.wav        the same bed without the voice and without ducking (voice swaps)
  out/explainer/sound-notes.txt  levels and the voice-over-bed ratio of every line
  reviews/sound-explainer.png    spectrogram + levels, VO lines and sections marked

Every position comes from src/timeline.json (events, hops, VO lines, camera
keys), written by src/timeline.py: change the timeline, regenerate the json,
run this again, and the sound re-times. The first film's
version of this file is archived in src-hide-the-hud/sound.py.
"""
import json
import math
import os
import sys
import wave
from types import SimpleNamespace

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d, minimum_filter1d

SRC = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(SRC)
sys.dont_write_bytecode = True
sys.path.insert(0, SRC)
import timeline  # noqa: E402

# Every frame (events, hops, VO lines, camera keys) comes from timeline.json;
# the module gives the beat -> frame helper. Run `python3 src/timeline.py` first.
T = SimpleNamespace(**json.load(open(os.path.join(SRC, 'timeline.json'))), f=timeline.f)
if [(e['f'], e['kind']) for e in timeline.EVENTS] != [(e['f'], e['kind']) for e in T.EVENTS]:
    print('warning: src/timeline.json is older than src/timeline.py; using the json (run python3 src/timeline.py)')

SR = 48000
FPS, BEAT_F = T.FPS, T.BEAT
BEAT = BEAT_F / FPS                 # 0.6 s
STEP = BEAT / 4                     # a sixteenth
DUR = T.FRAMES / FPS                # 30.0 s
N = int(round(DUR * SR))
rng = np.random.default_rng(404)

DUCK_DB = -9.0                      # music + effects under the voice
MID_DIP_DB = -3.0                   # and a little more out of 1-5 kHz, where the words live
TARGET_LUFS = -14.0
CEILING_DBTP = -1.0


def t_of(frame):
    return (frame - 1) / FPS


def b_of(frame):
    return (frame - 1) / BEAT_F


def beat_t(b):
    return b * BEAT


def ev(kind, **match):
    """The frame of the first event of a kind (and matching fields)."""
    return next(e['f'] for e in T.EVENTS if e['kind'] == kind and all(e.get(k) == v for k, v in match.items()))


# ------------------------------------------------------- the sections ---
# All from the timeline, in beats.
DROP_B = b_of(ev('pop'))                            # 4: glass shatters, the beat drops
GROW_B = b_of(ev('hud-grow'))                       # 4.3: stay alive
_drain = next(e for e in T.EVENTS if e['kind'] == 'needs-drain')
DRAIN_B0, DRAIN_B1 = b_of(_drain['f']), b_of(_drain['f1'])   # 7.6 - 10.3
FILL_BS = [b_of(e['f']) for e in T.EVENTS if e['kind'] == 'need-fill']   # 11, 12, 13, 14
BUS_B = b_of(ev('bus-arrive'))                      # 14.8: the danfo
MONEY_B = b_of(ev('press', target='dock-jobs'))     # 20: make money
SPEND_B = b_of(ev('whoosh'))                        # 23.05: spend it
PEOPLE_B = b_of(T.CHAPTERS[3]['f_in'])              # 29.8: real people
HIDE_B = b_of(ev('press', target='btn-hide'))       # 38
OFF_B = b_of(ev('hud-off'))                         # 38.5: the HUD powers down, drums out
DANCE_B = b_of(ev('dance'))                         # 41: the groove comes back
END_B = b_of(ev('endcard'))                         # 43
FADE_B = b_of(ev('fade'))                           # 48.6 to the end
SECTIONS = [(0, 'hook'), (GROW_B, 'stay alive'), (BUS_B, 'danfo'), (MONEY_B, 'make money'),
            (SPEND_B, 'spend it'), (PEOPLE_B, 'real people'), (HIDE_B, 'hide'), (DANCE_B, 'dance'),
            (END_B, 'end card'), (FADE_B, 'fade')]

# Where the voice speaks (seconds), from the VO lines; arrangement choices read this.
VO_SPANS = [(t_of(v['f']), t_of(v['f_end'])) for v in T.VO]


def speaking(t0, t1=None, pre=0.08, post=0.1):
    """Does [t0, t1] touch a VO line (with a little margin)?"""
    t1 = t0 if t1 is None else t1
    return any(t1 >= a - pre and t0 <= b + post for a, b in VO_SPANS)


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
        self.l = np.zeros(N + 4 * SR)
        self.r = np.zeros(N + 4 * SR)

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


# music_a: everything that starts before the HUD powers down (it tape-stops
# there); music_b: everything from then on; sfx: the events.
music_a, music_b, sfx = Bus(), Bus(), Bus()
OFF_T = beat_t(OFF_B)


def M(x, t, gain=1.0, pan=0.0):
    (music_a if t < OFF_T else music_b).add(x, t, gain, pan)


# ---------------------------------------------------------------- music ---
# The first film's instruments, unchanged.

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


def pad(midis, dur, cutoff=1400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for det in (-0.07, 0.0, 0.07):
            ph = 2 * np.pi * note_hz(m + det) * t
            x += signal.sawtooth(ph) * 0.25
    x = lowpass(x, cutoff)
    a = np.clip(t / 0.25, 0, 1) * np.clip((dur - t) / 0.3, 0, 1)
    return x * a / len(midis)


def talking_drum(t0, gain=0.5):
    """A pitch-bent tom phrase, for the dance."""
    for off, f0, f1 in ((0, 180, 260), (STEP * 1.5, 260, 150), (STEP * 3, 200, 300)):
        n = int(0.25 * SR)
        tt = np.arange(n) / SR
        f = f0 + (f1 - f0) * np.clip(tt / 0.12, 0, 1)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.09)
        M(x, t0 + off, gain, 0.25)


# New for the explainer, from the same parts.

def sink_pad(midis, dur, bend=-1.6):
    """Needs draining: the chord slowly detunes and sinks, a wobble in it."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    semis = bend * u ** 1.4 + 0.12 * np.sin(2 * np.pi * 3.1 * t) * u
    x = np.zeros(n)
    for m in midis:
        for det in (-0.12, 0.0, 0.15):
            f = note_hz(m + det) * 2 ** (semis / 12)
            x += signal.sawtooth(2 * np.pi * np.cumsum(f) / SR) * 0.25
    x = lowpass(x, 900)
    a = np.clip(t / 0.4, 0, 1) * np.clip((dur - t) / 0.25, 0, 1)
    return x * a / len(midis)


def choir(midis, dur):
    """The crowd, made musical: a soft 'oh' sung by a handful of voices."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for k in range(3):
            vib = 1 + 0.004 * np.sin(2 * np.pi * (4.6 + 0.7 * k) * t + k)
            f = note_hz(m + rng.uniform(-0.1, 0.1)) * vib
            x += signal.sawtooth(2 * np.pi * np.cumsum(f) / SR)
    x = band(x, 380, 620) * 1.0 + band(x, 760, 1050) * 0.5   # the vowel 'oh'
    x = lowpass(x, 1600)
    a = np.clip(t / 0.35, 0, 1) * np.clip((dur - t) / 0.4, 0, 1)
    return x * a / (len(midis) * 3) * 2.5


def crowd_clap():
    """A few people clapping a hair apart."""
    n = int(0.35 * SR)
    out = np.zeros(n)
    for _ in range(5):
        c = clap()
        i = int(rng.uniform(0, 0.025) * SR)
        out[i:i + len(c)] += c[: n - i] * rng.uniform(0.4, 0.8)
    return out * 0.6


# A minor afro-pop loop: Am, F, C, G, one chord a bar.
CHORDS = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]
KICK = (0, 6, 8, 14)
CLAP = (4, 12)
RIM = (3, 7, 11, 15)
BASS = ((0, 0), (3, 7), (6, 12), (10, 0), (13, 7))
GUITAR = (2, 5, 7, 9, 13, 15)
FILL = (0, 3, 6, 8, 10, 11, 14)                     # the busier riff for the gaps
SK, SC, SR_ = kick(), clap(), rim()
PLUCKS = []                                         # where the lead plucks play (for the notes)


def chord_at(b):
    return CHORDS[int(b // 4) % 4]


bars = math.ceil(T.BEATS / 4)
for bar in range(bars):
    b0 = bar * 4
    root, chord = CHORDS[bar % 4]
    pad_notes = chord + [chord[0] + 12]
    # The pad: quiet before the drop, cut by the tape stop, back with the dance.
    if b0 + 4 <= OFF_B or b0 >= DANCE_B:
        M(pad(pad_notes, 4 * BEAT + 0.3), beat_t(b0), 0.22 if b0 >= DROP_B else 0.14)
    elif b0 < OFF_B:
        M(pad(pad_notes, 4 * BEAT + 0.3), beat_t(b0), 0.22)
    if b0 < DANCE_B < b0 + 4:
        M(pad(pad_notes, (b0 + 4 - DANCE_B) * BEAT + 0.3), beat_t(DANCE_B), 0.22)
    # Real people: the choir holds the chord.
    if PEOPLE_B - 4 < b0 < HIDE_B:
        s0 = max(b0, PEOPLE_B)
        e0 = min(b0 + 4, OFF_B)
        M(choir(chord + [chord[1] + 12], (e0 - s0) * BEAT + 0.4), beat_t(s0), 0.16, -0.1)

    for s in range(16):
        b = b0 + s / 4
        t = beat_t(b)
        if b >= T.BEATS:
            break
        talk = speaking(t, t + 0.12)
        if b < DROP_B:
            # Before the pop: only a muffled shaker under the knocks.
            if s % 2 == 1:
                M(lowpass(shaker(s % 4 == 2), 2500), t, 0.25, -0.2)
            continue
        if OFF_B <= b < DANCE_B:
            # Hidden HUD: the drums are gone; a low filtered log drum keeps time.
            if s % 4 == 0:
                M(lowpass(log_drum(note_hz(root - 12)), 400), t, 0.5)
            continue
        if s in KICK:
            M(SK, t, 0.85)
        if s in CLAP:
            if PEOPLE_B <= b < HIDE_B and not talk:
                M(crowd_clap(), t, 0.5, 0.15)
            else:
                M(SC, t, 0.28 if talk else 0.45, 0.1)
        if s in RIM and not talk:
            M(SR_, t, 0.22, -0.35)
        M(shaker(s % 2 == 1), t, 0.11 if talk else 0.16, 0.4)
        for step, iv in BASS:
            if s == step:
                M(log_drum(note_hz(root - 12 + iv)), t, 0.55)
        # Lead plucks only where nobody is talking (and their ring clears the next word).
        steps = FILL if (BUS_B <= b < MONEY_B or b >= DANCE_B) else GUITAR
        if s in steps and not speaking(t, t + 0.15, pre=0.05, post=0.05):
            tone = chord[(s * 7 + bar) % 3] + 12 + (12 if s in (9, 15, 11) else 0)
            M(pluck(note_hz(tone), 0.45, 0.6), t, 0.3, 0.3 if s % 2 else -0.3)
            PLUCKS.append(t)

# The dance: the talking drum answers, loud in the gap, softer under the end line.
b = DANCE_B
while b < T.BEATS - 1:
    talking_drum(beat_t(b + 0.5), 0.35 if speaking(beat_t(b + 0.5), beat_t(b + 1.4)) else 0.55)
    b += 2

# The drop: a reversed cymbal into the pop.
n = int(1.2 * SR)
swell = highpass(noise(n), 5000) * np.linspace(0, 1, n) ** 3
M(swell, beat_t(DROP_B) - 1.2, 0.35)

# Needs draining: the chord sinks under it.
_dur = beat_t(FILL_BS[0]) - beat_t(DRAIN_B0) - 0.1
M(sink_pad(chord_at(DRAIN_B0)[1], _dur), beat_t(DRAIN_B0), 0.2, 0.0)

# The hidden HUD: a dark pad holds until the dance, and a swell into it.
M(pad(chord_at(OFF_B)[1], beat_t(DANCE_B) - OFF_T + 0.3, cutoff=700), OFF_T + 0.15, 0.2)
n = int(0.9 * SR)
M(highpass(noise(n), 4000) * np.linspace(0, 1, n) ** 3, beat_t(DANCE_B) - 0.9, 0.18)


def tape_stop(x, t0, length=0.5):
    """The music slows to a stop at t0, over `length` seconds, then silence."""
    i0, L = int(t0 * SR), int(length * SR)
    u = np.arange(L) / L
    pos = i0 + L * (1 - (1 - u) ** 3) / 3                    # integral of (1 - u)^2
    y = x.copy()
    for c in range(x.shape[0]):
        y[c, i0:i0 + L] = np.interp(pos, np.arange(x.shape[1]), x[c]) * (1 - u) ** 0.5
    y[:, i0 + L:] = 0
    return y


def drained(x):
    """The music goes under water while the needs drain, and comes straight back."""
    t = np.arange(N) / SR
    t0, t1 = beat_t(DRAIN_B0), beat_t(DRAIN_B1)
    back = beat_t(FILL_BS[0]) - 0.25
    w = np.clip((t - t0) / (t1 - t0), 0, 1) ** 1.3 * 0.8
    w *= np.clip(1 - (t - back) / 0.25, 0, 1)
    lp = signal.sosfiltfilt(signal.butter(2, 650, 'lowpass', fs=SR, output='sos'), x, axis=1)
    return x * (1 - w) + lp * w


music = drained(tape_stop(music_a.stereo(), OFF_T) + music_b.stereo())

# --------------------------------------------------------------- effects ---
# The first film's effects, unchanged ...

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


def ding(midi, dur=1.1, decay=0.35):
    """An FM bell: a need filling."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = note_hz(midi)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t / 0.15)
    return np.sin(2 * np.pi * f * t + mod) * env(n, 0.002, decay)


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


# ... and the explainer's new ones, built from the same parts.

def cash():
    """Shift pay: the drawer's clack, a two-bell 'ching', coins settling."""
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    out = band(noise(n), 1800, 6000) * env(n, 0.0005, 0.012) * 0.9          # the clack
    out += sine_sweep(240, 120, n, 0.015) * env(n, 0.001, 0.05) * 0.6        # the drawer thump
    for k, (m, dt) in enumerate(((96, 0.07), (100, 0.13))):                  # ching: C7, E7
        i = int(dt * SR)
        f = note_hz(m)
        tt = t[: n - i]
        bell = (np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(2 * np.pi * f * 2.76 * tt)
                + 0.2 * np.sin(2 * np.pi * f * 5.4 * tt)) * env(n - i, 0.001, 0.32)
        out[i:] += bell * (0.55 if k == 0 else 0.5)
    for j in range(14):                                                       # coins
        i = int((0.18 + 0.5 * (j / 14) ** 1.3 + rng.uniform(0, 0.03)) * SR)
        m = int(0.06 * SR)
        tt = np.arange(m) / SR
        tink = np.sin(2 * np.pi * rng.uniform(3500, 7500) * tt) * np.exp(-tt / rng.uniform(0.01, 0.03))
        out[i:i + m] += tink[: max(0, n - i)] * 0.25 * (1 - j / 16)
    return out


def blip(midi):
    """An app opening: a short sine tick on top of the press."""
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * note_hz(midi) * t) * env(n, 0.001, 0.04)


def fill_up():
    """A need bar filling: a short rising sine under its ding."""
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    f = 300 + 900 * (t / 0.25) ** 1.5
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.25) * 0.5


def pan_of(x_px):
    return float(np.clip((x_px - 960) / 960, -1, 1)) * 0.6


def hop_pan(h):
    return pan_of(h['to'][0]) if isinstance(h['to'], (list, tuple)) else 0.0


hop_by_t1 = {h['t1']: h for h in T.HOPS}
hop_by_t0 = {h['t0']: h for h in T.HOPS}
NEED_NOTES = [72, 76, 79, 84]           # C E G C: each need a step up
APP_NOTES = {'app-cars': 84, 'app-property': 86, 'app-boutique': 88, 'app-hail': 91}
for e in T.EVENTS:
    k, t = e['kind'], t_of(e['f'])
    if k == 'knock':
        sfx.add(knock(), t, 0.9)
    elif k == 'peel':
        sfx.add(peel(), t, 0.55)
    elif k == 'pop':
        sfx.add(shatter(), t, 0.85)
    elif k == 'hud-grow':
        sfx.add(whoosh(0.7, True, 250, 1800), t, 0.3, -0.4)
    elif k == 'hud-shrink':
        sfx.add(whoosh(0.5, False, 300, 2000), t, 0.22, -0.4)
    elif k == 'takeoff':
        h = hop_by_t0[e['f']]
        dur = (h['t1'] - h['t0']) / FPS
        sfx.add(whoosh(min(0.6, dur + 0.1), True, 500, 2500), t, 0.22 + 0.06 * h['apex'], hop_pan(h))
    elif k == 'land':
        h = hop_by_t1[e['f']]
        sfx.add(land(e['z']), t, 0.7, hop_pan(h))
    elif k == 'need-fill':
        sfx.add(ding(NEED_NOTES[e['note']]), t + 0.03, 0.42, -0.45)
        sfx.add(fill_up(), t, 0.18, -0.45)
    elif k == 'press':
        sfx.add(click(), t, 0.55)
        if e['target'] in APP_NOTES:
            sfx.add(blip(APP_NOTES[e['target']]), t + 0.04, 0.16, 0.15)
    elif k == 'shift-pay':
        sfx.add(cash(), t, 0.85, 0.2)
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
            sfx.add(note_flick(), t + i * 2 / FPS, 0.7, 0.3 + 0.03 * i)
    elif k == 'whoosh':
        sfx.add(whoosh(1.0, True, 300, 4500), t, 0.5)
    elif k == 'phone-rise':
        sfx.add(whoosh(0.45, True, 1200, 6000), t, 0.25, 0.1)
        sfx.add(ding(88), t + 0.25, 0.12, 0.1)
    elif k == 'phone-sink':
        sfx.add(whoosh(0.45, False, 1000, 5000), t, 0.22, 0.1)
    elif k == 'hud-off':
        for i, delay in enumerate((0.0, 0.07, 0.13, 0.2, 0.28, 0.36, 0.45)):
            sfx.add(power_down(), t + delay, 0.28 * (1 - i * 0.08), (-1) ** i * 0.15 * i)
    elif k == 'land-world':
        sfx.add(land('world'), t, 1.0)
    elif k == 'dance':
        sfx.add(whoosh(0.4, False, 800, 3000), t - 0.05, 0.2)
    elif k == 'endcard':
        sfx.add(shimmer([69, 72, 76, 81, 84]), t, 0.22)

# The camera's whip onto Tobi for Spray money: the move between the two camera
# keys that end on the spray press gets an air whoosh across its length.
_spray = ev('press', target='spray')
_cam = sorted(T.CAMERA, key=lambda c: c['f'])
_k = min(range(1, len(_cam)), key=lambda i: abs(_cam[i]['f'] - _spray))
if abs(_cam[_k]['f'] - _spray) <= 3 and _cam[_k]['f'] - _cam[_k - 1]['f'] <= BEAT_F:
    _w0, _w1 = t_of(_cam[_k - 1]['f']), t_of(_cam[_k]['f'])
    sfx.add(whoosh(_w1 - _w0 + 0.15, True, 600, 5000), _w0 - 0.05, 0.35, -0.3)
    WHIP = (_w0, _w1)
else:
    WHIP = None

# ------------------------------------------------------------- dynamics ---

def follow(x, attack, release):
    """A peak follower of a 1-D level, at a 1 kHz control rate."""
    hop = SR // 1000
    lv = maximum_filter1d(x, hop)[::hop]
    a_a, a_r = np.exp(-1 / (attack * 1000)), np.exp(-1 / (release * 1000))
    out = np.empty_like(lv)
    cur = 0.0
    for i, v in enumerate(lv):
        cur = v + (cur - v) * (a_a if v > cur else a_r)
        out[i] = cur
    return np.interp(np.arange(len(x)), np.arange(len(out)) * hop, out)


def comp_gain(x, thresh_db=-18, ratio=3.0, attack=0.005, release=0.12, makeup_db=0):
    """The gain a feed-forward compressor applies to a stereo signal."""
    lvl = follow(np.max(np.abs(x), axis=0), attack, release)
    lvl_db = 20 * np.log10(np.maximum(lvl, 1e-6))
    over = np.maximum(lvl_db - thresh_db, 0)
    return 10 ** ((-over * (1 - 1 / ratio) + makeup_db) / 20)


def true_peak_per_sample(x, over=4):
    """|x| at 4x oversampling, the worst of each sample's four, both channels."""
    up = signal.resample_poly(x, over, 1, axis=1)
    return np.max(np.abs(up), axis=0)[: x.shape[1] * over].reshape(-1, over).max(axis=1)


def limit_gain(x, ceiling_db=CEILING_DBTP - 0.2, look=0.003, release=0.08):
    """A true-peak lookahead limiter's gain: held over the lookahead, a smooth attack, a slow release."""
    ceil = 10 ** (ceiling_db / 20)
    la = int(look * SR)
    need = np.minimum(1.0, ceil / np.maximum(true_peak_per_sample(x), 1e-9))
    held = minimum_filter1d(need, size=2 * la + 1)
    hop = 16                                 # release at a 3 kHz control rate
    hc = np.pad(held, (0, -len(held) % hop), mode='edge').reshape(-1, hop).min(axis=1)
    rel = np.exp(-1 / (release * SR / hop))
    g = np.empty_like(hc)
    cur = 1.0
    for i, h in enumerate(hc):
        cur = h if h < cur else h + (cur - h) * rel
        g[i] = cur
    g = np.repeat(g, hop)[: len(held)]
    g = np.minimum(g, held)
    w = np.hanning(la) / np.hanning(la).sum()
    return np.minimum(np.convolve(g, w, 'same'), held)


def lufs(x):
    """Integrated loudness, ITU-R BS.1770-4 (K-weighting, 400 ms blocks, gated)."""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    y = signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=1), axis=1)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    sq = np.cumsum(np.pad(y ** 2, ((0, 0), (1, 0))), axis=1)
    starts = np.arange(0, y.shape[1] - blk + 1, hop)
    z = ((sq[:, starts + blk] - sq[:, starts]) / blk).sum(axis=0)
    l = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    z = z[l > -70]
    l = l[l > -70]
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    return -0.691 + 10 * np.log10(z[l > rel].mean())


def db(x):
    return 20 * np.log10(max(1e-9, x))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if np.size(x) else 0.0


# ---------------------------------------------------------------- voice ---

def read_wav(path):
    with wave.open(path) as w:
        assert w.getsampwidth() == 2, path
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 32768
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels()).mean(axis=1)
        return x, w.getframerate()


def peaking(x, f0, gain_db, q):
    """RBJ peaking EQ."""
    A, w0 = 10 ** (gain_db / 40), 2 * np.pi * f0 / SR
    al = np.sin(w0) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w0), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w0), 1 - al / A]
    return signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], x)


def speech_rms(x, frame=0.02, floor_db=-30):
    """RMS over the frames that are speech (within floor_db of the loudest)."""
    n = int(frame * SR)
    fr = x[: len(x) // n * n].reshape(-1, n)
    r = np.sqrt(np.mean(fr ** 2, axis=1))
    keep = r > r.max() * 10 ** (floor_db / 20)
    return float(np.sqrt(np.mean(fr[keep] ** 2)))


VO_DIR = os.path.join(STUDIO, 'cache', 'vo', T.VOICE)
VOICE_RMS = 10 ** (-19 / 20)         # every line levelled to the same speech RMS before the comp
voice = np.zeros(N + 4 * SR)
for v in T.VO:
    x, sr = read_wav(os.path.join(VO_DIR, v['id'] + '.wav'))
    g = math.gcd(SR, sr)
    x = signal.resample_poly(x, SR // g, sr // g)
    x = highpass(x, 90, 2)
    x = peaking(x, 3000, 2.5, 0.9)                         # presence
    x = peaking(x, 250, -1.5, 1.0)                         # a touch less box
    gain = np.clip(VOICE_RMS / max(speech_rms(x), 1e-6), 10 ** (-6 / 20), 10 ** (6 / 20))
    x = x * gain
    x = x * comp_gain(x[None], thresh_db=-22, ratio=2.5, attack=0.005, release=0.1)
    x *= VOICE_RMS / max(speech_rms(x), 1e-6)              # back to the line level after the comp
    i = int(round(t_of(v['f']) * SR))
    voice[i:i + len(x)] += x
voice = voice[:N]

# The sidechain: where the voice is speaking, with a little lookahead and a hold
# across the gaps between words, smoothed to ~40 ms down and ~250 ms back up.
hop = SR // 1000
vr = np.sqrt(np.convolve(voice ** 2, np.ones(int(0.01 * SR)) / int(0.01 * SR), 'same'))[::hop]
active = (vr > VOICE_RMS * 10 ** (-24 / 20)).astype(float)
cm = maximum_filter1d(active, size=181)               # max over [i - 90, i + 90] ms
active = np.concatenate([np.full(60, cm[0]), cm[:-60]])  # -> [i - 150, i + 30]: hold 150 ms, look ahead 30 ms
target = 1 - active                                   # 1 = no duck, 0 = full duck
a_a, a_r = np.exp(-1 / (0.040 * 1000)), np.exp(-1 / (0.250 * 1000))
depth = np.empty_like(target)
cur = 1.0
for i, v in enumerate(target):
    cur = v + (cur - v) * (a_a if v < cur else a_r)
    depth[i] = cur
depth = 1 - np.interp(np.arange(N), np.arange(len(depth)) * hop, depth)     # 0..1, 1 = fully ducked
duck = 10 ** (DUCK_DB * depth / 20)
mid_keep = 10 ** (MID_DIP_DB * depth / 20)

# -------------------------------------------------------------- the mix ---

bed = music * comp_gain(music, -16, 2.5, 0.01, 0.2, 2) * 0.9 + sfx.stereo()
# The bed fades from the fade event to the end; the voice is never faded.
fade_t = t_of(ev('fade'))
tt = np.arange(N) / SR
bed = bed * np.clip(1 - (tt - fade_t) / (DUR - fade_t), 0, 1) ** 1.5

# Level the bed against the voice: where nobody speaks after the drop, the
# bed sits 3 dB under the voice's speech level (then the duck takes it down).
free = depth < 0.02
free &= (tt > beat_t(DROP_B)) & (tt < fade_t)
bed_gain = VOICE_RMS * 10 ** (-3 / 20) / max(rms(bed[:, free]), 1e-9)
bed = bed * bed_gain

mid = signal.sosfiltfilt(signal.butter(2, [1000, 5000], 'bandpass', fs=SR, output='sos'), bed, axis=1)
bed_d = (bed - mid * (1 - mid_keep)) * duck
vo2 = np.stack([voice, voice])                       # centred
mix = vo2 + bed_d

# The master: a gentle glue compressor, then gain to the loudness target and a
# true-peak limiter, iterated until both hold. The same gain goes on the stems
# (for the measurements) and on the music-only file.
g_master = comp_gain(mix, -16, 1.8, 0.005, 0.15)
gain = 1.0
for _ in range(6):
    pre = mix * g_master * gain
    g_lim = limit_gain(pre)
    out = pre * g_lim
    L = lufs(out)
    if abs(L - TARGET_LUFS) < 0.1:
        break
    gain *= 10 ** ((TARGET_LUFS - L) / 20)
g_total = g_master * gain * g_lim
mix_out = mix * g_total
voice_out, bed_out = vo2 * g_total, bed_d * g_total
tp = db(np.max(true_peak_per_sample(mix_out)))

music_pre = bed * g_master * gain                    # the un-ducked bed, same staging
music_out = music_pre * limit_gain(music_pre)
music_l, music_tp = lufs(music_out), db(np.max(true_peak_per_sample(music_out)))

# ---------------------------------------------------------------- write ---

def write_wav(path, x):
    pcm = np.round(np.clip(x, -1, 1 - 2 ** -23) * 8388607).astype('<i4').T.copy()
    b = pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b)


out_dir = os.path.join(STUDIO, 'out', 'explainer')
os.makedirs(out_dir, exist_ok=True)
write_wav(os.path.join(out_dir, 'sound.wav'), mix_out)
write_wav(os.path.join(out_dir, 'music.wav'), music_out)

# ------------------------------------------------------------- measure ---
# Voice over the ducked bed, per line, over the samples where the voice speaks:
# broadband RMS and in the speech band (300 Hz - 4 kHz).
spb = signal.butter(4, [300, 4000], 'bandpass', fs=SR, output='sos')
voice_sb = signal.sosfiltfilt(spb, voice_out[0])
bed_sb = signal.sosfiltfilt(spb, bed_out.mean(axis=0))
spoken = np.repeat(vr > VOICE_RMS * 10 ** (-24 / 20), hop)[:N]
rows = []
for v in T.VO:
    a, b = int(t_of(v['f']) * SR), min(N, int(t_of(v['f_end']) * SR))
    m = spoken[a:b]
    vb, bb = voice_out[0, a:b][m], bed_out[:, a:b][:, m]
    r_bb = db(rms(vb)) - db(rms(bb))
    r_sb = db(rms(voice_sb[a:b][m])) - db(rms(bed_sb[a:b][m]))
    bed_peak = db(np.max(np.abs(bb))) - db(np.max(np.abs(vb)))
    rows.append((v['id'], t_of(v['f']), t_of(v['f_end']), db(rms(vb)), db(rms(bb)), r_bb, r_sb, bed_peak))

clip = int(np.sum(np.abs(mix_out) >= 1.0))
L_mix = lufs(mix_out)
L_vo = lufs(voice_out)
fade_i = int(fade_t * SR)
tail = [db(rms(bed_out[:, i:i + SR // 10])) for i in range(fade_i, N, SR // 10)]

lines = [
    'PH Lifestyle explainer: sound notes (written by src/sound.py)',
    '',
    f'sound.wav  48 kHz stereo 24-bit, {mix_out.shape[1]} samples = {mix_out.shape[1] / SR:.3f} s = {mix_out.shape[1] / SR * FPS:.0f} frames',
    f'  integrated {L_mix:.1f} LUFS (BS.1770-4, own meter), true peak {tp:.2f} dBTP (4x oversampled), {clip} clipped samples',
    f'  voice alone (as mixed) {L_vo:.1f} LUFS',
    f'music.wav  the bed without the voice and without ducking, same gain staging',
    f'  integrated {music_l:.1f} LUFS, true peak {music_tp:.2f} dBTP',
    '',
    f'Voice: {T.VOICE}, resampled to 48 kHz, high-pass 90 Hz, +2.5 dB at 3 kHz, -1.5 dB at 250 Hz,',
    '  levelled per line, 2.5:1 compression, centred. Bed ducked {:.0f} dB under it (+{:.0f} dB more at 1-5 kHz),'.format(DUCK_DB, -MID_DIP_DB),
    '  ~40 ms down, ~250 ms back up, 150 ms hold, 30 ms lookahead. The fade touches only the bed.',
    '',
    'Voice over the ducked bed, per line (where the voice speaks; dB):',
    f'  {"line":8} {"start":>6} {"end":>6} {"voice":>7} {"bed":>7} {"ratio":>6} {"speech-band":>11} {"bed pk vs voice pk":>19}',
]
for r in rows:
    lines.append(f'  {r[0]:8} {r[1]:6.2f} {r[2]:6.2f} {r[3]:7.1f} {r[4]:7.1f} {r[5]:6.1f} {r[6]:11.1f} {r[7]:19.1f}')
lines += ['', f'  worst broadband ratio {min(r[5] for r in rows):.1f} dB ({min(rows, key=lambda r: r[5])[0]}), '
          f'worst speech-band ratio {min(r[6] for r in rows):.1f} dB ({min(rows, key=lambda r: r[6])[0]})',
          '', f'Camera whip whoosh: {WHIP[0]:.2f}-{WHIP[1]:.2f} s' if WHIP else 'Camera whip whoosh: none found',
          '', f'Lead plucks ({len(PLUCKS)}), only between lines, at (s): ' + ' '.join(f'{x:.1f}' for x in PLUCKS),
          '', 'Bed level through the fade (100 ms steps from the fade event): '
          + ' '.join(f'{x:.0f}' for x in tail)]
notes = '\n'.join(lines) + '\n'
open(os.path.join(out_dir, 'sound-notes.txt'), 'w').write(notes)
print(notes)

# -------------------------------------------------------------- review ---
# A spectrogram of the mix, the voice and bed levels under it, the duck, the VO
# lines shaded and the sections marked.
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

Wd, LEFT, RIGHT = 1800, 70, 20
PW = Wd - LEFT - RIGHT
SPEC_Y, SPEC_H = 70, 360
LVL_Y, LVL_H = SPEC_Y + SPEC_H + 30, 220
WAV_Y, WAV_H = LVL_Y + LVL_H + 30, 120
Hd = WAV_Y + WAV_H + 50
img = Image.new('RGB', (Wd, Hd), (14, 14, 18))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.load_default(size=13)
    big = ImageFont.load_default(size=17)
except TypeError:
    font = big = ImageFont.load_default()


def X(t):
    return LEFT + t / DUR * PW


# Spectrogram: log frequency 40 Hz - 16 kHz, dB, a dark-to-warm colour ramp.
mono = mix_out.mean(axis=0)
fr, ts, S = signal.spectrogram(mono, SR, nperseg=2048, noverlap=2048 - 480, window='hann')
S = 10 * np.log10(S + 1e-14)
cols = np.clip(((ts / DUR) * PW).astype(int), 0, PW - 1)
fy = np.geomspace(40, 16000, SPEC_H)[::-1]
rows_i = np.clip(np.searchsorted(fr, fy), 0, len(fr) - 1)
grid = np.full((SPEC_H, PW), -140.0)
for c in range(PW):
    k = np.argmin(np.abs(ts - (c + 0.5) / PW * DUR))
    grid[:, c] = S[rows_i, k]
top = np.percentile(grid, 99.5)
u = np.clip((grid - (top - 80)) / 80, 0, 1)
ramp = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66],
                 [245, 125, 21], [250, 193, 39], [252, 255, 164]], float)
idx = u * (len(ramp) - 1)
lo_i = np.floor(idx).astype(int).clip(0, len(ramp) - 2)
fra = (idx - lo_i)[..., None]
rgb = ramp[lo_i] * (1 - fra) + ramp[lo_i + 1] * fra
img.paste(Image.fromarray(rgb.astype(np.uint8)), (LEFT, SPEC_Y))
for f_hz in (100, 300, 1000, 3000, 10000):
    y = SPEC_Y + SPEC_H - np.log(f_hz / 40) / np.log(16000 / 40) * SPEC_H
    d.line([(LEFT - 5, y), (LEFT, y)], fill=(180, 180, 180))
    d.text((8, y - 7), f'{f_hz // 1000}k' if f_hz >= 1000 else str(f_hz), fill=(180, 180, 180), font=font)

# Levels: voice and bed short-term RMS (50 ms), the duck gain.
d.rectangle([LEFT, LVL_Y, LEFT + PW, LVL_Y + LVL_H], fill=(22, 22, 28))
win = int(0.05 * SR)


def level_curve(x):
    e = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, 'same'))[::win // 2]
    return 20 * np.log10(np.maximum(e, 1e-6))


def Ylvl(v):
    return LVL_Y + LVL_H - (np.clip(v, -60, 0) + 60) / 60 * LVL_H


for g_db in (-10, -20, -30, -40, -50):
    y = Ylvl(g_db)
    d.line([(LEFT, y), (LEFT + PW, y)], fill=(45, 45, 55))
    d.text((24, y - 7), f'{g_db}', fill=(140, 140, 150), font=font)
tl = np.arange(0, N, win // 2) / SR
for curve, colour in ((level_curve(bed_out.mean(axis=0)), (150, 150, 165)),
                      (level_curve(voice_out[0]), (0, 200, 120))):
    d.line(list(zip(X(tl), Ylvl(curve))), fill=colour, width=2)
dk = 20 * np.log10(duck[::win // 2])
d.line(list(zip(X(tl), LVL_Y + 4 - dk / 9 * 24)), fill=(240, 170, 60), width=1)

# Waveform of the mix.
d.rectangle([LEFT, WAV_Y, LEFT + PW, WAV_Y + WAV_H], fill=(22, 22, 28))
for c in range(PW):
    a, b = int(c / PW * N), int((c + 1) / PW * N)
    seg = mono[a:b]
    ymid = WAV_Y + WAV_H / 2
    d.line([(LEFT + c, ymid - seg.max() * WAV_H / 2), (LEFT + c, ymid - seg.min() * WAV_H / 2)], fill=(120, 160, 230))

# VO lines: shaded across every lane, named under the spectrogram.
over = Image.new('RGBA', img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(over)
for k, v in enumerate(T.VO):
    x0, x1 = X(t_of(v['f'])), X(t_of(v['f_end']))
    for y0, h in ((SPEC_Y, SPEC_H), (LVL_Y, LVL_H), (WAV_Y, WAV_H)):
        od.rectangle([x0, y0, x1, y0 + h], fill=(0, 220, 130, 34), outline=(0, 220, 130, 120))
    d_y = LVL_Y - 22 + (k % 2) * 11
    od.text((x0 + 2, d_y), v['id'], fill=(0, 230, 140, 255), font=font)
img = Image.alpha_composite(img.convert('RGBA'), over).convert('RGB')
d = ImageDraw.Draw(img)
# Sections and events.
for b, name in SECTIONS:
    x = X(beat_t(b))
    d.line([(x, SPEC_Y - 26), (x, WAV_Y + WAV_H)], fill=(255, 255, 255), width=1)
    d.text((x + 3, SPEC_Y - 26), name, fill=(255, 255, 255), font=font)
for e in T.EVENTS:
    if e['kind'] in ('takeoff', 'land'):
        continue
    x = X(t_of(e['f']))
    d.line([(x, WAV_Y + WAV_H), (x, WAV_Y + WAV_H + 6)], fill=(240, 170, 60))
for s in range(0, int(DUR) + 1, 2):
    d.text((X(s) - 6, WAV_Y + WAV_H + 10), f'{s}s', fill=(160, 160, 170), font=font)
d.text((LEFT, 12), f'{T.NAME}: sound.wav  {L_mix:.1f} LUFS  {tp:.1f} dBTP  |  green = voice lines / voice level, '
       f'grey = ducked bed, orange = duck ({DUCK_DB:.0f} dB at the top)', fill=(230, 230, 235), font=big)
rev = os.path.join(STUDIO, 'reviews', 'sound-explainer.png')
img.save(rev)
print(f'{os.path.join(out_dir, "sound.wav")}\n{os.path.join(out_dir, "music.wav")}\n{rev}')
