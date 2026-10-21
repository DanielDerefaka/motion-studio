"""The one timeline: every beat, hop, press, cut, line and sound in the film.

"How PH Lifestyle works": 30 s, four lessons (stay alive, make money, spend
it, real people), each word of the voiceover landing on one of Tobi's beats.
The first film, "Just Hide the HUD", lives on in src-hide-the-hud/.

Read by the UI capture (via timeline.json), the world comp, the Blender
scene, the overlay, the voice and the sound. Run `python3 src/timeline.py`
to write timeline.json (after src/voice.py, so the captions get the real
lengths of the spoken lines).

Space is the game screen at 1920x1080 UI pixels, top-left origin, laid flat
as a floor (the exploded game screen). px() turns a UI pixel into metres.
"""
import json
import os
import re

FPS = 30
BPM = 100
BEAT = 18                    # frames per beat (0.6 s)
BEATS = 50
FRAMES = BEATS * BEAT        # 900 = 30 s
W, H = 1920, 1080
SCALE = 0.01                 # metres per UI pixel: Tobi (1.98 m) is 198 px tall

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECTS = json.load(open(os.path.join(STUDIO, 'assets', 'ui', 'rects.json')))
NAME = 'ph-lifestyle-explainer'


def f(beat):
    """Frame number (1-based) of a beat, fractional beats allowed."""
    return int(round(beat * BEAT)) + 1


def px(x, y):
    """UI pixel -> (x, y) metres on the floor, screen centre at the origin."""
    return ((x - W / 2) * SCALE, (H / 2 - y) * SCALE)


def centre(r):
    return (r['x'] + r['w'] / 2, r['y'] + r['h'] / 2)


HUD = RECTS['hud']
APPS = {a['app']: a for a in RECTS['phone']['apps']}
DOCK = {a['action']: a for a in RECTS['dock']}
PHONE = RECTS['phone']['host']

# Heights (metres) of the exploded layers above the world slab (z = 0).
Z = {
    'world': 0.0,
    'glass': 0.03,
    'hud': 0.32,        # HUD panels float above the world
    'phone': 0.72,      # the phone floats above the HUD
    'tile': 0.05,       # app tiles, dock buttons and nav buttons stand proud of their slab
    'slab': 0.05,       # slab thickness
}

# The needs panel grows forward so its rows become steps Tobi can land on.
NEEDS_GROW = 2.5
NEEDS_ORIGIN = (HUD['#hud-me']['x'], HUD['#hud-me']['y'])
NEED_ROWS = {'hunger': 70, 'energy': 90, 'vibe': 110, 'thirst': 130, 'social': 150, 'fun': 170}
NEED_BAR_X = 132             # middle of the bars, UI px (before growing)
MOOD_ROW = (110, 194)        # the mood line under the bars, UI px (before growing)


def grown(x, y):
    ox, oy = NEEDS_ORIGIN
    return (ox + (x - ox) * NEEDS_GROW, oy + (y - oy) * NEEDS_GROW)


# The four apps Tobi lands on, and the dock buttons that are their own tiles.
TILES = ['cars', 'property', 'boutique', 'hail']
DOCK_TILES = {'dock-jobs': 'work-hire', 'spray': 'spray'}

# World footage cuts: (start frame, clip slug, seconds into the clip, speed).
# Clips start 1.2 s in or later, after the game's "press H" hint has gone.
CUTS = [
    (f(0), 'market-day', 1.4, 1.0),
    (f(5.2), 'market-night', 1.2, 1.0),    # on the needs panel: the day goes by
    (f(11), 'jevinik', 1.2, 1.0),          # Eat
    (f(12), 'home', 1.2, 1.0),             # Sleep
    (f(13), 'club', 1.2, 1.0),             # Party
    (f(14), 'beach', 1.2, 1.0),            # Drink
    (f(16.2), 'ride-bus', 1.0, 1.0),       # on the danfo
    (f(20), 'hall-night', 1.0, 1.0),       # Jobs here: the hall
    (f(25), 'ride-drop', 1.6, 1.0),        # Cars
    (f(26), 'estate', 1.6, 1.0),           # Property
    (f(27), 'mall', 1.2, 1.0),             # Boutique
    (f(28), 'ride-drop', 4.2, 1.0),        # PH Ride
    (f(30), 'hall-night', 3.3, 1.0),       # the people in the hall
    (f(34.4), 'hall-high', 1.2, 0.6),      # pulling back over them, slowed to last to the end
]

