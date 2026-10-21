"""The sound library: every drum, instrument, effect, dynamics stage and voice
tool a film's sound needs, made from numpy noise and sines. No samples.

Copy to <studio>/src/synth.py next to sound.py; sound.py imports it.
Everything is mono float64 at SR (48 kHz) unless it says stereo (2, n).
Random parts draw from one seeded generator, so a film renders the same twice:
call seed(n) for another take.

    cache/venv/bin/python -c "import sys; sys.path.insert(0, 'src'); import synth"   # import check

Needs numpy + scipy; soundfile when present (wave from the stdlib otherwise).
"""
import math
import wave

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d, minimum_filter1d

try:
    import soundfile as _sf
except ImportError:          # the stdlib wave module covers 16/24-bit PCM
    _sf = None

SR = 48000
rng = np.random.default_rng(404)


def seed(n=404):
    """Reset the generator: same seed, same film."""
    global rng
    rng = np.random.default_rng(n)


def secs(n):
    return int(round(n * SR))


# ============================================================ building blocks ==

def env(n, a=0.002, d=0.2, curve=1.0):
    """Attack then exponential decay, n samples."""
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-5), 0, 1)
    return att * np.exp(-t / max(d, 1e-5)) ** curve


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    """A held note: attack, decay to sustain, release over the last r seconds."""
    t = np.arange(n) / SR
    dur = n / SR
    e = np.where(t < a, t / max(a, 1e-5), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-5)))
    return e * np.clip((dur - t) / max(r, 1e-5), 0, 1)


def noise(n):
    return rng.standard_normal(n)


def band(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR / 2 - 100)], 'bandpass', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lowpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, min(f, SR / 2 - 100), 'lowpass', fs=SR, output='sos'), x)


def highpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x)


def swept_band(x, lo, hi, q=1.4, k=1024):
    """Band-pass whose centre glides from lo to hi across x (block-wise, cheap)."""
    out = np.zeros(len(x))
    for i in range(0, len(x), k):
        c = lo + (hi - lo) * (i / max(1, len(x)))
        out[i:i + k] = band(x[i:i + k], c / q, min(c * q, SR / 2 - 200), 1)
    return out


