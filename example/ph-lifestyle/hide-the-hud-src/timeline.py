"""The one timeline: every beat, hop, press, cut and sound in the film.

Read by the UI capture (via timeline.json), the world comp, the Blender scene
and the sound. Run `python3 src/timeline.py` to write timeline.json.

Space is the game screen at 1920x1080 UI pixels, top-left origin, laid flat
as a floor (the exploded game screen). px() turns a UI pixel into metres.
"""
import json
import os

FPS = 30
BPM = 100
BEAT = 18                    # frames per beat (0.6 s)
BEATS = 28
FRAMES = BEATS * BEAT        # 504 = 16.8 s
W, H = 1920, 1080
SCALE = 0.01                 # metres per UI pixel: Tobi (1.98 m) is 198 px tall

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECTS = json.load(open(os.path.join(STUDIO, 'assets', 'ui', 'rects.json')))


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
    'tile': 0.05,       # app tiles and nav buttons stand proud of their slab
    'slab': 0.05,       # slab thickness
}

# The needs panel grows forward so its rows become steps Tobi can land on.
NEEDS_GROW = 2.5
NEEDS_ORIGIN = (HUD['#hud-me']['x'], HUD['#hud-me']['y'])
NEED_ROWS = {'hunger': 70, 'energy': 90, 'vibe': 110, 'thirst': 130, 'social': 150, 'fun': 170}
NEED_BAR_X = 132             # middle of the bars, UI px (before growing)


def grown(x, y):
    ox, oy = NEEDS_ORIGIN
    return (ox + (x - ox) * NEEDS_GROW, oy + (y - oy) * NEEDS_GROW)


# World footage cuts: (start frame, clip slug, seconds into the clip).
# Clips start 1.2 s in or later, after the game's "press H" hint has gone.
CUTS = [
    (f(0), 'market-day', 1.4),
    (f(5), 'jevinik', 1.2),
    (f(6), 'home', 1.2),
    (f(7), 'club', 1.2),
    (f(8), 'beach', 1.2),
    (f(9), 'ride-bus', 1.0),    # the player hanging off a danfo
    (f(13), 'hall-night', 1.0),
    (f(16), 'ride-drop', 1.6),
    (f(17), 'hall-night', 3.8),
    (f(18), 'estate', 1.6),
    (f(19), 'mall', 1.2),
    (f(20.5), 'hall-high', 1.2),
]

# Tobi's path. Each hop: take-off frame, landing frame, landing point (UI px),
# landing height, apex height above the higher end, spins (front flips).
START = (960, 640)           # the sticker, on the world, where the player stands
NEED_HOPS = ['hunger', 'energy', 'vibe', 'thirst']   # the four needs the mood is made of
need_pts = [grown(NEED_BAR_X + dx, NEED_ROWS[n]) for n, dx in zip(NEED_HOPS, (-28, 18, -18, 22))]

BUS_FROM = (150, 1032)
BUS_TO = (1720, 1032)
BUS_ROOF = 1.06               # metres: the danfo scaled to 400 px long