# Tobi's path. Each hop: take-off frame, landing frame, landing point (UI px),
# the slab it lands on, apex height above the higher end, spins (front flips).
START = (960, 640)           # the sticker, on the world, where the player stands
NEED_HOPS = ['hunger', 'energy', 'vibe', 'thirst']   # the four needs the mood is made of
need_pts = [grown(NEED_BAR_X + dx, NEED_ROWS[n]) for n, dx in zip(NEED_HOPS, (-28, 18, -18, 22))]

BUS_FROM = (150, 1032)
BUS_TO = (1720, 1032)
BUS_ROOF = 1.06               # metres: the danfo scaled to 400 px long
# The danfo's x along the bottom: (beat, UI px). In from the left, out right.
BUS_PATH = [(14.6, -420), (16.2, BUS_FROM[0]), (19.3, BUS_TO[0]), (20.2, 2500)]

HOPS = [
    # pop up onto the mood line of the growing needs panel, and watch it drain
    dict(t0=f(4.3), t1=f(5.2), to=grown(*MOOD_ROW), on='me', z='hud', apex=1.6, spin=0),
    # Eat, Sleep, Party, Drink: one need a beat
    dict(t0=f(10.5), t1=f(11), to=need_pts[0], on='me', z='hud', apex=0.6, spin=0),
    dict(t0=f(11.5), t1=f(12), to=need_pts[1], on='me', z='hud', apex=0.5, spin=0),
    dict(t0=f(12.5), t1=f(13), to=need_pts[2], on='me', z='hud', apex=0.5, spin=0),
    dict(t0=f(13.5), t1=f(14), to=need_pts[3], on='me', z='hud', apex=0.6, spin=0),
    # down onto the danfo's roof as it arrives along the bottom
    dict(t0=f(15.45), t1=f(16.2), to='bus', on='bus', z='bus', apex=0.9, spin=0),
    # off the bus at the dock, onto Jobs here
    dict(t0=f(19.3), t1=f(20), to=centre(DOCK['work-hire']), on='dock-jobs', z='hud', apex=1.1, spin=0),
    # the long leap with a front flip onto the Phone button
    dict(t0=f(23.05), t1=f(24), to=centre(HUD['#btn-phone']), on='btn-phone', z='hud', apex=2.2, spin=1),
    # Cars, Property, Boutique, PH Ride
    dict(t0=f(24.55), t1=f(25), to=centre(APPS['cars']), on='app-cars', z='phone', apex=0.9, spin=0),
    dict(t0=f(25.55), t1=f(26), to=centre(APPS['property']), on='app-property', z='phone', apex=0.6, spin=0),
    dict(t0=f(26.55), t1=f(27), to=centre(APPS['boutique']), on='app-boutique', z='phone', apex=0.6, spin=0),
    dict(t0=f(27.55), t1=f(28), to=centre(APPS['hail']), on='app-hail', z='phone', apex=0.6, spin=0),
    # off the phone onto Spray money, for the people
    dict(t0=f(29.1), t1=f(30), to=centre(DOCK['spray']), on='spray', z='hud', apex=1.4, spin=0),
    # down onto Hide
    dict(t0=f(37.4), t1=f(38), to=centre(HUD['#btn-hide']), on='btn-hide', z='hud', apex=1.2, spin=0),
    # off the falling HUD onto the bare world, to dance
    dict(t0=f(40.0), t1=f(40.6), to=(1420, 700), on='world', z='world', apex=1.4, spin=0),
]

# Everything that happens on a frame. kind + args; the sound reads every one.
EVENTS = [
    dict(f=f(1), kind='knock'),
    dict(f=f(2), kind='knock'),
    dict(f=f(3), kind='peel'),
    dict(f=f(4), kind='pop'),               # glass shatters, the beat drops
    dict(f=f(4.3), kind='hud-grow', target='#hud-me'),
    # "Your needs drop all day": Belle and Water run down (Energy and Vibe
    # were already at 0 when recorded), the mood falls with them.
    dict(f=f(7.6), kind='needs-drain', f1=f(10.3), to={'hunger': 16.0, 'thirst': 18.0}),
]
for i, (n, h) in enumerate(zip(NEED_HOPS, HOPS[1:5])):
    EVENTS.append(dict(f=h['t1'], kind='need-fill', need=n, note=i))