def sine_sweep(f0, f1, n, tau=0.05):
    """A sine that falls (or rises) exponentially from f0 to f1, time constant tau."""
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def osc(f, n=None, shape='sine'):
    """An oscillator from a frequency (Hz, scalar or per-sample array)."""
    f = np.full(n, float(f)) if np.isscalar(f) else np.asarray(f, float)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if shape == 'saw':
        return signal.sawtooth(ph)
    if shape == 'square':
        return signal.square(ph)
    if shape == 'tri':
        return signal.sawtooth(ph, 0.5)
    return np.sin(ph)


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def pan(x, p=0.0):
    """Mono -> stereo (2, n), equal-power, p in -1 (left) .. 1 (right)."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)])


def fade_edges(x, a=0.003, r=0.01):
    """Short fades so a cut-off sound does not click."""
    n = len(x)
    t = np.arange(n) / SR
    return x * np.clip(t / a, 0, 1) * np.clip((n / SR - t) / r, 0, 1)


def mixdown(*parts):
    """Sum sounds of different lengths, aligned at their start: (x, offset_s, gain)."""
    n = max(secs(o) + len(x) for x, o, g in parts)
    out = np.zeros(n)
    for x, o, g in parts:
        i = secs(o)
        out[i:i + len(x)] += x * g
    return out


# ====================================================================== drums ==

def kick():
    n = secs(0.45)
    x = sine_sweep(150, 46, n, 0.035) * env(n, 0.001, 0.22)
    x += band(noise(n), 1500, 6000) * env(n, 0.0005, 0.006) * 0.4      # the beater
    return np.tanh(x * 1.6)


def clap():
    n = secs(0.3)
    e = np.zeros(n)
    for k, off in enumerate((0, 0.009, 0.019)):                          # three hands a hair apart
        i = secs(off)
        e[i:] += env(n - i, 0.0005, 0.012 if k < 2 else 0.11)
    return band(noise(n), 900, 5200) * e


def crowd_clap(people=5):
    """A few people clapping a hair apart."""
    n = secs(0.35)
    out = np.zeros(n)
    for _ in range(people):
        c = clap()
        i = secs(rng.uniform(0, 0.025))
        out[i:i + len(c)] += c[: n - i] * rng.uniform(0.4, 0.8)
    return out * 0.6


def shaker(accent=False):
    n = secs(0.06)
    return highpass(noise(n), 6000) * env(n, 0.004, 0.018) * (1.0 if accent else 0.55)


def rim():
    n = secs(0.08)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 820 * t) * 0.6 + band(noise(n), 1800, 4000) * 0.4) * env(n, 0.0005, 0.018)


def hat(open_=False):
    """808-style hat: six detuned squares, metallic, high-passed."""
    n = secs(0.35 if open_ else 0.08)
    x = sum(osc(f * 1.9, n, 'square') for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
    x = highpass(band(x, 6500, 15000), 7000)
    return x * env(n, 0.0005, 0.11 if open_ else 0.018) * 0.35


# ================================================================ instruments ==

def pluck(hz, dur=0.5, bright=0.5):
    """Karplus-Strong: the highlife guitar. A recursive filter, so it is fast."""
    n = secs(dur)
    p = max(2, int(SR / hz))
    burst = np.zeros(n)
    burst[:p] = lowpass(noise(p) * 0.5, 2000 + 5000 * bright, 1)
    a = np.zeros(p + 1)
    a[0], a[p - 1], a[p] = 1.0, -0.498, -0.498                          # average two taps, lose 0.4 % a lap
    return signal.lfilter([1.0], a, burst) * env(n, 0.001, dur * 0.6)


def pad(midis, dur, cutoff=1400, attack=0.25, release=0.3):
    """Three detuned saws a note, low-passed: the chord bed."""
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for det in (-0.07, 0.0, 0.07):
            x += signal.sawtooth(2 * np.pi * note_hz(m + det) * t) * 0.25
    x = lowpass(x, cutoff)
    a = np.clip(t / attack, 0, 1) * np.clip((dur - t) / release, 0, 1)
    return x * a / max(1, len(midis))


def bass(hz, dur=0.4, cutoff=420):
    """A round synth bass: saw + sub sine, low-passed, plucked envelope."""
    n = secs(dur)
    x = osc(hz, n, 'saw') * 0.5 + osc(hz, n) * 0.8
    return np.tanh(lowpass(x, cutoff) * 1.4) * adsr(n, 0.004, 0.12, 0.55, 0.05)


def log_drum(hz):
    """The amapiano/afro log drum: a sine that slides down into its note."""
    n = secs(0.42)
    x = sine_sweep(hz * 1.9, hz, n, 0.018) * env(n, 0.002, 0.16)
    return np.tanh(x * 2.2) * 0.8


def keys(midi, dur=0.8, bright=1.0):
    """FM electric piano: a 1:1 bell body with a short 14:1 tine on the front."""
    n = secs(dur)
    t = np.arange(n) / SR
    f = note_hz(midi)
    body = np.sin(2 * np.pi * f * t + 1.6 * bright * np.exp(-t / 0.25) * np.sin(2 * np.pi * f * t))
    tine = np.sin(2 * np.pi * f * 14 * t) * np.exp(-t / 0.012) * 0.12 * bright
    return (body + tine) * env(n, 0.002, dur * 0.45) * np.clip((dur - t) / 0.05, 0, 1)


def keys_chord(midis, dur=0.8, bright=1.0, strum=0.012):
    out = np.zeros(secs(dur + strum * len(midis)))
    for k, m in enumerate(midis):
        x = keys(m, dur, bright)
        i = secs(k * strum)
        out[i:i + len(x)] += x
    return out / max(1, len(midis)) * 1.6


def brass_stab(midis, dur=0.35):
    """A horn-section stab: detuned saws whose filter closes fast."""
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for det in (-0.08, 0.06):
            f = note_hz(m + det) * (1 + 0.012 * np.exp(-t / 0.03))        # a little scoop up into the note
            x += osc(f, n, 'saw')
    x /= max(1, len(midis))
    bright, dark = lowpass(x, 4200), lowpass(x, 900)
    w = np.exp(-t / 0.07)
    return np.tanh((bright * w + dark * (1 - w)) * 1.3) * adsr(n, 0.008, 0.12, 0.5, 0.08)


def choir(midis, dur):
    """A soft 'oh' sung by a handful of voices."""
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in midis:
        for k in range(3):
            vib = 1 + 0.004 * np.sin(2 * np.pi * (4.6 + 0.7 * k) * t + k)
            x += osc(note_hz(m + rng.uniform(-0.1, 0.1)) * vib, n, 'saw')
    x = band(x, 380, 620) + band(x, 760, 1050) * 0.5                     # the vowel 'oh'
    x = lowpass(x, 1600)
    a = np.clip(t / 0.35, 0, 1) * np.clip((dur - t) / 0.4, 0, 1)
    return x * a / (max(1, len(midis)) * 3) * 2.5


def talking_drum(step):
    """A pitch-bent tom phrase (three strokes a sixteenth and a half apart)."""
    parts = []
    for off, f0, f1 in ((0, 180, 260), (step * 1.5, 260, 150), (step * 3, 200, 300)):
        n = secs(0.25)
        tt = np.arange(n) / SR
        f = f0 + (f1 - f0) * np.clip(tt / 0.12, 0, 1)
        parts.append((osc(f) * env(n, 0.001, 0.09), off, 1.0))
    return mixdown(*parts)


# ====================================================================== sfx ==

def knock():
    """A knuckle on glass: a dull body and a ring."""
    n = secs(0.25)
    t = np.arange(n) / SR
    body = lowpass(noise(n), 900) * env(n, 0.0008, 0.02) * 1.5
    ring = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((2300, 0.3), (3720, 0.2), (5150, 0.1))) * env(n, 0.001, 0.07)
    return body + ring


def peel():
    """A sticker coming off: a rising band of noise with crackle."""
    n = secs(0.55)
    t = np.arange(n) / SR
    crackle = (rng.random(n) < 0.012) * rng.standard_normal(n) * 3
    x = swept_band(noise(n), 1000, 6800, q=1.35) + highpass(crackle, 2000)
    return x * np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.35) * 0.9


def shatter():
    """Glass breaking: a stomp, a crack and seventy pieces."""
    n = secs(1.6)
    out = lowpass(noise(n), 200) * env(n, 0.001, 0.12) * 2.5
    out += sine_sweep(90, 40, n, 0.08) * env(n, 0.001, 0.25) * 1.2
    out += highpass(noise(n), 3000) * env(n, 0.0005, 0.09)
    for _ in range(70):
        i = secs(rng.uniform(0, 0.9) ** 1.8)
        m = secs(0.12)
        tt = np.arange(m) / SR
        tink = np.sin(2 * np.pi * rng.uniform(2500, 9000) * tt) * np.exp(-tt / rng.uniform(0.01, 0.04)) * rng.uniform(0.05, 0.25)
        out[i:i + m] += tink[: n - i]
    return out


def pop():
    """A bubble or cork pop: a fast upward blip with a puff."""
    n = secs(0.12)
    t = np.arange(n) / SR
    f = 380 + 1500 * (1 - np.exp(-t / 0.012))
    return osc(f) * env(n, 0.0005, 0.03) + band(noise(n), 800, 3000) * env(n, 0.0003, 0.006) * 0.5


def whoosh(dur=0.5, up=True, lo=400, hi=3000):
    """Air past the camera: band noise gliding up (or down), swelled."""
    n = secs(dur)
    x = swept_band(noise(n), lo, hi) if up else swept_band(noise(n), hi, lo)
    tt = np.arange(n) / SR
    return x * np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.5 * 1.6


def boing(dur=0.42, f0=180, f1=520):
    """A take-off spring: pitch bends up while it wobbles, a jaw-harp edge."""
    n = secs(dur)
    t = np.arange(n) / SR
    wob = 1 + 0.18 * np.sin(2 * np.pi * 15 * t) * np.exp(-t / 0.18)
    f = (f0 + (f1 - f0) * (1 - np.exp(-t / (dur * 0.35)))) * wob
    x = osc(f) + 0.3 * osc(f * 2.01) + 0.12 * osc(f, shape='square')
    return lowpass(x, 3500) * env(n, 0.003, dur * 0.4) * 0.8


def land(z='hud'):
    """A hard landing: a tuned thump (lower for heavier floors) and a scuff."""
    n = secs(0.3)
    lo = {'world': 70, 'hud': 110, 'phone': 150, 'bus': 85}.get(z, 110)
    x = sine_sweep(lo * 2, lo, n, 0.02) * env(n, 0.001, 0.07)
    x += band(noise(n), 1500, 5000) * env(n, 0.0005, 0.008) * 0.6
    return np.tanh(x * 1.5)


def pomf(hz=90, weight=1.0):
    """A soft landing: a cushioned low thump and a cloth puff, no click."""
    n = secs(0.35)
    x = sine_sweep(hz * 1.6, hz * 0.7, n, 0.04) * env(n, 0.006, 0.09 * weight)
    puff = lowpass(noise(n), 700) * env(n, 0.004, 0.035) * 0.7
    return np.tanh((x + puff) * 1.3)


def click():
    """A keycap: a bright down-click, then the softer return 35 ms later."""
    n = secs(0.12)
    t = np.arange(n) / SR
    a = np.sin(2 * np.pi * 1900 * t) * env(n, 0.0003, 0.008)
    b = np.sin(2 * np.pi * 1300 * t) * env(n, 0.0003, 0.03)
    b = np.concatenate([np.zeros(secs(0.035)), b])[:n]
    return a * 0.8 + b * 0.6


def blip(midi=84):
    """A UI blip on top of a press: a short sine tick."""
    n = secs(0.16)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * note_hz(midi) * t) * env(n, 0.001, 0.04)


def ding(midi=84, dur=1.1, decay=0.35):
    """An FM bell."""
    n = secs(dur)
    t = np.arange(n) / SR
    f = note_hz(midi)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t / 0.15)
    return np.sin(2 * np.pi * f * t + mod) * env(n, 0.002, decay)


def fill_up(dur=0.25):
    """A bar filling: a short rising sine (goes under a ding)."""
    n = secs(dur)
    t = np.arange(n) / SR
    return osc(300 + 900 * (t / dur) ** 1.5) * np.sin(np.pi * t / dur) * 0.5


def horn(honks=2):
    """A minibus horn: short two-note square honks."""
    out = np.zeros(secs(0.18 + 0.26 * honks))
    for k in range(honks):
        n = secs(0.18)
        t = np.arange(n) / SR
        x = osc(415, n, 'square') * 0.5 + osc(523, n, 'square') * 0.5
        x = lowpass(x, 2200) * np.clip(t / 0.01, 0, 1) * np.clip((0.18 - t) / 0.02, 0, 1)
        i = secs(k * 0.26)
        out[i:i + n] += x
    return out


def engine(dur=2.0, rev=False):
    """An engine idling past (rev=False) or revving away (rev=True)."""
    n = secs(dur)
    t = np.arange(n) / SR
    f = 38 + 22 * (t / dur if rev else np.sin(np.pi * t / dur))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = signal.sawtooth(ph) + 0.5 * signal.sawtooth(ph * 2.02)
    x = lowpass(x, 500) + lowpass(noise(n), 300) * 0.6
    return x * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7


def clang():
    """Metal struck: four inharmonic partials over a thump."""
    n = secs(0.6)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((310, 0.5), (742, 0.35), (1290, 0.2), (2010, 0.1)))
    x = x * env(n, 0.001, 0.14)
    th = land('bus')
    x[:len(th)] += th * 0.6
    return x


def coins(count=14, dur=0.7):
    """Coins settling: tinkles that thin out."""
    n = secs(dur + 0.1)
    out = np.zeros(n)
    for j in range(count):
        i = secs(dur * 0.75 * (j / count) ** 1.3 + rng.uniform(0, 0.03))
        m = secs(0.06)
        tt = np.arange(m) / SR
        tink = np.sin(2 * np.pi * rng.uniform(3500, 7500) * tt) * np.exp(-tt / rng.uniform(0.01, 0.03))
        out[i:i + m] += tink[: max(0, n - i)] * 0.25 * (1 - j / (count + 2))
    return out


def cash():
    """A till: the drawer's clack, a two-bell 'ching', coins settling."""
    n = secs(1.2)
    t = np.arange(n) / SR
    out = band(noise(n), 1800, 6000) * env(n, 0.0005, 0.012) * 0.9
    out += sine_sweep(240, 120, n, 0.015) * env(n, 0.001, 0.05) * 0.6
    for k, (m, dt) in enumerate(((96, 0.07), (100, 0.13))):                # ching: C7, E7
        i = secs(dt)
        f = note_hz(m)
        tt = t[: n - i]
        bell = (np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(2 * np.pi * f * 2.76 * tt)
                + 0.2 * np.sin(2 * np.pi * f * 5.4 * tt)) * env(n - i, 0.001, 0.32)
        out[i:] += bell * (0.55 if k == 0 else 0.5)
    c = coins()
    i = secs(0.18)
    out[i:i + len(c)] += c[: n - i]
    return out


