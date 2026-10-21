"""The film's sound: music on the film's beat grid, an effect on the frame of
every timeline event, the voiceover on top with the bed ducked under it,
mastered to -14 LUFS and -1 dBTP. All synthesised (src/synth.py), no samples.

    python3 src/timeline.py                  # first: writes src/timeline.json
    cache/venv/bin/python src/sound.py       # venv from templates/sound/setup-venv.sh

Writes
  out/sound.wav         the final mix, 48 kHz stereo 24-bit, exactly FRAMES/FPS long
  out/music.wav         the bed alone (music + effects, no voice, no ducking), same staging
  out/sound-notes.txt   loudness per section and per half second, LUFS, true peak,
                        every event placed and when, the duck under every VO line
  reviews/sound.png     waveform + loudness per half second, events and VO lines marked

Everything that has a time comes from src/timeline.json. A new film edits
three things here: MUSIC defaults (or T.MUSIC in the timeline), PATTERN (the
groove) and EVENT_SFX (one row per event kind). The arrangement:
  start .. MUSIC.drop     a soft pad and ticking hats only, a riser into the drop
  drop .. MUSIC.stop      the groove (drop lands with a kick and a brass stab)
  stop                    tape stop: drums out; a dark pad holds
  MUSIC.back (optional)   the groove comes back
  MUSIC.ring .. end       the final chord rings out; the bed fades from MUSIC.fade
Runs without a voiceover (prints a warning): run src/voice.py for one.
"""
import json
import os
import sys
from types import SimpleNamespace

import numpy as np

SRC = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(SRC)
sys.dont_write_bytecode = True
sys.path.insert(0, SRC)
import synth as S  # noqa: E402

T = SimpleNamespace(**json.load(open(os.path.join(SRC, 'timeline.json'))))
SR = S.SR
FPS, BEAT_F = T.FPS, T.BEAT
BEAT = BEAT_F / FPS                   # seconds a beat
STEP = BEAT / 4                       # a sixteenth
DUR = T.FRAMES / FPS
N = S.secs(DUR)
W_UI = getattr(T, 'W', 1920)
RECTS = getattr(T, 'RECTS', {}) or {}
HOPS = getattr(T, 'HOPS', []) or []
VO = getattr(T, 'VO', []) or []

# Music settings: the timeline's MUSIC over these defaults. `stop`, `back`,
# `ring`, `fade` and `final` are optional timeline fields; missing events are
# simply skipped.
MUSIC = dict(
    chords=[(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])],   # Am F C G
    drop='pop',            # event kind the groove starts on
    stop='hud-off',        # drums out with a tape stop
    back=None,             # event kind the groove comes back on (None: it does not)
    ring='endcard',        # the final chord starts ringing
    fade='fade',           # the bed fades from here to the end (the voice never fades)
    final=None,            # (bass, chord) of the last chord; None = the first bar's
    duck_db=-9.0,          # music + effects under the voice
    mid_dip_db=-3.0,       # and this much more at 1-5 kHz, where the words live
    lufs=-14.0,
    bed_under_voice_db=-5.0,   # the groove's level away from speech, against the voice's speech level
    ceiling_dbtp=-1.0,
)
MUSIC.update(getattr(T, 'MUSIC', {}) or {})
CHORDS = [(int(b), [int(m) for m in c]) for b, c in MUSIC['chords']]
FINAL = MUSIC['final'] or CHORDS[0]

# The groove, in sixteenths of a 4/4 bar (0-15). Afro-pop by default.
PATTERN = dict(
    kick=(0, 6, 8, 14),
    clap=(4, 12),
    rim=(3, 7, 11, 15),
    hat=(2, 6, 10, 14),                                   # off-beat eighths
    bass=((0, 0), (3, 7), (6, 12), (10, 0), (13, 7)),     # (step, semitones over the bar's bass note)
    keys=(2, 10),                                         # soft chord stabs
    pluck=(2, 5, 7, 9, 13, 15),                           # lead plucks, only between VO lines
    talking_drum_bars=2,                                  # a talking-drum fill every n bars
)