EVENTS += [
    dict(f=f(15.8), kind='hud-shrink', target='#hud-me'),
    dict(f=f(14.8), kind='bus-arrive'),
    dict(f=f(16.2), kind='land-bus'),
    dict(f=f(19.3), kind='bus-leave'),
    dict(f=f(20), kind='press', target='dock-jobs'),
    # A DJ's first shift at the hall pays ₦7,900 (work.js, rank 1, performance 50).
    dict(f=f(21.6), kind='shift-pay', amount=7900),
    dict(f=f(23.05), kind='whoosh'),
    dict(f=f(24), kind='press', target='btn-phone'),
    dict(f=f(24), kind='phone-rise'),
    dict(f=f(25), kind='press', target='app-cars'),
    dict(f=f(26), kind='press', target='app-property'),
    dict(f=f(27), kind='press', target='app-boutique'),
    dict(f=f(28), kind='press', target='app-hail'),
    dict(f=f(29.4), kind='phone-sink'),
    dict(f=f(35.5), kind='press', target='spray'),
    dict(f=f(35.6), kind='kick-spray', notes=10, each=200),
    dict(f=f(38), kind='press', target='btn-hide'),
    dict(f=f(38.5), kind='hud-off'),        # every panel powers down and falls
    dict(f=f(40.6), kind='land-world'),
    dict(f=f(41), kind='dance'),
    dict(f=f(43), kind='endcard'),
    dict(f=f(48.6), kind='fade'),
]
for h in HOPS:
    EVENTS.append(dict(f=h['t0'], kind='takeoff'))
    EVENTS.append(dict(f=h['t1'], kind='land', z=h['z'], on=h['on']))
EVENTS.sort(key=lambda e: e['f'])


def event(kind):
    return next(e for e in EVENTS if e['kind'] == kind)


# Cash: 62,800 as recorded, plus the DJ shift, minus ten real ₦200 spray notes.
CASH0 = 62800
NEEDS0 = {'hunger': 70.2, 'energy': 0.0, 'vibe': 0.0, 'thirst': 88.9, 'social': 97.1, 'fun': 96.8}   # as recorded

END_LINE = 'A free multiplayer life game in Port Harcourt.'
END_URL = 'phlifestyle.fun'

# ------------------------------------------------------------------ voice ---

# The voiceover, one clip per line or word: (beat it starts on, id, words).
# `say` is what the voice reads when the spelling would trip it up.
VOICE = 'af_heart'
VO = [
    dict(beat=0.4, id='hook', text='This is PH Lifestyle. A whole Port Harcourt life, online.'),
    dict(beat=6.3, id='alive', text='First, stay alive. Your needs drop all day.'),
    dict(beat=10.95, id='eat', text='Eat.'),
    dict(beat=11.95, id='sleep', text='Sleep.'),
    dict(beat=12.95, id='party', text='Party.'),
    dict(beat=13.95, id='drink', text='Drink.'),
    dict(beat=15.2, id='danfo', text='Hop a danfo to work.'),
    dict(beat=19.95, id='job', text='Take a job.'),
    dict(beat=21.5, id='paid', text='Get paid.'),
    dict(beat=23.0, id='spend', text='Then spend it.'),
    dict(beat=24.95, id='car', text='A car.'),
    dict(beat=25.97, id='house', text='A house.'),
    dict(beat=27.0, id='clothes', text='Drip.'),
    dict(beat=27.95, id='ride', text='A ride across town.'),
    dict(beat=30.6, id='real', text='And everyone here is a real player.'),
    dict(beat=34.3, id='chat', text='Chat.'),
    dict(beat=35.25, id='spray', text='Spray money.'),
    dict(beat=36.65, id='love', text='Fall in love.'),
    dict(beat=38.3, id='hide', text='Hide the HUD, and just live.'),
    dict(beat=42.8, id='end', text='PH Lifestyle. Free to play, at phlifestyle.fun.',
         say='PH Lifestyle. Free to play, at P H lifestyle dot fun.'),
]
VO_LINES = os.path.join(STUDIO, 'cache', 'vo', VOICE, 'lines.json')
_secs = {}
if os.path.exists(VO_LINES):
    _secs = {m['id']: m['secs'] for m in json.load(open(VO_LINES))['lines']}