def note_flick():
    """A banknote flicked off a stack."""
    n = secs(0.09)
    return band(noise(n), 1500, 7000) * env(n, 0.001, 0.02)


def power_down():
    """A panel switching off: a zap falling from 1.6 kHz to a hum."""
    n = secs(0.35)
    t = np.arange(n) / SR
    x = osc(1600 * np.exp(-t / 0.08) + 90) * env(n, 0.001, 0.12)
    return x + highpass(noise(n), 4000) * env(n, 0.0005, 0.01) * 0.3


def shimmer(midis, gap=0.06):
    """Bells up an arpeggio, a hair apart (the end card's sparkle)."""
    return mixdown(*[(ding(m), k * gap, 1.0) for k, m in enumerate(midis)])


def riser(dur=1.2, lo=300, hi=6000):
    """Into a drop: high noise swelling (a reversed cymbal) and a sine climbing."""
    n = secs(dur)
    t = np.arange(n) / SR
    u = t / dur
    air = highpass(noise(n), 5000) * u ** 3
    tone = osc(lo * (hi / lo) ** (u ** 2) * 0.25) * u ** 2 * 0.3
    return (air + tone) * np.clip((dur - t) / 0.01, 0, 1)


def tape_stop(x, t0, length=0.5):
    """The music slows to a stop from t0 over `length` seconds, then silence.
    x is stereo (2, n) or mono; returns a copy."""
    y = np.atleast_2d(x).astype(float).copy()
    i0, L = secs(t0), secs(length)
    if i0 >= y.shape[1]:
        return y if np.ndim(x) == 2 else y[0]
    u = np.arange(L) / L
    pos = i0 + L * (1 - (1 - u) ** 3) / 3                                 # integral of the speed (1 - u)^2
    for c in range(y.shape[0]):
        seg = np.interp(pos, np.arange(y.shape[1]), y[c]) * (1 - u) ** 0.5
        y[c, i0:i0 + L] = seg[: max(0, y.shape[1] - i0)]
    y[:, i0 + L:] = 0
    return y if np.ndim(x) == 2 else y[0]


