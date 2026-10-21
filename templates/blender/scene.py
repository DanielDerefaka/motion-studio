"""The Blender scene: the exploded product screen as a floor of glowing UI
slabs under glass in a warm dark studio, the hero hopping across the buttons,
every press changing something. Keyed per frame from timeline.py through
scene_kit.py. Builds cache/scene.blend.

blender -b --factory-startup -P src/scene.py

This is the DEMO film: it runs with no assets. It draws its own textures
(numpy; Blender's Python has no PIL) into cache/demo-ui/ in the same
textures.json shape the capture step writes, and uses the toy hero. A real
film swaps in three things, each marked PLUG below:
  1. its captured UI: assets/ui/textures.json + assets/ui/tex/*.png
  2. its footage on the base slab: cache/world/NNNN.jpg, one per film frame
  3. its hero: assets/hero.glb (rigged, animation clips become NLA strips)
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402
import scene_kit as K  # noqa: E402

ROOT = T.STUDIO
F = T.f
HERO_GLB = os.path.join(ROOT, 'assets', 'hero.glb')
HERO_CLIPS = dict(idle='Idle', air='Run')          # the glb's clip names
BUTTONS = ['btn-a', 'btn-b', 'btn-c']
TINT = {'btn-a': (0.98, 0.45, 0.32), 'btn-b': (0.25, 0.80, 0.72), 'btn-c': (0.98, 0.78, 0.30)}
ICON = {'btn-a': 'circle', 'btn-b': 'triangle', 'btn-c': 'plus'}

K.studio()

# --------------------------------------------------- demo textures (numpy) ---
# Stand-ins for the captured UI. Each PNG covers its element plus PAD px of
# soft shadow, like the capture step's output. Pixel values are sRGB.

DEMO = os.path.join(ROOT, 'cache', 'demo-ui')
PAD, DPR = 24, 2


def save_png(arr, file):
    """arr: h x w x 4 floats, top row first."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new('tmp', w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())
    img.filepath_raw = file
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def rr_mask(h, w, x0, y0, x1, y1, r, soft=1.0):
    """Coverage of a rounded rect (px), anti-aliased over `soft` px."""
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    qx = np.abs(xx - cx) - ((x1 - x0) / 2 - r)
    qy = np.abs(yy - cy) - ((y1 - y0) / 2 - r)
    d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    return np.clip(0.5 - d / soft, 0, 1)


def panel(rect, tint, radius=16):
    """A glossy rounded panel with a drop shadow in the padding."""
    w, h = int((rect['w'] + 2 * PAD) * DPR), int((rect['h'] + 2 * PAD) * DPR)
    p, r = PAD * DPR, radius * DPR
    a = np.zeros((h, w, 4), np.float32)
    shadow = rr_mask(h, w, p, p + 6 * DPR, w - p, h - p + 6 * DPR, r, soft=18 * DPR) * 0.55
    body = rr_mask(h, w, p, p, w - p, h - p, r)
    yy = np.linspace(0, 1, h)[:, None]
    for c in range(3):
        top, bot = tint[c] * 0.95 + 0.05, tint[c] * 0.55
        a[..., c] = top + (bot - top) * yy
    ring = body - rr_mask(h, w, p + 2 * DPR, p + 2 * DPR, w - p - 2 * DPR, h - p - 2 * DPR, r - 2 * DPR)
    a[..., :3] = a[..., :3] * (1 - ring[..., None] * 0.5) + ring[..., None] * 0.5
    a[..., 3] = np.maximum(body, shadow)
    a[..., :3] *= (body / np.maximum(a[..., 3], 1e-4))[..., None]       # shadow is black
    return a


def icon(a, kind, ink=(1, 1, 1)):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    cx, cy, s = w / 2, h / 2, min(w, h) * 0.2
    if kind == 'circle':
        cov = np.clip(s - np.hypot(xx - cx, yy - cy) + 0.5, 0, 1)
    elif kind == 'triangle':
        u, v = (xx - cx) / s, (yy - cy) / s
        cov = ((v < 0.8) & (v > -0.9 + 1.7 * np.abs(u) * 1.1)).astype(np.float32)
    else:
        cov = (((np.abs(xx - cx) < s) & (np.abs(yy - cy) < s * 0.3)) |
               ((np.abs(yy - cy) < s) & (np.abs(xx - cx) < s * 0.3))).astype(np.float32)
    a[..., :3] = a[..., :3] * (1 - cov[..., None]) + np.array(ink) * cov[..., None]
    return a


def stats_frames(rect):
    """The stats panel as a per-frame sequence: a bar per button fills as it is
    pressed, the total jumps on the money event. One PNG per film frame."""
    base = panel(rect, (0.16, 0.16, 0.19))
    h, w = base.shape[:2]
    p = PAD * DPR
    money_f = K.event_f('money', T.FRAMES + 1)
    out = os.path.join(DEMO, 'panel-stats')
    os.makedirs(out, exist_ok=True)
    for fr in K.FRAMES:
        file = os.path.join(out, f'{fr:04d}.png')
        if os.path.exists(file):
            continue
        a = base.copy()
        for i, b in enumerate(BUTTONS):
            pf = K.event_f('press', T.FRAMES + 1, target=b)
            k = K.spring(fr - pf, 10, 8)
            y0 = int(p + h * 0.30 + i * h * 0.13)
            x0, x1 = int(p + 30 * DPR), int(w - p - 30 * DPR)
            a[y0:y0 + 10 * DPR, x0:x1, :3] = 0.28
            xe = x0 + int((x1 - x0) * (0.12 + 0.78 * k))
            a[y0:y0 + 10 * DPR, x0:xe, :3] = TINT[b]
        k = K.spring(fr - money_f, 12, 8)
        y0 = int(h - p - 46 * DPR)
        x0, x1 = int(p + 30 * DPR), int(w - p - 30 * DPR)
        a[y0:y0 + 18 * DPR, x0:x1, :3] = 0.22
        a[y0:y0 + 18 * DPR, x0:x0 + int((x1 - x0) * (0.2 + 0.8 * k)), :3] = (0.2, 0.95, 0.55)
        save_png(a, file)
    return os.path.join(out, '0001.png')