for v in VO:
    v['f'] = f(v['beat'])
    # Until voice.py has run: about 15 characters a second.
    v['secs'] = _secs.get(v['id'], round(len(v['text']) / 15, 2))
    v['f_end'] = v['f'] + int(round(v['secs'] * FPS))
VO_BY = {v['id']: v for v in VO}

# Captions: cards of fragments, each fragment from one VO clip; a fragment
# shows when its words are said (by its place in the clip's text), *stars*
# mark the accent words. A card holds until the next card, or `hold` frames
# after its last words.
CAPTION_CARDS = [
    [('This is', 'hook'), ('*PH Lifestyle.*', 'hook')],
    [('A whole', 'hook'), ('Port Harcourt', 'hook'), ('life,', 'hook'), ('*online.*', 'hook')],
    [('First,', 'alive'), ('*stay alive.*', 'alive')],
    [('Your needs', 'alive'), ('drop', 'alive'), ('all day.', 'alive')],
    [('*Eat.*', 'eat'), ('*Sleep.*', 'sleep'), ('*Party.*', 'party'), ('*Drink.*', 'drink')],
    [('Hop a', 'danfo'), ('*danfo*', 'danfo'), ('to work.', 'danfo')],
    [('Take a job.', 'job'), ('*Get paid.*', 'paid')],
    [('Then', 'spend'), ('*spend it.*', 'spend')],
    [('A car.', 'car'), ('A house.', 'house'), ('*Drip.*', 'clothes')],
    [('A ride', 'ride'), ('across town.', 'ride')],
    [('And everyone here', 'real'), ('is a', 'real'), ('*real player.*', 'real')],
    [('Chat.', 'chat'), ('Spray money.', 'spray'), ('*Fall in love.*', 'love')],
    [('Hide the HUD,', 'hide'), ('and', 'hide'), ('*just live.*', 'hide')],
]


def caption_cards():
    cards = []
    for parts in CAPTION_CARDS:
        out = []
        for text, vid in parts:
            v = VO_BY[vid]
            plain = re.sub(r'\*', '', text)
            # Where these words sit in the clip, by characters: an estimate.
            at = v['text'].find(plain)
            k = max(0, at) / max(1, len(v['text']))
            out.append(dict(f=v['f'] + int(round(k * v['secs'] * FPS * 0.92)), text=text, vo=vid))
        last = VO_BY[parts[-1][1]]
        cards.append(dict(f_in=out[0]['f'], f_out=last['f_end'] + 12, parts=out))
    for a, b in zip(cards, cards[1:]):
        a['f_out'] = min(a['f_out'], b['f_in'])
    return cards


CAPTIONS = caption_cards()

# ---------------------------------------------------------------- overlay ---

# The lesson chips, top left: the number in the accent face, the title bold.
CHAPTERS = [
    dict(f_in=f(5.4), f_out=f(15.2), n='01', title='Stay alive'),
    dict(f_in=f(15.2), f_out=f(23.0), n='02', title='Make money'),
    dict(f_in=f(23.0), f_out=f(29.8), n='03', title='Spend it'),
    dict(f_in=f(29.8), f_out=f(38.2), n='04', title='Real people'),
]

# Points the callouts point at, followed in 3D: a slab and a UI px on it
# (None = its centre), or Tobi's head, or the danfo's roof. scene.py makes an
# empty for each; anchors.py projects them through each camera, every frame.
ANCHORS = {
    'needs': dict(slab='me', at=(232, 120)),             # the right edge of the bars
    'hunger': dict(slab='me', at=(222, NEED_ROWS['hunger'])),
    'energy': dict(slab='me', at=(222, NEED_ROWS['energy'])),
    'vibe': dict(slab='me', at=(222, NEED_ROWS['vibe'])),
    'thirst': dict(slab='me', at=(222, NEED_ROWS['thirst'])),
    'mood': dict(slab='me', at=(200, MOOD_ROW[1])),
    'bus': dict(obj='bus'),
    'jobs': dict(slab='dock-jobs', at=None),
    'cars': dict(slab='app-cars', at=None),
    'property': dict(slab='app-property', at=None),
    'boutique': dict(slab='app-boutique', at=None),
    'hail': dict(slab='app-hail', at=None),
    'online': dict(slab='stats', at=centre(HUD['#online-pill'])),
    'chat': dict(slab='chat', at=(222, 975)),
    'spray': dict(slab='spray', at=None),
    'hide': dict(slab='btn-hide', at=None),
    'tobi': dict(obj='tobi'),
}