def rewind(dur=0.7):
    """A tape rewind: warbling chirps that speed up, under a hiss."""
    n = secs(dur)
    t = np.arange(n) / SR
    rate = 6 + 30 * (t / dur) ** 1.5                                      # chirps per second, accelerating
    ph = np.cumsum(rate) / SR
    f = 600 + 2400 * (ph % 1.0) ** 0.6
    chirp = osc(f) * (0.6 + 0.4 * np.sin(2 * np.pi * ph))
    hiss = band(noise(n), 2500, 9000) * 0.35
    return (band(chirp, 300, 5000) + hiss) * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6 * 0.8


# ================================================================== dynamics ==

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
    """The gain a feed-forward compressor applies (x mono or stereo (2, n))."""
    lvl = follow(np.max(np.abs(np.atleast_2d(x)), axis=0), attack, release)
    lvl_db = 20 * np.log10(np.maximum(lvl, 1e-6))
    over = np.maximum(lvl_db - thresh_db, 0)
    return 10 ** ((-over * (1 - 1 / ratio) + makeup_db) / 20)


def true_peak_per_sample(x, over=4):
    """|x| at 4x oversampling, the worst of each sample's four, all channels."""
    x = np.atleast_2d(x)
    up = signal.resample_poly(x, over, 1, axis=1)
    return np.max(np.abs(up), axis=0)[: x.shape[1] * over].reshape(-1, over).max(axis=1)