def world_png():
    """The base slab without footage: a dark city map, streets on a grid."""
    w, h = T.W // 2, T.H // 2
    a = np.zeros((h, w, 4), np.float32)
    a[..., :3] = (0.05, 0.06, 0.07)
    a[..., 3] = 1
    rs = np.random.default_rng(7)
    for _ in range(140):
        x, y = rs.integers(0, w - 40), rs.integers(0, h - 30)
        a[y:y + rs.integers(14, 40), x:x + rs.integers(18, 60), :3] = rs.uniform(0.07, 0.13)
    for x in range(0, w, 64):
        a[:, x:x + 5, :3] = (0.16, 0.15, 0.13)
    for y in range(0, h, 54):
        a[y:y + 5, :, :3] = (0.16, 0.15, 0.13)
    file = os.path.join(DEMO, 'world.png')
    save_png(a, file)
    return file


def demo_textures():
    """Writes cache/demo-ui/textures.json in the capture step's shape."""
    os.makedirs(DEMO, exist_ok=True)
    tex = {'pad': PAD, 'dpr': DPR}
    for name, r in T.RECTS.items():
        face = dict(x=r['x'] - PAD, y=r['y'] - PAD, w=r['w'] + 2 * PAD, h=r['h'] + 2 * PAD)
        if name == 'panel-stats':
            file = stats_frames(r)
        else:
            file = os.path.join(DEMO, f'{name}.png')
            save_png(icon(panel(r, TINT.get(name, (0.5, 0.5, 0.55)), 22), ICON.get(name, 'circle')), file)
        tex[name] = dict(file=os.path.relpath(file, ROOT), el=dict(r), **face)
    file = os.path.join(DEMO, 'textures.json')
    json.dump(tex, open(file, 'w'), indent=1)
    return file


# PLUG 1: a real film loads its capture instead:
#   TEX = K.load_textures()        # assets/ui/textures.json
TEX = K.load_textures(demo_textures())

# --------------------------------------------------------------- the set ---

# PLUG 2: the live footage, one frame per film frame, when the film has it.
WORLD_SEQ = os.path.join(ROOT, 'cache', 'world', '0001.jpg')
if os.path.exists(WORLD_SEQ):
    base = K.Base(K.load_image(WORLD_SEQ, T.FRAMES), seq=T.FRAMES)
else:
    base = K.Base(K.load_image(world_png()), strength=1.0)

ZH = K.layer_top('hud')                           # top of a HUD panel
stats = K.Slab.from_tex('panel-stats', TEX['panel-stats'], ZH, radius_px=16, seq=T.FRAMES)
for b in BUTTONS:
    K.Slab.from_tex(b, TEX[b], ZH, radius_px=22, strength=1.4)
K.label('STATS', stats.root, size=0.32, loc=stats.at(stats.cx, stats.el['y'] + 34) + Vector((0, 0, 0.004)))

# The glass over the world, with a hole of shards where the hero breaks out.
POP_F = K.event_f('pop', 1)
shards = K.glass_sheet(hole_at=T.START)
K.shatter(shards, T.START, POP_F)
K.studio_lights()

# ------------------------------------------------------------------ hero ---

# PLUG 3: a rigged glb hero, its clips on the NLA. Without one, the toy.
if os.path.exists(HERO_GLB):
    hero = K.hero_glb(HERO_GLB, height=1.6)
    hero.clip('base', HERO_CLIPS['idle'], 1)
    hero.air(HERO_CLIPS['air'])
else:
    hero = K.toy_hero()

hops = K.Hops(hero, start=T.START, start_on='world')


def hero_state(fr):
    """The demo's own beat on top of the hops: the hero bursts up through the
    glass on the pop (hidden under it before)."""
    st = hops.state(fr)
    k = K.spring(fr - POP_F, 10, 9)
    st['pos'] = st['pos'] + Vector((0, 0, -0.9 * (1 - k)))
    st['grow'] = max(0.001, min(1.0, k * 1.5)) if fr < POP_F + 10 else 1.0
    return st


K.key_hero(hero, hero_state)

# ------------------------------------------------------------ slab motion ---

OFF_F = K.event_f('hud-off', T.FRAMES + 1)


def motion(s, fr, loc, scl, strength):
    """hud-off: the panels power down in a ripple out from the last button,
    flickering as they go. They stay put: the hero is still standing on one."""
    order = (s.base - K.SLABS['btn-c'].base).xy.length
    t = fr - (OFF_F + order * 0.8)
    if t > 0:
        strength *= 0.12 if t > 4 else (1 - 0.22 * t) * (0.4 if int(t) % 2 else 1)
    return loc, scl, strength


K.animate_slabs(motion)

# ------------------------------------------------- cameras, anchors, comp ---

K.cameras(hops)
K.anchors(objs={'hero': (hero.root, hero.height)})
K.compositor()
K.save()