# Callouts: a glass label on a leader line to an anchor. `title` bold, `sub`
# the real detail from the game. kind 'money' is a big number popping off the
# anchor. Hidden on a format whose camera has the anchor off screen.
CALLOUTS = [
    dict(id='needs', anchor='needs', f_in=f(7.4), f_out=f(10.6), title='Your needs', sub='They drop all day'),
    dict(id='mood', anchor='mood', f_in=f(9.0), f_out=f(10.6), title='Mood: Miserable', sub='Low needs, low mood'),
    dict(id='eat', anchor='hunger', f_in=f(11), f_out=f(15.3), title='Belle', sub='Eat'),
    dict(id='sleep', anchor='energy', f_in=f(12), f_out=f(15.3), title='Energy', sub='Sleep'),
    dict(id='party', anchor='vibe', f_in=f(13), f_out=f(15.3), title='Vibe', sub='Party'),
    dict(id='drink', anchor='thirst', f_in=f(14), f_out=f(15.3), title='Water', sub='Drink'),
    dict(id='danfo', anchor='bus', f_in=f(16.4), f_out=f(19.2), title='Danfo', sub='Bus routes across the city'),
    dict(id='jobs', anchor='jobs', f_in=f(20.1), f_out=f(23.0), title='Jobs here · 2 vacancies',
         sub='DJ ₦7,900 · Event Planner ₦6,800 a shift'),
    dict(id='halve', anchor='jobs', f_in=f(20.8), f_out=f(23.0), kind='tip', title='Low belly, energy or water?', sub='Half pay'),
    dict(id='paid', anchor='jobs', f_in=f(21.6), f_out=f(23.2), kind='money', title='+₦7,900'),
    dict(id='cars', anchor='cars', f_in=f(25), f_out=f(29.2), title='Cars', sub='Buy one, drive it'),
    dict(id='property', anchor='property', f_in=f(26), f_out=f(29.2), title='Property', sub='Rent or buy a home'),
    dict(id='boutique', anchor='boutique', f_in=f(27), f_out=f(29.2), title='Boutique', sub='Dress up'),
    dict(id='hail', anchor='hail', f_in=f(28), f_out=f(29.2), title='PH Ride', sub='Hail a ride, or drive one'),
    dict(id='online', anchor='online', f_in=f(31.0), f_out=f(33.9), title='79 online', sub='Every one a real player'),
    dict(id='chat', anchor='chat', f_in=f(34.0), f_out=f(35.3), title='Chat and Gist', sub='Talk to anyone in town'),
    dict(id='spray', anchor='spray', f_in=f(35.5), f_out=f(37.4), title='Spray money', sub='Make it rain at the owambe'),
    dict(id='love', anchor='tobi', f_in=f(36.65), f_out=f(37.6), title='Date · marry · start a family'),
    dict(id='spent', anchor='spray', f_in=f(35.8), f_out=f(36.9), kind='money', title='−₦2,000', tone='spend'),
    dict(id='hide', anchor='hide', f_in=f(38.0), f_out=f(39.6), title='Hide', sub='The HUD goes; the city stays'),
]

# --------------------------------------------------------------- cameras ---