HOPS = [
    # pop onto the first need, Belle; then Energy, Vibe, Water
    dict(t0=f(4.3), t1=f(5), to=need_pts[0], z='hud', apex=1.6, spin=0),
    dict(t0=f(5.55), t1=f(6), to=need_pts[1], z='hud', apex=0.5, spin=0),
    dict(t0=f(6.55), t1=f(7), to=need_pts[2], z='hud', apex=0.5, spin=0),
    dict(t0=f(7.5), t1=f(8), to=need_pts[3], z='hud', apex=0.7, spin=0),
    # down onto the danfo's roof as it arrives along the bottom
    dict(t0=f(8.45), t1=f(9), to='bus', z='bus', apex=0.9, spin=0),
    # off the bus at the dock, up onto Spray money
    dict(t0=f(12.3), t1=f(13), to=centre(DOCK['spray']), z='hud', apex=1.1, spin=0),
    # the long leap with a front flip onto the Phone button
    dict(t0=f(14.05), t1=f(15), to=centre(HUD['#btn-phone']), z='hud', apex=2.2, spin=1),
    # the four app tiles
    dict(t0=f(15.55), t1=f(16), to=centre(APPS['cars']), z='phone', apex=0.9, spin=0),
    dict(t0=f(16.55), t1=f(17), to=centre(APPS['events']), z='phone', apex=0.6, spin=0),
    dict(t0=f(17.55), t1=f(18), to=centre(APPS['property']), z='phone', apex=0.6, spin=0),
    dict(t0=f(18.55), t1=f(19), to=centre(APPS['boutique']), z='phone', apex=0.6, spin=0),
    # down onto Hide
    dict(t0=f(19.5), t1=f(20), to=centre(HUD['#btn-hide']), z='hud', apex=1.2, spin=0),
    # off the falling HUD onto the bare world, to dance
    dict(t0=f(21.0), t1=f(21.6), to=(1420, 700), z='world', apex=1.4, spin=0),
]

# Everything that happens on a frame. kind + args; the sound reads every one.
EVENTS = [
    dict(f=f(1), kind='knock'),
    dict(f=f(2), kind='knock'),
    dict(f=f(3), kind='peel'),
    dict(f=f(4), kind='pop'),               # glass shatters, the beat drops
    dict(f=f(4.3), kind='hud-grow', target='#hud-me'),
]
for i, (n, h) in enumerate(zip(NEED_HOPS, HOPS[:4])):
    EVENTS.append(dict(f=h['t1'], kind='need-fill', need=n, note=i))
EVENTS += [
    dict(f=f(8.2), kind='bus-arrive'),
    dict(f=f(9), kind='land-bus'),
    dict(f=f(12.3), kind='bus-leave'),
    dict(f=f(13), kind='press', target='spray'),
    dict(f=f(13.5), kind='kick-spray', notes=10, each=200),
    dict(f=f(14.05), kind='whoosh'),
    dict(f=f(15), kind='press', target='#btn-phone'),
    dict(f=f(15), kind='phone-rise'),
    dict(f=f(16), kind='press', target='cars'),
    dict(f=f(17), kind='press', target='events'),
    dict(f=f(18), kind='press', target='property'),
    dict(f=f(19), kind='press', target='boutique'),
    dict(f=f(20), kind='press', target='#btn-hide'),
    dict(f=f(20.5), kind='hud-off'),        # every panel powers down and falls
    dict(f=f(21.6), kind='land-world'),
    dict(f=f(22), kind='dance'),
    dict(f=f(23), kind='endcard'),
    dict(f=f(26.5), kind='fade'),
]
for h in HOPS:
    EVENTS.append(dict(f=h['t0'], kind='takeoff'))
    EVENTS.append(dict(f=h['t1'], kind='land', z=h['z']))
EVENTS.sort(key=lambda e: e['f'])

# Cash: 62,800 as recorded, minus ten real ₦200 spray notes after the kick.
CASH0 = 62800
NEEDS0 = {'hunger': 70.2, 'energy': 0.0, 'vibe': 0.0, 'thirst': 88.9, 'social': 97.1, 'fun': 96.8}   # as recorded

END_LINE = 'A free multiplayer life game in Port Harcourt.'
END_URL = 'phlifestyle.fun'