def t_of(frame):
    return (frame - 1) / FPS


def beat_t(b):
    return b * BEAT


def ev_t(kind):
    """Time of the first event of a kind, or None."""
    if not kind:
        return None
    e = next((e for e in T.EVENTS if e['kind'] == kind), None)
    return None if e is None else t_of(e['f'])


DROP_T = ev_t(MUSIC['drop'])
if DROP_T is None:
    print(f"warning: no '{MUSIC['drop']}' event for the drop; the groove starts at once")
    DROP_T = 0.0
FADE_T = ev_t(MUSIC['fade'])
FADE_T = DUR if FADE_T is None else FADE_T
RING_T = ev_t(MUSIC['ring'])
RING_T = FADE_T if RING_T is None else RING_T
STOP_T = ev_t(MUSIC['stop'])
BACK_T = ev_t(MUSIC['back'])
GROOVE = [(DROP_T, STOP_T if STOP_T is not None else RING_T)]
if BACK_T is not None and STOP_T is not None and BACK_T < RING_T:
    GROOVE.append((BACK_T, RING_T))
SECTIONS = [(0.0, 'intro'), (DROP_T, 'groove')]
if STOP_T is not None:
    SECTIONS.append((STOP_T, 'drums out'))
if len(GROOVE) > 1:
    SECTIONS.append((BACK_T, 'groove again'))
SECTIONS += [(RING_T, 'ring out'), (FADE_T, 'fade')]
SECTIONS = sorted({t: name for t, name in SECTIONS if t < DUR}.items())


def section(t):
    if t < DROP_T - 1e-6:
        return 'intro'
    if any(a - 1e-6 <= t < b - 1e-6 for a, b in GROOVE):
        return 'groove'
    if t >= RING_T - 1e-6:
        return 'ring'
    return 'quiet'


# ------------------------------------------------------------ the voice ---
# Read first: the arrangement keeps the lead parts out of the way of the words.
VO_DIR = os.path.join(STUDIO, 'cache', 'vo', T.VOICE)
voice = np.zeros(N)
VO_PLACED, VO_MISSING = [], []
for v in VO:
    path = os.path.join(VO_DIR, v['id'] + '.wav')
    if not os.path.exists(path):
        VO_MISSING.append(v['id'])
        continue
    x = S.prep_voice(*S.read_wav(path))
    i = S.secs(t_of(v['f']))
    x = x[: max(0, N - i)]
    voice[i:i + len(x)] += x
    VO_PLACED.append(dict(v, t0=t_of(v['f']), t1=t_of(v['f']) + len(x) / SR))
if VO and not VO_PLACED:
    print(f'warning: no voiceover in {os.path.relpath(VO_DIR, STUDIO)}/ (run src/voice.py, then '
          'python3 src/timeline.py); mixing music and effects only')
elif VO_MISSING:
    print(f'warning: VO lines with no wav, skipped: {", ".join(VO_MISSING)}')
VO_SPANS = [(v['t0'], v['t1']) for v in VO_PLACED]


def speaking(t0, t1=None, pre=0.08, post=0.1):
    """Does [t0, t1] touch a VO line (with a little margin)?"""
    t1 = t0 if t1 is None else t1
    return any(t1 >= a - pre and t0 <= b + post for a, b in VO_SPANS)


# ------------------------------------------------------------ the music ---
# music_a holds everything that starts before the stop (it tape-stops there);
# music_b everything after.
music_a, music_b = S.Bus(DUR), S.Bus(DUR)


def M(x, t, gain=1.0, pan=0.0):
    (music_a if STOP_T is None or t < STOP_T else music_b).add(x, t, gain, pan)


