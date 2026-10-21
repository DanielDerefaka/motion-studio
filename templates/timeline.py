"""The one timeline: every beat, hop, press, cut, line and sound in the film.

Copy to <studio>/src/timeline.py and replace the DEMO values. Every other
script reads it (Python imports it; Node, Blender and the sound read the
timeline.json it writes). Nothing else may hold a time or a UI position.

    python3 src/timeline.py          # writes src/timeline.json

Run it again after src/voice.py, so the captions get the real lengths of the
spoken lines (cache/vo/<voice>/lines.json).

Space is the product's screen at W x H UI pixels, top-left origin, laid flat
as a floor (the exploded screen). px() turns a UI pixel into metres.
"""
import json
import os
import re

NAME = 'demo-film'           # output name: out/<NAME>-<fmt>.mp4
FPS = 30
BPM = 100                    # pick so a beat is a whole number of frames: 100 -> 18, 120 -> 15
BEAT = round(FPS * 60 / BPM)
BEATS = 12
FRAMES = BEATS * BEAT        # 216 = 7.2 s
FORMATS = {'16x9': (1920, 1080), '9x16': (1080, 1920)}
W, H = 1920, 1080            # UI space (the product's own screen)
SCALE = 0.01                 # metres per UI pixel: a 1.8 m hero is 180 px tall

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def f(beat):
    """Frame number (1-based) of a beat, fractional beats allowed."""
    return int(round(beat * BEAT)) + 1


def px(x, y):
    """UI pixel -> (x, y) metres on the floor, screen centre at the origin."""
    return ((x - W / 2) * SCALE, (H / 2 - y) * SCALE)


def centre(r):
    return (r['x'] + r['w'] / 2, r['y'] + r['h'] / 2)


# ------------------------------------------------------------------- layout --
# The panels of the real UI in UI pixels. In a real film this comes from the
# product's live DOM (snapshot -> assets/ui/rects.json), never typed by hand.
RECTS_FILE = os.path.join(STUDIO, 'assets', 'ui', 'rects.json')
RECTS = json.load(open(RECTS_FILE)) if os.path.exists(RECTS_FILE) else {
    'panel-stats': dict(x=60, y=60, w=420, h=240),
    'btn-a': dict(x=700, y=900, w=140, h=120),
    'btn-b': dict(x=890, y=900, w=140, h=120),
    'btn-c': dict(x=1080, y=900, w=140, h=120),
}

# Heights (metres) of the exploded layers above the base slab (z = 0).
Z = dict(world=0.0, glass=0.03, hud=0.32, phone=0.72, tile=0.05, slab=0.05)

# --------------------------------------------------------------------- hero --
# Each hop: take-off frame, landing frame, landing point (UI px), the slab it
# lands on, the layer, apex height (m) above the higher end, front flips.
# Every hop lands on something that changes the picture. A hop that changes
# nothing is cut.
START = (960, 600)
HOPS = [
    dict(t0=f(2.5), t1=f(3), to=centre(RECTS['btn-a']), on='btn-a', z='hud', apex=0.9, spin=0),
    dict(t0=f(3.5), t1=f(4), to=centre(RECTS['btn-b']), on='btn-b', z='hud', apex=0.6, spin=0),
    dict(t0=f(4.4), t1=f(5), to=centre(RECTS['btn-c']), on='btn-c', z='hud', apex=1.4, spin=1),
]

# World footage cuts: (start frame, clip slug, seconds into the clip, speed).
CUTS = [(f(0), 'clip-a', 1.0, 1.0), (f(3), 'clip-b', 1.0, 1.0)]

# ------------------------------------------------------------------- events --
# Everything that happens on a frame. kind + args. The scene, the overlay and
# the sound all read this list; add kinds freely, each reader ignores the
# kinds it does not know.
EVENTS = [
    dict(f=f(0.5), kind='knock'),
    dict(f=f(1.5), kind='pop'),                 # the beat drops
    dict(f=f(3), kind='press', target='btn-a'),
    dict(f=f(4), kind='press', target='btn-b'),
    dict(f=f(5), kind='press', target='btn-c'),
    dict(f=f(5.2), kind='money', amount=500),
    dict(f=f(7), kind='hud-off'),
    dict(f=f(8), kind='endcard'),
    dict(f=f(10.8), kind='fade'),
]
for h in HOPS:
    EVENTS.append(dict(f=h['t0'], kind='takeoff', spin=h['spin']))
    EVENTS.append(dict(f=h['t1'], kind='land', z=h['z'], on=h['on']))