# Camera keys: frame, target (UI px or 'tobi'), distance, height, yaw, lens.
CAMERA = [
    dict(f=f(0), look=(960, 560), dist=17.0, elev=34, yaw=-8, lens=40, fstop=8.0),
    dict(f=f(3), look=START, dist=7.5, elev=26, yaw=-4, lens=45, fstop=4.0),
    dict(f=f(4), look='tobi', dist=7.6, elev=24, yaw=-12, lens=50, fstop=2.8),
    dict(f=f(8.5), look='tobi', dist=7.8, elev=26, yaw=10, lens=50, fstop=2.8),
    dict(f=f(9.2), look='tobi', dist=9.0, elev=14, yaw=-55, lens=40, fstop=3.2),
    dict(f=f(12), look='tobi', dist=9.0, elev=14, yaw=-25, lens=40, fstop=3.2),
    dict(f=f(13.6), look='tobi', dist=7.4, elev=22, yaw=-30, lens=50, fstop=2.8),
    dict(f=f(15), look='tobi', dist=8.6, elev=24, yaw=-6, lens=45, fstop=3.2),
    dict(f=f(19.2), look='tobi', dist=8.0, elev=22, yaw=8, lens=45, fstop=3.2),
    dict(f=f(20.4), look=(960, 760), dist=9.0, elev=26, yaw=0, lens=40, fstop=4.0),
    dict(f=f(23), look=(960, 600), dist=17.5, elev=32, yaw=-4, lens=40, fstop=8.0),
    dict(f=f(28), look=(960, 610), dist=16.6, elev=33, yaw=-2, lens=40, fstop=8.0),
]


# The 9:16 cut has its own camera: the same beats, framed for a tall screen.
# Only ~8.6 m of the screen fits across, so the wide keys follow Tobi too, and
# the end looks at the tall end card (END_CARD_9X16) and the dance.
END_CARD_9X16 = dict(cx=1180, bottom=150)
CAMERA_9X16 = [
    dict(f=f(0), look=(960, 600), dist=15.0, elev=40, yaw=-6, lens=36, fstop=8.0),
    dict(f=f(3), look=START, dist=6.8, elev=30, yaw=-4, lens=40, fstop=4.0),
    dict(f=f(4), look='tobi', dist=6.6, elev=24, yaw=-12, lens=45, fstop=2.8),
    dict(f=f(8.5), look='tobi', dist=6.8, elev=26, yaw=10, lens=45, fstop=2.8),
    dict(f=f(9.2), look='tobi', dist=7.6, elev=16, yaw=-40, lens=36, fstop=3.2),
    dict(f=f(12), look='tobi', dist=7.6, elev=16, yaw=-20, lens=36, fstop=3.2),
    dict(f=f(13.6), look='tobi', dist=6.6, elev=22, yaw=-28, lens=45, fstop=2.8),
    dict(f=f(15), look='tobi', dist=7.6, elev=26, yaw=-6, lens=40, fstop=3.2),
    dict(f=f(19.2), look='tobi', dist=7.0, elev=24, yaw=8, lens=40, fstop=3.2),
    dict(f=f(20.4), look='tobi', dist=8.0, elev=28, yaw=0, lens=36, fstop=4.0),
    dict(f=f(23), look=(1200, 760), dist=15.5, elev=38, yaw=-4, lens=36, fstop=8.0),
    dict(f=f(28), look=(1200, 770), dist=14.8, elev=39, yaw=-2, lens=36, fstop=8.0),
]


def to_json():
    return dict(FPS=FPS, BPM=BPM, BEAT=BEAT, BEATS=BEATS, FRAMES=FRAMES, W=W, H=H, SCALE=SCALE,
                Z=Z, NEEDS_GROW=NEEDS_GROW, NEEDS_ORIGIN=NEEDS_ORIGIN, NEED_ROWS=NEED_ROWS,
                CUTS=CUTS, START=START, HOPS=HOPS, BUS_FROM=BUS_FROM, BUS_TO=BUS_TO, BUS_ROOF=BUS_ROOF,
                EVENTS=EVENTS, CASH0=CASH0, NEEDS0=NEEDS0, END_LINE=END_LINE, END_URL=END_URL,
                CAMERA=CAMERA, CAMERA_9X16=CAMERA_9X16, END_CARD_9X16=END_CARD_9X16, HUD=HUD, APPS=APPS, DOCK=DOCK, PHONE=PHONE)


if __name__ == '__main__':
    out = os.path.join(STUDIO, 'src', 'timeline.json')
    json.dump(to_json(), open(out, 'w'), indent=1)
    print(f'{FRAMES} frames, {len(EVENTS)} events, {len(HOPS)} hops, {len(CUTS)} cuts -> {out}')