def chord_at(t):
    return CHORDS[int(t / BEAT // 4) % len(CHORDS)]


# The pad, bar by bar, cut where the sections change: soft and dark in the
# intro, fuller in the groove, darker with the drums out, none in the ring
# (the final chord takes over there).
PAD = dict(intro=(0.1, 800), groove=(0.2, 1400), quiet=(0.18, 700))
cuts = sorted({DROP_T, RING_T, DUR} | {t for g in GROOVE for t in g if t is not None})
bars = int(np.ceil(T.BEATS / 4))
for bar in range(bars):
    t0, t1 = beat_t(bar * 4), min(DUR, beat_t(bar * 4 + 4))
    root, chord = CHORDS[bar % len(CHORDS)]
    edges = [t0] + [c for c in cuts if t0 < c < t1] + [t1]
    for a, b in zip(edges, edges[1:]):
        sec = section(a)
        if sec == 'ring' or b - a < 0.02:
            continue
        g, cut = PAD[sec]
        hit = sec == 'groove' and any(abs(a - g0) < 1e-6 for g0, _ in GROOVE)
        M(S.pad(chord + [chord[0] + 12], b - a + 0.3, cut, attack=0.02 if hit else 0.25), a, g)

# Into each groove: a riser; on it: a kick, a sub and a brass stab of its chord.
for g0, _ in GROOVE:
    if g0 <= 0:
        continue
    root, chord = chord_at(g0)
    r = min(1.2, BEAT * 1.5, g0)
    M(S.riser(r), g0 - r, 0.16)
    M(S.kick(), g0, 1.0)
    M(S.bass(S.note_hz(root - 12), 0.8), g0, 0.5)
    M(S.brass_stab([m + 12 for m in chord], 0.4), g0, 0.32, 0.1)

# The beat grid, a sixteenth at a time.
SK, SC, SR_ = S.kick(), S.clap(), S.rim()
PLUCKS = []
for k in range(T.BEATS * 4):
    t = k * STEP
    if t >= DUR:
        break
    bar, s = divmod(k, 16)
    root, chord = CHORDS[bar % len(CHORDS)]
    sec = section(t)
    talk = speaking(t, t + 0.12)
    if sec == 'intro':
        # Ticking hats, eighths, the beat a little stronger.
        if s % 2 == 0:
            M(S.lowpass(S.hat(), 9000), t, 0.22 if s % 4 == 0 else 0.13, 0.25)
        continue
    if sec == 'quiet':
        # Drums out: a low, filtered log drum keeps time on the beat.
        if s % 4 == 0:
            M(S.lowpass(S.log_drum(S.note_hz(root - 12)), 400), t, 0.45)
        continue
    if sec == 'ring':
        continue
    if abs(t - DROP_T) < 1e-6 or (BACK_T is not None and abs(t - BACK_T) < 1e-6):
        pass                                             # the drop's own kick is already there
    elif s in PATTERN['kick']:
        M(SK, t, 0.85)
    if s in PATTERN['clap']:
        M(SC, t, 0.28 if talk else 0.45, 0.1)
    if s in PATTERN['rim'] and not talk:
        M(SR_, t, 0.22, -0.35)
    if s in PATTERN['hat']:
        M(S.hat(), t, 0.3, -0.2)
    M(S.shaker(s % 2 == 1), t, 0.11 if talk else 0.16, 0.4)
    for step, iv in PATTERN['bass']:
        if s == step:
            M(S.log_drum(S.note_hz(root - 12 + iv)), t, 0.55)
    if s in PATTERN['keys']:
        M(S.keys_chord([m + 12 for m in chord], 0.35, 0.6), t, 0.12 if talk else 0.2, -0.15)
    # Lead plucks only where nobody is talking (and their ring clears the next word).
    if s in PATTERN['pluck'] and not speaking(t, t + 0.15, pre=0.05, post=0.05):
        tone = chord[(s * 7 + bar) % len(chord)] + 12 + (12 if s in (9, 11, 15) else 0)
        M(S.pluck(S.note_hz(tone), 0.45, 0.6), t, 0.3, 0.3 if s % 2 else -0.3)
        PLUCKS.append(t)
    # A talking-drum answer at the end of every n-th bar, in a gap.
    n_td = PATTERN['talking_drum_bars']
    if n_td and s == 10 and bar % n_td == n_td - 1 and not speaking(t, t + 4 * STEP):
        M(S.talking_drum(STEP), t, 0.45, 0.25)

# The ring: the final chord, held to the end; the fade (below) takes it down.
if RING_T < DUR:
    root, chord = FINAL
    hold = DUR - RING_T + 0.5
    M(S.pad(chord + [chord[0] + 12], hold, 1800, attack=0.05, release=0.6), RING_T, 0.2)
    M(S.keys_chord([m + 12 for m in chord], min(hold, 4.0), 1.0, strum=0.02), RING_T, 0.28)
    M(S.bass(S.note_hz(root - 12), hold, 300) * S.env(S.secs(hold), 0.004, hold * 0.5), RING_T, 0.35)
    M(S.choir(chord + [chord[1] + 12], hold), RING_T + 0.1, 0.12, -0.1)

music = music_a.stereo()
if STOP_T is not None:
    music = S.tape_stop(music, STOP_T, min(0.5, BEAT))
music = music + music_b.stereo()

# --------------------------------------------------------------- effects ---
# ONE table: event kind -> the layers it makes, each (sound, dt seconds after
# the event's frame, gain, pan). A new film edits this table only. Kinds not
# in it are listed in the notes as having no sound.
RUN_NOTES = [72, 76, 79, 84]          # C E G C: each step of a run a note higher


def runs(kind, gap_beats=2.0):
    """Index of each event of `kind` within its run (events closer than gap_beats)."""
    out, last, i = {}, None, 0
    for e in T.EVENTS:
        if e['kind'] != kind:
            continue
        i = i + 1 if last is not None and e['f'] - last <= gap_beats * BEAT_F else 0
        out[id(e)] = i
        last = e['f']
    return out


RUN = {k: runs(k) for k in ('press', 'step', 'ding')}
HOP_T0 = {h['t0']: h for h in HOPS}
HOP_T1 = {h['t1']: h for h in HOPS}


def pan_x(x_px):
    return float(np.clip((x_px - W_UI / 2) / (W_UI / 2), -1, 1)) * 0.6


def pan_of(e):
    """Pan from the event's target rect, or its hop's landing point."""
    r = RECTS.get(e.get('target') or e.get('on') or '')
    if r:
        return pan_x(r['x'] + r['w'] / 2)
    h = HOP_T0.get(e['f']) or HOP_T1.get(e['f'])
    if h and isinstance(h.get('to'), (list, tuple)):
        return pan_x(h['to'][0])
    return 0.0


def takeoff(e):
    h = HOP_T0.get(e['f'], {})
    big = h.get('apex', 0) >= 1.0 or e.get('spin', 0)
    air = (h['t1'] - h['t0']) / FPS if h else 0.5
    out = [(S.boing(), 0, 0.32, pan_of(e))]
    if big:                                               # whooshes on big leaps
        out.append((S.whoosh(min(0.8, air + 0.15), True, 500, 3500), 0.02, 0.3, pan_of(e)))
    return out


def press(e):
    i = RUN['press'][id(e)]
    return [(S.click(), 0, 0.55, pan_of(e)), (S.blip(RUN_NOTES[i % 4] + 12), 0.04, 0.16, pan_of(e))]


def hud_off(e):
    panels = e.get('panels') or len(RECTS) or 5           # a zap per falling panel
    return [(S.power_down(), i * 0.07, 0.28 * (1 - i * 0.6 / panels), (-1) ** i * min(0.6, 0.15 * i))
            for i in range(panels)]


EVENT_SFX = {
    'knock':   lambda e: [(S.knock(), 0, 0.55, 0)],
    'pop':     lambda e: [(S.shatter(), 0, 0.85, 0)],                      # the glass breaks, the beat drops
    'press':   press,                                                      # keycap click + UI blip, rising in a run
    'money':   lambda e: [(S.cash(), 0, 0.8, pan_of(e))],
    'takeoff': takeoff,                                                    # boing (+ whoosh on a big leap)
    'land':    lambda e: [(S.pomf({'world': 70, 'hud': 95, 'phone': 120}.get(e.get('z'), 95)), 0, 0.8, pan_of(e))],
    'hud-off': hud_off,
    'endcard': lambda e: [(S.shimmer([m + 12 for m in FINAL[1]] + [FINAL[1][0] + 24]), 0, 0.22, 0)],
    'fade':    lambda e: [],                                               # the music does the fade
    # Kinds the demo does not use, ready for a new film:
    'step':    lambda e: [(S.ding(RUN_NOTES[RUN['step'][id(e)] % 4]), 0.03, 0.42, -0.3), (S.fill_up(), 0, 0.18, -0.3)],
    'ding':    lambda e: [(S.ding(e.get('note', RUN_NOTES[RUN['ding'][id(e)] % 4])), 0, 0.4, 0)],
    'peel':    lambda e: [(S.peel(), 0, 0.55, 0)],
    'whoosh':  lambda e: [(S.whoosh(e.get('secs', 1.0), True, 300, 4500), 0, 0.5, 0)],
    'bubble':  lambda e: [(S.pop(), 0, 0.5, pan_of(e))],
    'horn':    lambda e: [(S.horn(), 0, 0.32, pan_of(e))],
    'engine':  lambda e: [(S.engine(e.get('secs', 2.0), e.get('rev', False)), 0, 0.45, pan_of(e))],
    'clang':   lambda e: [(S.clang(), 0, 0.45, pan_of(e))],
    'coins':   lambda e: [(S.coins(), 0, 0.6, pan_of(e))],
    'spray':   lambda e: [(S.note_flick(), i * 2 / FPS, 0.7, 0.3 + 0.03 * i) for i in range(e.get('notes', 6))],
    'rewind':  lambda e: [(S.rewind(), 0, 0.45, 0)],
    'riser':   lambda e: [(S.riser(e.get('secs', 1.0)), -e.get('secs', 1.0), 0.35, 0)],   # ends on the frame
}

sfx = S.Bus(DUR)
PLACED, SILENT = [], set()
for e in T.EVENTS:
    fn = EVENT_SFX.get(e['kind'])
    if fn is None:
        SILENT.add(e['kind'])
        continue
    layers = fn(e)
    for x, dt, gain, p in layers:
        sfx.at(x, e['f'], FPS, gain, p, dt=dt)
    PLACED.append((e, len(layers)))
if SILENT:
    print(f'note: no sound for event kinds {sorted(SILENT)} (add them to EVENT_SFX)')

# ---------------------------------------------------------------- the mix ---
bed = music * S.comp_gain(music, -16, 2.5, 0.01, 0.2, 2) * 0.9 + sfx.stereo()
tt = np.arange(N) / SR
if FADE_T < DUR:                          # the bed fades to silence; the voice is never faded
    bed = bed * np.clip(1 - (tt - FADE_T) / (DUR - FADE_T), 0, 1) ** 1.5

if VO_PLACED:
    depth = S.sidechain(voice)
    # Level the bed against the voice: where the groove plays and nobody speaks
    # it sits MUSIC['bed_under_voice_db'] under the voice's speech level (then the duck takes it down).
    grooving = np.zeros(N, bool)
    for g0, g1 in GROOVE:
        grooving[S.secs(g0):S.secs(g1)] = True
    free = (depth < 0.02) & grooving & (tt < FADE_T)
    if free.sum() < SR // 4:                  # the voice covers the groove: use everything after the drop
        free = (depth < 0.02) & (tt > DROP_T) & (tt < FADE_T)
    if free.sum() > SR // 4:
        bed = bed * S.VOICE_RMS * 10 ** (MUSIC['bed_under_voice_db'] / 20) / max(S.rms(bed[:, free]), 1e-9)
    bed_d = S.duck(bed, depth, MUSIC['duck_db'], MUSIC['mid_dip_db'])
else:
    depth = np.zeros(N)
    bed_d = bed
vo2 = np.stack([voice, voice])            # centred
mix = vo2 + bed_d

# The master: a gentle glue compressor, then gain to the loudness target and a
# true-peak limiter, iterated until both hold. The same gain goes on the stems
# (for the measurements) and on the music-only file.
g_master = S.comp_gain(mix, -16, 1.8, 0.005, 0.15)
ceil = MUSIC['ceiling_dbtp'] - 0.2
gain = 1.0
for _ in range(8):
    pre = mix * g_master * gain
    g_lim = S.limit_gain(pre, ceil)
    L = S.lufs(pre * g_lim)
    if not np.isfinite(L) or abs(L - MUSIC['lufs']) < 0.1:
        break
    gain *= 10 ** ((MUSIC['lufs'] - L) / 20)
g_total = g_master * gain * g_lim
mix_out = mix * g_total
voice_out, bed_out = vo2 * g_total, bed_d * g_total
music_pre = bed * g_master * gain         # the un-ducked bed, same staging
music_out = music_pre * S.limit_gain(music_pre, ceil)

# ------------------------------------------------------------------ write ---
OUT, REV = os.path.join(STUDIO, 'out'), os.path.join(STUDIO, 'reviews')
os.makedirs(OUT, exist_ok=True)
os.makedirs(REV, exist_ok=True)
assert mix_out.shape == (2, N)
S.write_wav(os.path.join(OUT, 'sound.wav'), mix_out)
S.write_wav(os.path.join(OUT, 'music.wav'), music_out)

# ---------------------------------------------------------------- measure ---
L_mix, tp = S.lufs(mix_out), S.true_peak(mix_out)
L_music, tp_music = S.lufs(music_out), S.true_peak(music_out)
clip = int(np.sum(np.abs(mix_out) >= 1.0))
HALF_K, HALF_R = S.loudness_windows(mix_out, 0.5)
ends = [t for t, _ in SECTIONS[1:]] + [DUR]
SEC_L = [(name, t0, t1, S.span_loudness(mix_out, t0, t1), S.span_loudness(music_out, t0, t1))
         for (t0, name), t1 in zip(SECTIONS, ends)]

# The duck, per line: the bed's level where the voice speaks, with and without
# the duck (same master gain), and the bed's level in the groove away from speech.
spoken = S.speech_mask(voice) if VO_PLACED else np.zeros(N, bool)
bed_plain = bed * g_total
rows = []
for v in VO_PLACED:
    a, b = S.secs(v['t0']), min(N, S.secs(v['t1']))
    m = spoken[a:b]
    if m.sum() < 10:
        continue
    vb, bb, bp = voice_out[0, a:b][m], bed_out[:, a:b][:, m], bed_plain[:, a:b][:, m]
    rows.append((v['id'], v['t0'], v['t1'], S.db(S.rms(vb)), S.db(S.rms(bb)), S.db(S.rms(bp)),
                 S.db(S.rms(bb)) - S.db(S.rms(bp)), S.db(S.rms(vb)) - S.db(S.rms(bb))))
in_groove = np.zeros(N, bool)
for g0, g1 in GROOVE:
    in_groove[S.secs(g0):S.secs(g1)] = True
in_groove &= tt < FADE_T
far = in_groove & (depth < 0.02)
near = in_groove & spoken
bed_far = S.db(S.rms(bed_out[:, far])) if far.any() else float('nan')
bed_near = S.db(S.rms(bed_out[:, near])) if near.any() else float('nan')

L = [f'{getattr(T, "NAME", "film")}: sound notes (written by src/sound.py)', '',
     f'sound.wav  {SR} Hz stereo 24-bit, {mix_out.shape[1]} samples = {mix_out.shape[1] / SR:.4f} s = '
     f'{mix_out.shape[1] / SR * FPS:.2f} frames (timeline: {T.FRAMES} frames at {FPS} fps)',
     f'  integrated {L_mix:.1f} LUFS (BS.1770-4, own meter; target {MUSIC["lufs"]:.0f}), '
     f'true peak {tp:.2f} dBTP (4x oversampled; ceiling {MUSIC["ceiling_dbtp"]:.0f}), {clip} clipped samples',
     f'music.wav  the bed alone, no voice, no ducking, same staging: {L_music:.1f} LUFS, {tp_music:.2f} dBTP', '',
     f'Grid: {BEAT:.3f} s a beat ({BEAT_F} frames), {T.BEATS} beats; chords {[c[0] for c in CHORDS]} a bar each, cycling.',
     'Sections (ungated K-weighted loudness, LUFS):   mix   bed alone (music.wav)']
for name, t0, t1, l, lb in SEC_L:
    L.append(f'  {name:13} {t0:6.2f}-{t1:6.2f} s  {l:6.1f}  {lb:6.1f}')
intro = next((r for r in SEC_L if r[0] == 'intro'), None)
groove = next((r for r in SEC_L if r[0] == 'groove'), None)
if intro and groove:
    L.append(f'  the drop: groove {groove[3] - intro[3]:+.1f} LU over the intro in the mix, '
             f'{groove[4] - intro[4]:+.1f} LU in the bed alone')
L += ['', 'Loudness per half second (LUFS, ungated / RMS dBFS):']
for i in range(0, len(HALF_K), 6):
    L.append('  ' + '  '.join(f'{j * 0.5:4.1f}s {HALF_K[j]:6.1f}/{HALF_R[j]:5.1f}' for j in range(i, min(i + 6, len(HALF_K)))))
L += ['', f'Events ({len(PLACED)} placed, sample = (frame - 1) / FPS * {SR}):']
for e, n in PLACED:
    extra = {k: v for k, v in e.items() if k not in ('f', 'kind')}
    L.append(f'  f{e["f"]:<5} {t_of(e["f"]):6.3f} s  {e["kind"]:9} {n} layer(s)  {extra if extra else ""}')
if SILENT:
    L.append(f'  no sound (not in EVENT_SFX): {", ".join(sorted(SILENT))}')
L += ['', f'Lead plucks ({len(PLUCKS)}), only between VO lines, at (s): ' + ' '.join(f'{x:.2f}' for x in PLUCKS), '']
if VO_PLACED:
    L += [f'Voice: {T.VOICE}, {len(VO_PLACED)}/{len(VO)} lines, 48 kHz, HP 90 Hz, +2.5 dB @ 3 kHz, -1.5 dB @ 250 Hz, '
          'levelled, 2.5:1, centred.',
          f'Duck: bed {MUSIC["duck_db"]:.0f} dB under the voice ({MUSIC["mid_dip_db"]:+.0f} dB more at 1-5 kHz), '
          '150 ms hold, 30 ms lookahead, ~40 ms down, ~250 ms up.',
          '  line          start    end  voice  bed(ducked)  bed(no duck)  duck  voice/bed  (RMS dBFS where the voice speaks)']
    for r in rows:
        L.append(f'  {r[0]:12} {r[1]:6.2f} {r[2]:6.2f} {r[3]:6.1f} {r[4]:12.1f} {r[5]:13.1f} {r[6]:5.1f} {r[7]:10.1f}')
    L.append(f'  groove bed level away from speech {bed_far:.1f} dBFS, under speech {bed_near:.1f} dBFS '
             f'({bed_near - bed_far:+.1f} dB)')
    if VO_MISSING:
        L.append(f'  missing wavs (skipped): {", ".join(VO_MISSING)}')
else:
    L.append(f'Voice: none found in {os.path.relpath(VO_DIR, STUDIO)}/ (run src/voice.py); no ducking.')

# ----------------------------------------------------------------- review ---
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    L += ['', 'reviews/sound.png: skipped (no PIL in this venv; templates/sound/setup-venv.sh installs pillow)']

if Image is not None:
    Wd, LEFT, RIGHT = 1600, 64, 24
    PW = Wd - LEFT - RIGHT
    WAV_Y, WAV_H = 64, 220
    LUF_Y, LUF_H = WAV_Y + WAV_H + 40, 240
    Hd = LUF_Y + LUF_H + 70
    img = Image.new('RGB', (Wd, Hd), (14, 14, 18))
    d = ImageDraw.Draw(img)
    try:
        font, big = ImageFont.load_default(size=13), ImageFont.load_default(size=17)
    except TypeError:
        font = big = ImageFont.load_default()

    def X(t):
        return LEFT + t / DUR * PW

    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for v in VO_PLACED:                                       # VO lines shaded across both lanes
        for y0, h in ((WAV_Y, WAV_H), (LUF_Y, LUF_H)):
            od.rectangle([X(v['t0']), y0, X(v['t1']), y0 + h], fill=(0, 220, 130, 40), outline=(0, 220, 130, 110))
        od.text((X(v['t0']) + 3, WAV_Y + 3), v['id'], fill=(0, 240, 150, 255), font=font)
    img = Image.alpha_composite(img.convert('RGBA'), over).convert('RGB')
    d = ImageDraw.Draw(img)

    # Waveform: the bed in grey, the voice in green on top.
    for x_sig, colour in ((bed_out.mean(axis=0), (130, 140, 170)), (voice_out[0], (0, 200, 120))):
        for c in range(PW):
            a, b = int(c / PW * N), int((c + 1) / PW * N)
            seg = x_sig[a:b]
            if len(seg) and np.max(np.abs(seg)) > 1e-4:
                ym = WAV_Y + WAV_H / 2
                d.line([(LEFT + c, ym - seg.max() * WAV_H / 2), (LEFT + c, ym - seg.min() * WAV_H / 2)], fill=colour)
    d.rectangle([LEFT, WAV_Y, LEFT + PW, WAV_Y + WAV_H], outline=(60, 60, 70))

    # Loudness per half second: bars on a -45 .. -5 LUFS scale, the target dashed.
    def Y(l):
        return LUF_Y + LUF_H - (np.clip(l, -45, -5) + 45) / 40 * LUF_H

    d.rectangle([LEFT, LUF_Y, LEFT + PW, LUF_Y + LUF_H], outline=(60, 60, 70))
    for g in (-10, -20, -30, -40):
        d.line([(LEFT, Y(g)), (LEFT + PW, Y(g))], fill=(40, 40, 50))
        d.text((16, Y(g) - 7), f'{g}', fill=(140, 140, 150), font=font)
    for j, l in enumerate(HALF_K):
        x0, x1 = X(j * 0.5) + 2, X(min(DUR, j * 0.5 + 0.5)) - 2
        d.rectangle([x0, Y(l), x1, LUF_Y + LUF_H], fill=(90, 120, 220))
        d.text((x0, Y(l) - 15), f'{l:.0f}', fill=(200, 205, 230), font=font)
    for x in range(LEFT, LEFT + PW, 12):
        d.line([(x, Y(MUSIC['lufs'])), (x + 6, Y(MUSIC['lufs']))], fill=(240, 170, 60))

    # Sections (white, top) and events (orange ticks, named, staggered).
    for t0, name in SECTIONS:
        d.line([(X(t0), WAV_Y - 18), (X(t0), LUF_Y + LUF_H)], fill=(255, 255, 255))
        d.text((X(t0) + 3, WAV_Y - 20), name, fill=(255, 255, 255), font=font)
    for k, (e, _) in enumerate(PLACED):
        x = X(t_of(e['f']))
        d.line([(x, LUF_Y + LUF_H), (x, LUF_Y + LUF_H + 8)], fill=(240, 170, 60), width=2)
        d.line([(x, WAV_Y), (x, WAV_Y + WAV_H)], fill=(240, 170, 60), width=2)
        d.text((x - 10, LUF_Y + LUF_H + 10 + (k % 3) * 13), e['kind'], fill=(240, 170, 60), font=font)
    for s in range(0, int(DUR) + 1):
        d.text((X(s) - 6, LUF_Y - 18), f'{s}s', fill=(150, 150, 160), font=font)
    d.text((LEFT, 12), f'{getattr(T, "NAME", "film")}: sound.wav  {L_mix:.1f} LUFS  {tp:.1f} dBTP  {DUR:.2f} s  |  '
           'grey = bed, green = voice / VO lines, blue = loudness per 0.5 s, orange = events, dashed = target',
           fill=(230, 230, 235), font=big)
    img.save(os.path.join(REV, 'sound.png'))

notes = '\n'.join(L) + '\n'
open(os.path.join(OUT, 'sound-notes.txt'), 'w').write(notes)
print(notes)
print('\n'.join(os.path.join(OUT, n) for n in ('sound.wav', 'music.wav', 'sound-notes.txt'))
      + ('' if Image is None else '\n' + os.path.join(REV, 'sound.png')))