def true_peak(x):
    """True peak in dBTP (4x oversampled)."""
    return db(float(np.max(true_peak_per_sample(x))))


def limit_gain(x, ceiling_db=-1.2, look=0.003, release=0.08):
    """A true-peak lookahead limiter's gain: held over the lookahead, a smooth
    attack, a slow release. The ceiling sits a hair under the target so the
    smoothing never overshoots it."""
    ceil = 10 ** (ceiling_db / 20)
    la = max(3, int(look * SR))
    need = np.minimum(1.0, ceil / np.maximum(true_peak_per_sample(x), 1e-9))
    held = minimum_filter1d(need, size=2 * la + 1)
    hop = 16                                                              # release at a 3 kHz control rate
    hc = np.pad(held, (0, -len(held) % hop), mode='edge').reshape(-1, hop).min(axis=1)
    rel = np.exp(-1 / (release * SR / hop))
    g = np.empty_like(hc)
    cur = 1.0
    for i, h in enumerate(hc):
        cur = h if h < cur else h + (cur - h) * rel
        g[i] = cur
    g = np.minimum(np.repeat(g, hop)[: len(held)], held)
    w = np.hanning(la) / np.hanning(la).sum()
    return np.minimum(np.convolve(g, w, 'same'), held)


def limiter(x, ceiling_db=-1.0, margin_db=0.2):
    return x * limit_gain(x, ceiling_db - margin_db)