# Camera keys: frame, target (UI px or 'tobi'), distance, height, yaw, lens.
NEEDS_VIEW = grown(122, 118)     # the middle of the grown needs panel
CAMERA = [
    dict(f=f(0), look=(960, 560), dist=17.0, elev=34, yaw=-8, lens=40, fstop=8.0),
    dict(f=f(3), look=START, dist=7.5, elev=26, yaw=-4, lens=45, fstop=4.0),
    dict(f=f(4), look='tobi', dist=7.6, elev=24, yaw=-12, lens=50, fstop=2.8),
    dict(f=f(5.6), look=NEEDS_VIEW, dist=9.6, elev=42, yaw=-6, lens=40, fstop=5.6),
    dict(f=f(10.2), look=NEEDS_VIEW, dist=8.8, elev=40, yaw=4, lens=40, fstop=5.6),
    dict(f=f(10.8), look='tobi', dist=7.8, elev=30, yaw=2, lens=45, fstop=3.2),
    dict(f=f(14.6), look='tobi', dist=7.8, elev=26, yaw=10, lens=50, fstop=2.8),
    dict(f=f(16.4), look='tobi', dist=9.0, elev=14, yaw=-55, lens=40, fstop=3.2),
    dict(f=f(19.0), look='tobi', dist=9.0, elev=14, yaw=-25, lens=40, fstop=3.2),
    dict(f=f(20.4), look='tobi', dist=7.4, elev=22, yaw=-30, lens=50, fstop=2.8),
    dict(f=f(22.8), look='tobi', dist=7.0, elev=22, yaw=-18, lens=50, fstop=2.8),
    dict(f=f(24), look='tobi', dist=8.6, elev=24, yaw=-6, lens=45, fstop=3.2),
    dict(f=f(28.2), look='tobi', dist=8.0, elev=22, yaw=8, lens=45, fstop=3.2),
    dict(f=f(29.8), look='tobi', dist=8.0, elev=24, yaw=-20, lens=45, fstop=3.2),
    # Wide: everyone online, the chat, Tobi on the dock.
    dict(f=f(31.2), look=(1080, 540), dist=18.0, elev=36, yaw=-6, lens=40, fstop=8.0),
    dict(f=f(33.4), look=(1160, 560), dist=16.6, elev=35, yaw=-3, lens=40, fstop=8.0),
    # Down to the chat for "Chat.", then a whip to Tobi on Spray money.
    dict(f=f(34.1), look=(330, 880), dist=8.6, elev=40, yaw=-4, lens=40, fstop=5.6),
    dict(f=f(34.9), look=(350, 885), dist=8.2, elev=40, yaw=0, lens=40, fstop=5.6),
    dict(f=f(35.5), look='tobi', dist=7.4, elev=22, yaw=-30, lens=50, fstop=2.8),
    dict(f=f(37.2), look='tobi', dist=8.0, elev=22, yaw=-10, lens=45, fstop=3.2),
    dict(f=f(38.4), look=(960, 760), dist=9.0, elev=26, yaw=0, lens=40, fstop=4.0),
    dict(f=f(41), look=(960, 600), dist=17.5, elev=32, yaw=-4, lens=40, fstop=8.0),
    dict(f=f(50), look=(960, 610), dist=16.6, elev=33, yaw=-2, lens=40, fstop=8.0),
]