EVENTS.sort(key=lambda e: e['f'])


def event(kind, **match):
    return next(e for e in EVENTS if e['kind'] == kind and all(e.get(k) == v for k, v in match.items()))


# -------------------------------------------------------------------- voice --
# One clip per line or word: (beat it starts on, id, text). `say` is what the
# voice reads when the spelling would trip it (URLs, initials, prices).
VOICE = 'af_heart'           # Kokoro voice; see templates/voice/voice.py
VOICE_SPEED = 1.1
VO = [
    dict(beat=0.3, id='hook', text='This is the demo film.'),
    dict(beat=2.9, id='press', text='Press. Press. Press.'),
    dict(beat=8.2, id='end', text='Made with code, at example.com.', say='Made with code, at example dot com.'),
]
VO_LINES = os.path.join(STUDIO, 'cache', 'vo', VOICE, 'lines.json')
_secs = {}
if os.path.exists(VO_LINES):
    _secs = {m['id']: m['secs'] for m in json.load(open(VO_LINES))['lines']}
for v in VO:
    v['f'] = f(v['beat'])
    v['secs'] = _secs.get(v['id'], round(len(v['text']) / 15, 2))   # ~15 chars/s until voice.py runs
    v['f_end'] = v['f'] + int(round(v['secs'] * FPS))
VO_BY = {v['id']: v for v in VO}

# Captions: cards of fragments, each fragment from one VO clip. A fragment
# shows when its words are said; *stars* mark the accent words (set in the
# accent face with a swash under them). A card holds until the next card.
CAPTION_CARDS = [
    [('This is', 'hook'), ('*the demo film.*', 'hook')],
    [('Press.', 'press'), ('Press.', 'press'), ('*Press.*', 'press')],
    [('Made with code,', 'end'), ('at *example.com*', 'end')],
]


def caption_cards():
    cards = []
    for parts in CAPTION_CARDS:
        out = []
        for text, vid in parts:
            v = VO_BY[vid]
            plain = re.sub(r'\*', '', text)
            at = v['text'].find(plain)
            k = max(0, at) / max(1, len(v['text']))
            out.append(dict(f=v['f'] + int(round(k * v['secs'] * FPS * 0.92)), text=text, vo=vid))
        last = VO_BY[parts[-1][1]]
        cards.append(dict(f_in=out[0]['f'], f_out=last['f_end'] + 12, parts=out))
    for a, b in zip(cards, cards[1:]):
        a['f_out'] = min(a['f_out'], b['f_in'])
    return cards


CAPTIONS = caption_cards()

# ------------------------------------------------------------------ overlay --
# Lesson chips (top left): number in the accent face, title bold.
CHAPTERS = [dict(f_in=f(2.5), f_out=f(7), n='01', title='Press things')]

# Points callouts point at. {slab, at}: a UI px on a slab (None = its centre),
# followed in 3D through anchors.py. {obj}: an object's head (hero, vehicle).
# {screen: {fmt: [x, y]}}: a fixed point in output pixels (2D-only films).
ANCHORS = {
    'btn-a': dict(slab='btn-a', at=None),
    'btn-c': dict(slab='btn-c', at=None),
    'hero': dict(obj='hero'),
}

# A glass label on a leader line to an anchor. kind: 'label' (default),
# 'tip' (small chip), 'money' (a big number popping off the anchor, tone
# 'earn' or 'spend'). Hidden on a format whose camera has the anchor off screen.
CALLOUTS = [
    dict(id='a', anchor='btn-a', f_in=f(3), f_out=f(5.5), title='Button A', sub='The real label, from the product'),
    dict(id='paid', anchor='btn-c', f_in=f(5.2), f_out=f(6.6), kind='money', title='+500', tone='earn'),
]