def kweight(x):
    """BS.1770 K-weighting (the 48 kHz coefficients): a high shelf, then a high-pass."""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, np.atleast_2d(x), axis=1), axis=1)


def lufs(x):
    """Integrated loudness, ITU-R BS.1770-4 (K-weighting, 400 ms blocks, 75 %
    overlap, -70 LUFS absolute and -10 LU relative gates)."""
    y = kweight(x)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    if y.shape[1] < blk:
        return -np.inf
    sq = np.cumsum(np.pad(y ** 2, ((0, 0), (1, 0))), axis=1)
    starts = np.arange(0, y.shape[1] - blk + 1, hop)
    z = ((sq[:, starts + blk] - sq[:, starts]) / blk).sum(axis=0)
    l = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    z = z[l > -70]
    if not len(z):
        return -np.inf
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    l = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    return -0.691 + 10 * np.log10(z[l > rel].mean())


def loudness_windows(x, win=0.5):
    """Ungated K-weighted loudness (LUFS) of each `win`-second window, and the
    plain RMS (dBFS) of each, as two lists."""
    y = kweight(x)
    x = np.atleast_2d(x)
    n = int(win * SR)
    k_l, r_l = [], []
    for i in range(0, x.shape[1], n):
        z = np.mean(y[:, i:i + n] ** 2, axis=1).sum()
        k_l.append(-0.691 + 10 * np.log10(max(z, 1e-12)))
        r_l.append(db(rms(x[:, i:i + n])))
    return k_l, r_l