# The 9:16 cut has its own camera: the same beats, framed for a tall screen.
# Only ~8.6 m of the screen fits across, so the wide keys follow Tobi too, the
# people shot frames the dock and the online pill (the chat stays off), and
# the end looks at the tall end card (END_CARD_9X16) and the dance.
END_CARD_9X16 = dict(cx=1180, bottom=150)
NEEDS_VIEW_9X16 = grown(150, 128)    # wider: the bars' right ends, where the callouts point
CAMERA_9X16 = [
    dict(f=f(0), look=(960, 600), dist=15.0, elev=40, yaw=-6, lens=36, fstop=8.0),
    dict(f=f(3), look=START, dist=6.8, elev=30, yaw=-4, lens=40, fstop=4.0),
    dict(f=f(4), look='tobi', dist=6.6, elev=24, yaw=-12, lens=45, fstop=2.8),
    dict(f=f(5.6), look=NEEDS_VIEW_9X16, dist=12.4, elev=46, yaw=-4, lens=36, fstop=5.6),
    dict(f=f(10.2), look=NEEDS_VIEW_9X16, dist=11.8, elev=44, yaw=2, lens=36, fstop=5.6),
    dict(f=f(14.6), look=NEEDS_VIEW_9X16, dist=11.2, elev=40, yaw=6, lens=36, fstop=5.6),
    dict(f=f(16.4), look='tobi', dist=7.6, elev=16, yaw=-40, lens=36, fstop=3.2),
    dict(f=f(19.0), look='tobi', dist=7.6, elev=16, yaw=-20, lens=36, fstop=3.2),
    dict(f=f(20.4), look='tobi', dist=6.6, elev=22, yaw=-28, lens=45, fstop=2.8),
    dict(f=f(22.8), look='tobi', dist=6.4, elev=22, yaw=-18, lens=45, fstop=2.8),
    dict(f=f(24), look='tobi', dist=7.6, elev=26, yaw=-6, lens=40, fstop=3.2),
    dict(f=f(28.2), look='tobi', dist=7.0, elev=24, yaw=8, lens=40, fstop=3.2),
    dict(f=f(29.8), look='tobi', dist=7.0, elev=24, yaw=-20, lens=40, fstop=3.2),
    dict(f=f(31.2), look=(1640, 420), dist=12.5, elev=42, yaw=-6, lens=36, fstop=6.0),
    dict(f=f(33.4), look=(1660, 440), dist=11.8, elev=41, yaw=-3, lens=36, fstop=6.0),
    dict(f=f(34.1), look=(230, 900), dist=9.0, elev=44, yaw=-4, lens=36, fstop=5.6),
    dict(f=f(34.9), look=(240, 905), dist=8.6, elev=44, yaw=0, lens=36, fstop=5.6),
    dict(f=f(35.5), look='tobi', dist=6.6, elev=22, yaw=-28, lens=45, fstop=2.8),
    dict(f=f(37.2), look='tobi', dist=7.0, elev=24, yaw=-10, lens=40, fstop=3.2),
    dict(f=f(38.4), look='tobi', dist=8.0, elev=28, yaw=0, lens=36, fstop=4.0),
    dict(f=f(41), look=(1200, 760), dist=15.5, elev=38, yaw=-4, lens=36, fstop=8.0),
    dict(f=f(50), look=(1200, 770), dist=14.8, elev=39, yaw=-2, lens=36, fstop=8.0),
]

FONTS = dict(
    bold=os.path.abspath('assets/fonts/mazzard-soft-h-bold.otf'),  # commercial, not in the repo
    accent_family="Editor's Note",      # installed in ~/Library/Fonts; italic for the accent words
)
GREEN = '#008751'


def to_json():
    return dict(NAME=NAME, FPS=FPS, BPM=BPM, BEAT=BEAT, BEATS=BEATS, FRAMES=FRAMES, W=W, H=H, SCALE=SCALE,
                Z=Z, NEEDS_GROW=NEEDS_GROW, NEEDS_ORIGIN=NEEDS_ORIGIN, NEED_ROWS=NEED_ROWS,
                CUTS=CUTS, START=START, HOPS=HOPS, BUS_FROM=BUS_FROM, BUS_TO=BUS_TO, BUS_ROOF=BUS_ROOF,
                BUS_PATH=BUS_PATH, TILES=TILES, DOCK_TILES=DOCK_TILES,
                EVENTS=EVENTS, CASH0=CASH0, NEEDS0=NEEDS0, END_LINE=END_LINE, END_URL=END_URL,
                VOICE=VOICE, VO=VO, CAPTIONS=CAPTIONS, CHAPTERS=CHAPTERS, ANCHORS=ANCHORS, CALLOUTS=CALLOUTS,
                FONTS=FONTS, GREEN=GREEN,
                CAMERA=CAMERA, CAMERA_9X16=CAMERA_9X16, END_CARD_9X16=END_CARD_9X16, HUD=HUD, APPS=APPS, DOCK=DOCK, PHONE=PHONE)


if __name__ == '__main__':
    out = os.path.join(STUDIO, 'src', 'timeline.json')
    json.dump(to_json(), open(out, 'w'), indent=1, ensure_ascii=False)
    print(f'{FRAMES} frames, {len(EVENTS)} events, {len(HOPS)} hops, {len(CUTS)} cuts, '
          f'{len(VO)} lines, {len(CAPTIONS)} captions, {len(CALLOUTS)} callouts -> {out}'
          + ('' if _secs else '  (no voice yet: run src/voice.py, then this again)'))