# ------------------------------------------------------------------ cameras --
# Keys: frame, look (UI px or 'hero'), distance (m), elevation and yaw (deg),
# lens (mm), f-stop, optional z (look height, UI px like Z). 9:16 is its own
# composition with its own keys.
SHAKE = {'pop': 0.06}        # event kind -> camera shake amplitude (m)
CAMERA = [
    dict(f=f(0), look=(960, 560), dist=17.0, elev=34, yaw=-8, lens=40, fstop=8.0),
    dict(f=f(2), look='hero', dist=7.6, elev=24, yaw=-12, lens=50, fstop=2.8),
    dict(f=f(5.5), look='hero', dist=8.0, elev=24, yaw=8, lens=45, fstop=3.2),
    dict(f=f(8), look=(960, 600), dist=16.5, elev=33, yaw=-3, lens=40, fstop=8.0),
]
CAMERA_9X16 = [
    dict(f=f(0), look=(960, 600), dist=15.0, elev=40, yaw=-6, lens=36, fstop=8.0),
    dict(f=f(2), look='hero', dist=6.6, elev=24, yaw=-12, lens=45, fstop=2.8),
    dict(f=f(5.5), look='hero', dist=7.0, elev=26, yaw=8, lens=40, fstop=3.2),
    dict(f=f(8), look=(960, 640), dist=14.8, elev=39, yaw=-2, lens=36, fstop=8.0),
]

# --------------------------------------------------------------------- sound --
# The music is written on the same beat grid. One chord a bar (4 beats):
# (bass MIDI note, chord MIDI notes).
MUSIC = dict(
    chords=[(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])],
    drop='pop',              # the event the full groove starts on
    duck_db=-9.0,            # music + effects under the voice
)

# ----------------------------------------------------------------- the look --
# Every value here comes from style-guide.md (the look recipe), which comes
# from measuring the inspo (scripts/analyse-inspo.py + frame-stepping). The
# DEMO values below are neutral placeholders, not a house style: replace all.
# Sizes are fractions of the frame HEIGHT so 16:9 and 9:16 share one recipe;
# eases are cubic-bezier [x1, y1, x2, y2] read off the inspo's moves.
FONT_DIR = os.path.join(STUDIO, 'assets', 'fonts')
FONTS = dict(                # key -> font file in assets/fonts (None = system sans)
    display=None,            # e.g. os.path.join(FONT_DIR, 'Display-Bold.otf')
    body=None,
)
STYLE = dict(
    inspo=[],                # the analysis.json files these numbers came from
    bg='#101010', ink='#f2f2f2', accent='#7a7a7a', palette=[],
    type=dict(
        display=dict(font='display', weight=700, size=0.075, tracking=-0.02, line=1.0, case='none'),
        body=dict(font='body', weight=400, size=0.032, tracking=0.0, line=1.25, case='none'),
    ),
    # where and how on-screen text sits: plain | pill | box | underline | none
    caption=dict(style='plain', y=0.86, max_w=0.8, align='center', bg=None, radius=0, pad=0.012),
    # how things arrive and leave: kind rise | fade | mask | scale | blur | type | slide
    enter=dict(kind='fade', by='line', frames=8, stagger=2, ease=[0.25, 0.1, 0.25, 1.0], dist=0.03),
    exit=dict(kind='fade', frames=6, ease=[0.42, 0.0, 1.0, 1.0]),
    move=dict(ease=[0.65, 0.0, 0.35, 1.0], overshoot=0.0),      # camera / object moves
    cut=dict(kind='hard', frames=0),          # hard | flash | whip | dissolve | match
    hold_min_s=1.0,                           # shortest hold on a readable state
    texture=dict(grain=0.0, vignette=0.0, blur=0.0, chroma=0.0, bloom=0.0),
)
COLORS = dict(accent=STYLE['accent'], ink=STYLE['ink'], bg=STYLE['bg'])
END_LINE = 'The product line, in its own words.'
END_URL = 'example.com'


def to_json():
    keep = {k: v for k, v in globals().items()
            if k.isupper() and not k.startswith('_') and isinstance(v, (int, float, str, list, dict, tuple))}
    keep.pop('CAPTION_CARDS', None)
    return keep


if __name__ == '__main__':
    out = os.path.join(STUDIO, 'src', 'timeline.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(to_json(), open(out, 'w'), indent=1, ensure_ascii=False)
    print(f'{FRAMES} frames ({FRAMES / FPS:.1f} s), {len(EVENTS)} events, {len(HOPS)} hops, '
          f'{len(VO)} lines, {len(CAPTIONS)} captions, {len(CALLOUTS)} callouts -> {out}'
          + ('' if _secs else '  (no voice yet: run src/voice.py, then this again)'))