def span_loudness(x, t0, t1):
    """Ungated K-weighted loudness of [t0, t1) seconds."""
    a, b = secs(t0), secs(t1)
    if b - a < 10:
        return -np.inf
    y = kweight(np.atleast_2d(x)[:, a:b])
    return -0.691 + 10 * np.log10(max(np.mean(y ** 2, axis=1).sum(), 1e-12))


def db(x):
    return 20 * np.log10(max(1e-9, float(x)))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if np.size(x) else 0.0


# ===================================================================== mixing ==

class Bus:
    """A stereo bus `dur` seconds long (plus a tail so late sounds can ring
    past the end before the cut). add() places a sound at a time; at() at a
    frame."""

    def __init__(self, dur, tail=4.0):
        self.n = secs(dur)
        self.x = np.zeros((2, self.n + secs(tail)))
        self.log = []                                     # (t, name, gain, pan) of everything placed

    def add(self, x, t, gain=1.0, pan=0.0, name=None):
        i = secs(t)
        if i >= self.n or i + np.shape(x)[-1] <= 0:
            return
        s = np.asarray(x, float)
        a = (pan + 1) * np.pi / 4
        s = np.stack([s * np.cos(a), s * np.sin(a)]) if s.ndim == 1 else s * np.array([[np.cos(a)], [np.sin(a)]]) * math.sqrt(2)
        if i < 0:
            s, i = s[:, -i:], 0
        s = s[:, : self.x.shape[1] - i]
        self.x[:, i:i + s.shape[1]] += s * gain
        if name:
            self.log.append((t, name, gain, pan))

    def at(self, x, frame, fps, gain=1.0, pan=0.0, name=None, dt=0.0):
        """Place at a timeline frame (1-based: frame 1 is t = 0)."""
        self.add(x, (frame - 1) / fps + dt, gain, pan, name)

    def stereo(self):
        return self.x[:, : self.n].copy()


def write_wav(path, x, sr=SR, bits=24):
    """Stereo (2, n) or mono float in [-1, 1] -> PCM WAV."""
    x = np.atleast_2d(x)
    if _sf is not None:
        _sf.write(path, np.clip(x, -1, 1).T, sr, subtype='PCM_24' if bits == 24 else 'PCM_16')
        return
    full = 2 ** (bits - 1) - 1
    pcm = np.round(np.clip(x, -1, 1 - 2 ** -(bits - 1)) * full).astype('<i4').T.copy()
    b = pcm.view(np.uint8).reshape(-1, 4)[:, :bits // 8].tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(x.shape[0])
        w.setsampwidth(bits // 8)
        w.setframerate(sr)
        w.writeframes(b)


# ====================================================================== voice ==

def read_wav(path):
    """Any PCM/float WAV -> (mono float64, its sample rate)."""
    if _sf is not None:
        x, sr = _sf.read(path, dtype='float64', always_2d=True)
        return x.mean(axis=1), sr
    with wave.open(path) as w:
        width, ch, sr = w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if width == 2:
        x = np.frombuffer(raw, '<i2').astype(np.float64) / 32768
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        x = (b[:, 0].astype(np.int32) | b[:, 1].astype(np.int32) << 8 | b[:, 2].astype(np.int8).astype(np.int32) << 16) / 8388608
    else:
        raise ValueError(f'{path}: {8 * width}-bit WAV needs soundfile (install it in the venv)')
    return x.reshape(-1, ch).mean(axis=1), sr


def resample(x, sr):
    """To SR."""
    if sr == SR:
        return x
    g = math.gcd(SR, int(sr))
    return signal.resample_poly(x, SR // g, int(sr) // g)


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
    if not len(fr):
        return rms(x)
    r = np.sqrt(np.mean(fr ** 2, axis=1))
    keep = r > r.max() * 10 ** (floor_db / 20)
    return float(np.sqrt(np.mean(fr[keep] ** 2)))


VOICE_RMS = 10 ** (-19 / 20)      # every line levelled to this speech RMS


def prep_voice(x, sr, level=VOICE_RMS):
    """A TTS line, ready to mix: 48 kHz, high-pass 90 Hz, +2.5 dB presence at
    3 kHz, -1.5 dB box at 250 Hz, levelled, 2.5:1 compression, re-levelled."""
    x = resample(x, sr)
    x = highpass(x, 90, 2)
    x = peaking(x, 3000, 2.5, 0.9)
    x = peaking(x, 250, -1.5, 1.0)
    x = x * np.clip(level / max(speech_rms(x), 1e-6), 10 ** (-12 / 20), 10 ** (12 / 20))
    x = x * comp_gain(x, thresh_db=-22, ratio=2.5, attack=0.005, release=0.1)
    return x * level / max(speech_rms(x), 1e-6)


def speech_mask(voice, level=VOICE_RMS, thresh_db=-24):
    """Per sample: is the voice speaking (10 ms RMS within thresh_db of its level)?"""
    w = int(0.01 * SR)
    r = np.sqrt(np.convolve(voice ** 2, np.ones(w) / w, 'same'))
    return r > level * 10 ** (thresh_db / 20)


def sidechain(voice, level=VOICE_RMS, thresh_db=-24, hold=0.15, look=0.03, attack=0.04, release=0.25):
    """How far to duck the bed under the voice, per sample, 0 (not at all) .. 1
    (fully). Held `hold` s across the gaps between words, starts `look` s before
    the voice, ~`attack` s down and ~`release` s back up."""
    n = len(voice)
    hop = SR // 1000
    active = speech_mask(voice, level, thresh_db)[::hop].astype(float)
    h, k = int(hold * 1000), int(look * 1000)
    half = (h + k) // 2
    cm = maximum_filter1d(active, size=2 * half + 1)          # max over [i - half, i + half]
    shift = h - half                                          # -> [i - hold, i + look]
    if shift > 0:
        active = np.concatenate([np.full(shift, cm[0]), cm[:-shift]])
    else:
        active = cm
    a_a, a_r = np.exp(-1 / (attack * 1000)), np.exp(-1 / (release * 1000))
    depth = np.empty_like(active)
    cur = 0.0
    for i, v in enumerate(active):
        cur = v + (cur - v) * (a_a if v > cur else a_r)
        depth[i] = cur
    return np.interp(np.arange(n), np.arange(len(depth)) * hop, depth)


def duck(bed, depth, duck_db=-9.0, mid_dip_db=-3.0, lo=1000, hi=5000):
    """The bed (stereo) under the voice: down duck_db, and mid_dip_db more in
    lo-hi Hz where the words live."""
    g = 10 ** (duck_db * depth / 20)
    keep = 10 ** (mid_dip_db * depth / 20)
    mid = signal.sosfiltfilt(signal.butter(2, [lo, hi], 'bandpass', fs=SR, output='sos'), bed, axis=1)
    return (bed - mid * (1 - keep)) * g
