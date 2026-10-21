"""The Blender scene: the exploded PH Lifestyle screen as a floor of slabs in
a warm dark studio, Tobi hopping across it, everything keyed per frame from
timeline.py. Builds cache/scene.blend.

blender -b --factory-startup -P src/scene.py
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402

ROOT = T.STUDIO
GAME = os.path.normpath(os.path.join(ROOT, '..', '..', 'game'))
TEX = json.load(open(os.path.join(ROOT, 'assets', 'ui', 'textures.json')))
F = T.f
rng = random.Random(404)

# ---------------------------------------------------------------- helpers ---

def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def smooth(k):
    k = clamp(k)
    return k * k * (3 - 2 * k)


def ease_out(k):
    return 1 - (1 - clamp(k)) ** 3


def spring(t, dur=9.0, wobble=9.0):
    """0 -> 1 with one overshoot; t and dur in frames."""
    if t <= 0:
        return 0.0
    if t >= dur:
        return 1.0
    k = t / dur
    return 1 - math.exp(-5.5 * k) * math.cos(wobble * k)


def m(x, y, z=0.0):
    """UI px (+ height in metres) -> a world Vector."""
    a, b = T.px(x, y)
    return Vector((a, b, z))


def key(obj, fr, loc=True, rot=True, scale=True):
    if loc:
        obj.keyframe_insert('location', frame=fr)
    if rot:
        obj.keyframe_insert('rotation_euler', frame=fr)
    if scale:
        obj.keyframe_insert('scale', frame=fr)


def linear(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fc in fcurves(ad.action):
        for p in fc.keyframe_points:
            p.interpolation = 'LINEAR'


def fcurves(action):
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def new_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat, mat.node_tree.nodes, mat.node_tree.links


def principled(nodes):
    return next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')


# ------------------------------------------------------------------ scene ---

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, T.FRAMES
scene.render.fps = T.FPS
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_use_gpu = True      # on the CPU it costs ~45 s a frame
scene.cycles.denoising_prefilter = 'FAST'
scene.cycles.max_bounces = 6
scene.cycles.transparent_max_bounces = 16
scene.cycles.transmission_bounces = 4
scene.cycles.glossy_bounces = 3
scene.cycles.diffuse_bounces = 2
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
scene.view_settings.exposure = 0.0
scene.render.film_transparent = False
scene.render.use_persistent_data = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02

world = bpy.data.worlds.new('studio')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.018, 0.011, 0.007, 1)
bg.inputs['Strength'].default_value = 1.0

# Studio floor and the screen's bezel.
SW, SH = T.W * T.SCALE, T.H * T.SCALE
mat_floor, n, l = new_mat('floor')
p = principled(n)
p.inputs['Base Color'].default_value = (0.034, 0.021, 0.014, 1)
p.inputs['Roughness'].default_value = 0.34
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.22))
floor = bpy.context.object
floor.name = 'floor'
floor.data.materials.append(mat_floor)

mat_bezel, n, l = new_mat('bezel')
p = principled(n)
p.inputs['Base Color'].default_value = (0.012, 0.011, 0.010, 1)
p.inputs['Roughness'].default_value = 0.22
p.inputs['Coat Weight'].default_value = 0.6
# Its top sits 5 mm under the world slab: coplanar, EEVEE z-fights them black.
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.115))
bezel = bpy.context.object
bezel.name = 'bezel'
bezel.scale = (SW + 0.5, SH + 0.5, 0.22)
bezel.data.materials.append(mat_bezel)
bevel = bezel.modifiers.new('bevel', 'BEVEL')
bevel.width, bevel.segments = 0.05, 3

# The world slab: the live footage, one frame per film frame.
def seq_image(path_first, frames):
    img = bpy.data.images.load(path_first)
    img.source = 'SEQUENCE'
    return img


def image_node(nodes, img, seq_frames=None):
    tn = nodes.new('ShaderNodeTexImage')
    tn.image = img
    tn.interpolation = 'Cubic'
    if seq_frames:
        tn.image_user.frame_duration = seq_frames
        tn.image_user.frame_start = 1
        tn.image_user.frame_offset = 0
        tn.image_user.use_auto_refresh = True
    return tn


mat_world, n, l = new_mat('world-screen')
n.remove(principled(n))
out = n['Material Output']
screen_img = seq_image(os.path.join(ROOT, 'cache', 'screen', '0001.jpg'), T.FRAMES)
tn = image_node(n, screen_img, T.FRAMES)
em = n.new('ShaderNodeEmission')
em.inputs['Strength'].default_value = 1.15
l.new(tn.outputs['Color'], em.inputs['Color'])
# A little gloss on top so the screen reads as glass, not a sticker.
gl = n.new('ShaderNodeBsdfGlossy')
gl.inputs['Roughness'].default_value = 0.08
gl.inputs['Color'].default_value = (1, 1, 1, 1)
fr_ = n.new('ShaderNodeFresnel')
fr_.inputs['IOR'].default_value = 1.5
mix = n.new('ShaderNodeMixShader')
l.new(fr_.outputs['Fac'], mix.inputs['Fac'])
l.new(em.outputs['Emission'], mix.inputs[1])
l.new(gl.outputs['BSDF'], mix.inputs[2])
l.new(mix.outputs['Shader'], out.inputs['Surface'])
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.0))
world_slab = bpy.context.object
world_slab.name = 'world-slab'
world_slab.scale = (SW, SH, 1)
world_slab.data.materials.append(mat_world)
screen_mat_em = em

# ------------------------------------------------------------- the slabs ---

mat_glass, n, l = new_mat('smoked-glass')
p = principled(n)
p.inputs['Base Color'].default_value = (0.020, 0.021, 0.022, 1)
p.inputs['Roughness'].default_value = 0.18
p.inputs['Coat Weight'].default_value = 1.0
p.inputs['Coat Roughness'].default_value = 0.04
p.inputs['Specular IOR Level'].default_value = 0.6


def rounded_rect(name, w, h, r, depth, seg=6):
    """A rounded-rectangle slab, origin at the centre of its top face."""
    r = min(r, w / 2 - 1e-4, h / 2 - 1e-4)
    bm = bmesh.new()
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    top = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in pts])
    ext = bmesh.ops.extrude_face_region(bm, geom=[top])
    for v in [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z -= depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    rim = [e for e in bm.edges if len(e.link_faces) == 2 and abs(e.link_faces[0].normal.z) > 0.9 or
           len(e.link_faces) == 2 and abs(e.link_faces[1].normal.z) > 0.9]
    bmesh.ops.bevel(bm, geom=rim, offset=min(0.012, depth * 0.3), segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def ui_material(name, img, seq=None, strength=1.6):
    mat, n, l = new_mat(name)
    n.remove(principled(n))
    out = n['Material Output']
    tn = image_node(n, img, seq)
    tn.extension = 'CLIP'
    em = n.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    l.new(tn.outputs['Color'], em.inputs['Color'])
    tr = n.new('ShaderNodeBsdfTransparent')
    mix = n.new('ShaderNodeMixShader')
    l.new(tn.outputs['Alpha'], mix.inputs['Fac'])
    l.new(tr.outputs['BSDF'], mix.inputs[1])
    l.new(em.outputs['Emission'], mix.inputs[2])
    l.new(mix.outputs['Shader'], out.inputs['Surface'])
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None
    return mat, em


SLABS = {}


class Slab:
    """A HUD panel: a smoked-glass body at the element's rect and its live
    texture just above the top face. `parent` stacks it on another slab."""

    def __init__(self, name, tex, z, radius_px=16, depth=T.Z['slab'], parent=None, seq=None, strength=1.6):
        t = TEX[tex]
        el = t['el']
        self.name = name
        self.el = el
        self.cx, self.cy = el['x'] + el['w'] / 2, el['y'] + el['h'] / 2
        self.root = bpy.data.objects.new(f'{name}-root', None)
        scene.collection.objects.link(self.root)
        self.base = m(self.cx, self.cy, z)
        self.root.location = self.base
        if parent:
            self.root.parent = parent.root
            self.root.location = self.base - parent.base
        self.body = rounded_rect(f'{name}-body', el['w'] * T.SCALE, el['h'] * T.SCALE, radius_px * T.SCALE, depth)
        self.body.data.materials.append(mat_glass)
        self.body.parent = self.root
        img = bpy.data.images.load(os.path.join(ROOT, t['file']))
        if seq:
            img.source = 'SEQUENCE'
        mat, self.em = ui_material(f'{name}-ui', img, seq, strength)
        self.strength = strength
        bpy.ops.mesh.primitive_plane_add(size=1)
        face = bpy.context.object
        face.name = f'{name}-face'
        face.scale = (t['w'] * T.SCALE, t['h'] * T.SCALE, 1)
        tcx, tcy = t['x'] + t['w'] / 2, t['y'] + t['h'] / 2
        face.location = ((tcx - self.cx) * T.SCALE, -(tcy - self.cy) * T.SCALE, 0.0015)
        face.data.materials.append(mat)
        face.parent = self.root
        face.visible_shadow = False
        self.face = face
        self.top = z          # height of the top face, before any motion
        SLABS[name] = self
        self.parent = parent

    def world_top(self, x=None, y=None):
        return self.top


# Layer heights.
ZH = T.Z['hud'] + T.Z['slab']             # top of a HUD panel
ZP = T.Z['phone'] + T.Z['slab']           # top of the phone
ZT = T.Z['tile']

me_seq = T.FRAMES
hud_me = Slab('me', 'me', ZH, 16, seq=me_seq)
Slab('place', 'place', ZH, 16)
Slab('stats', 'stats', ZH, 16)
Slab('board', 'board', ZH, 14)
Slab('goal', 'goal', ZH, 14)
Slab('chat', 'chat', ZH, 18)
dock = Slab('dock', 'dock', ZH, 18)
spray = Slab('spray', 'dock-spray', ZH + ZT, 12, depth=ZT + 0.01, parent=dock)
nav = Slab('nav', 'nav', ZH, 22)
for b in ['home', 'map', 'people', 'phone', 'eyes', 'hide']:
    Slab(f'btn-{b}', f'btn-{b}', ZH + ZT, 14, depth=ZT + 0.01, parent=nav)
phone = Slab('phone', 'phone', ZP, 52, depth=0.09)
for a in ['cars', 'events', 'property', 'boutique']:
    Slab(f'app-{a}', f'app-{a}', ZP + ZT, 18, depth=ZT + 0.01, parent=phone)

# ------------------------------------------------------------------ Tobi ---

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(GAME, 'media', 'characters', 'tobi.glb'))
tobi_objs = [o for o in bpy.data.objects if o not in before]
arm = next(o for o in tobi_objs if o.type == 'ARMATURE')
for o in tobi_objs:
    if o.type == 'MESH' and o.name.startswith('Icosphere'):
        o.hide_render = True
        o.hide_viewport = True
tobi_mesh = next(o for o in tobi_objs if o.type == 'MESH' and not o.hide_render)
hero = bpy.data.objects.new('tobi-root', None)      # feet: position, yaw, squash
scene.collection.objects.link(hero)
flip = bpy.data.objects.new('tobi-flip', None)      # centre of mass: flips, leans
scene.collection.objects.link(flip)
flip.parent = hero
flip.location = (0, 0, 1.0)
arm.parent = flip
arm.location = (0, 0, -1.0)
CLIPS = {a.name: a for a in bpy.data.actions}

# The clips on the NLA: Idle all along, RunFast in the air on long leaps,
# the dance at the end.
ad = arm.animation_data or arm.animation_data_create()
ad.action = None
base_track = ad.nla_tracks.new()
base_track.name = 'idle'
idle = base_track.strips.new('Idle', 1, CLIPS['Idle'])
idle.repeat = max(1.0, (F(22) - 1) / (CLIPS['Idle'].frame_range[1] - CLIPS['Idle'].frame_range[0]))
idle.frame_end = F(22)
dance_track = ad.nla_tracks.new()
dance_track.name = 'dance'
dance = dance_track.strips.new('Dance', F(22), CLIPS['Hip_Hop_Dance'])
dance.scale = 0.9
dance.repeat = 2.0
dance.blend_in = 4
air_track = ad.nla_tracks.new()
air_track.name = 'air'
for i, h in enumerate(T.HOPS):
    if h['apex'] >= 0.9 or h['t1'] - h['t0'] >= 12:
        s = air_track.strips.new(f'air{i}', h['t0'], CLIPS['RunFast'])
        s.repeat = max(1.0, (h['t1'] - h['t0']) / 11.2)
        s.blend_in = s.blend_out = 2
bus_track = ad.nla_tracks.new()
bus_track.name = 'surf'
surf = bus_track.strips.new('surf', F(9.2), CLIPS['Alert'])
surf.frame_end = F(12.3)
surf.blend_in = surf.blend_out = 3

# ---------------------------------------------------------------- danfo ---

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(GAME, 'media', 'props', 'danfo.glb'))
danfo_mesh = next(o for o in bpy.data.objects if o not in before and o.type == 'MESH')
bus = bpy.data.objects.new('danfo', None)
scene.collection.objects.link(bus)
danfo_mesh.parent = bus
BUS_SCALE = 3.4 / 1.89
danfo_mesh.scale = (BUS_SCALE,) * 3
danfo_mesh.location = (0, 0, 0.528 * BUS_SCALE)
BUS_FACES = +1     # the model's nose points +X, the way it drives
danfo_mesh.rotation_euler = (0, 0, 0 if BUS_FACES > 0 else math.pi)
BUS_ROOF = 1.061 * BUS_SCALE
BUS_Z = ZH + 0.01

# ------------------------------------------------------------- the glass ---

# Thin glass: a fresnel gloss over a clear pass. No refraction, so the
# footage under it stays sharp and the frames stay cheap.
mat_pane, n, l = new_mat('screen-glass')
n.remove(principled(n))
lw = n.new('ShaderNodeLayerWeight')
lw.inputs['Blend'].default_value = 0.25
gl = n.new('ShaderNodeBsdfGlossy')
gl.inputs['Roughness'].default_value = 0.03
tr = n.new('ShaderNodeBsdfTransparent')
tr.inputs['Color'].default_value = (0.96, 0.97, 0.98, 1)
mix = n.new('ShaderNodeMixShader')
l.new(lw.outputs['Fresnel'], mix.inputs['Fac'])
l.new(tr.outputs['BSDF'], mix.inputs[1])
l.new(gl.outputs['BSDF'], mix.inputs[2])
l.new(mix.outputs['Shader'], n['Material Output'].inputs['Surface'])
GZ = T.Z['glass']
HOLE = (2.6, 2.0)            # metres: the panes that shatter around the sticker
sx, sy = T.px(*T.START)


def pane(name, x0, y0, x1, y1):
    bpy.ops.mesh.primitive_plane_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, GZ))
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, 1)
    o.data.materials.append(mat_pane)
    o.visible_shadow = False
    return o


hx0, hx1 = sx - HOLE[0] / 2, sx + HOLE[0] / 2
hy0, hy1 = sy - 0.35, sy + HOLE[1] - 0.35
pane('glass-l', -SW / 2, -SH / 2, hx0, SH / 2)
pane('glass-r', hx1, -SH / 2, SW / 2, SH / 2)
pane('glass-b', hx0, -SH / 2, hx1, hy0)
pane('glass-t', hx0, hy1, hx1, SH / 2)
shards = []
NX, NY = 9, 7
grid = [[Vector((hx0 + (hx1 - hx0) * i / NX + (rng.uniform(-0.4, 0.4) * (hx1 - hx0) / NX if 0 < i < NX else 0),
                 hy0 + (hy1 - hy0) * j / NY + (rng.uniform(-0.4, 0.4) * (hy1 - hy0) / NY if 0 < j < NY else 0), 0))
         for j in range(NY + 1)] for i in range(NX + 1)]
for i in range(NX):
    for j in range(NY):
        a, b, c, d = grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]
        for tri in ((a, b, c), (a, c, d)) if rng.random() < 0.5 else ((a, b, d), (b, c, d)):
            cen = sum(tri, Vector()) / 3
            me = bpy.data.meshes.new('shard')
            a_, b_, c_ = tri
            if (b_ - a_).cross(c_ - a_).z < 0:     # every shard faces up
                tri = (a_, c_, b_)
            me.from_pydata([v - cen for v in tri], [], [(0, 1, 2)])
            me.update()
            o = bpy.data.objects.new('shard', me)
            scene.collection.objects.link(o)
            o.location = (cen.x, cen.y, GZ)
            o.data.materials.append(mat_pane)
            o.visible_shadow = False
            shards.append(o)

# ----------------------------------------------------------- naira notes ---

note_img = bpy.data.images.load(os.path.join(ROOT, TEX['note']['file']))
mat_note, n, l = new_mat('note')
p = principled(n)
tn = image_node(n, note_img)
l.new(tn.outputs['Color'], p.inputs['Base Color'])
p.inputs['Roughness'].default_value = 0.7
notes = []
kick = next(e for e in T.EVENTS if e['kind'] == 'kick-spray')
for i in range(kick['notes']):
    bpy.ops.mesh.primitive_plane_add(size=1)
    o = bpy.context.object
    o.name = f'note-{i}'
    o.scale = (0.52, 0.26, 1)
    o.data.materials.append(mat_note)
    notes.append(o)

# ------------------------------------------------------------ the motion ---

def need_target(i):
    return T.HOPS[i]['to']


def hud_me_scale(fr):
    grow = next(e for e in T.EVENTS if e['kind'] == 'hud-grow')['f']
    up = spring(fr - grow, 12)
    down = spring(fr - F(9.4), 10)
    return 1 + (T.NEEDS_GROW - 1) * (up - down)


def hud_me_lift(fr):
    return 0.12 * (hud_me_scale(fr) - 1) / (T.NEEDS_GROW - 1)


def bus_x(fr):
    """The danfo's x in UI px: in from the left, along the bottom, out right."""
    pts = [(F(8.0), -420), (F(9), T.BUS_FROM[0]), (F(12.3), T.BUS_TO[0]), (F(13.2), 2500)]
    if fr <= pts[0][0]:
        return pts[0][1]
    for (f0, x0), (f1, x1) in zip(pts, pts[1:]):
        if fr <= f1:
            k = (fr - f0) / (f1 - f0)
            if f0 == pts[0][0]:
                k = ease_out(k)
            elif f1 == pts[-1][0]:
                k = k * k
            return x0 + (x1 - x0) * k
    return pts[-1][1]


def bus_pos(fr):
    p = m(bus_x(fr), T.BUS_FROM[1], BUS_Z)
    p.z += 0.03 * math.sin(fr * 1.3)   # the road under a danfo is never flat
    return p


def tile_top(name):
    s = SLABS[name]
    return s.top


def landing(i, fr):
    """Where hop i lands, at frame fr (the bus moves)."""
    h = T.HOPS[i]
    if h['to'] == 'bus':
        return bus_pos(fr) + Vector((0, 0, BUS_ROOF))
    x, y = h['to']
    if i < 4:   # the needs rows on the grown panel
        return m(x, y, ZH + hud_me_lift(F(6)))
    if i == 5:
        return m(x, y, tile_top('spray'))
    if i == 6:
        return m(x, y, tile_top('btn-phone'))
    if 7 <= i <= 10:
        return m(x, y - 12, tile_top(['app-cars', 'app-events', 'app-property', 'app-boutique'][i - 7]))
    if i == 11:
        return m(x, y, tile_top('btn-hide'))
    return m(x, y, GZ + 0.006)


def tobi_at(fr):
    """Feet position, yaw (deg), squash (z scale), flip angle, lean."""
    start = m(*T.START, GZ + 0.004)
    pos, yaw, flip_a, lean = start.copy(), 0.0, 0.0, 0.0
    prev_end, prev_land = start, None
    squash = 1.0
    for i, h in enumerate(T.HOPS):
        t0, t1 = h['t0'], h['t1']
        p0 = prev_end if T.HOPS[i - 1]['to'] != 'bus' or i == 0 else landing(i - 1, t0)
        if i > 0 and T.HOPS[i - 1]['to'] == 'bus':
            p0 = bus_pos(t0) + Vector((0, 0, BUS_ROOF))
        p1 = landing(i, t1)
        d = p1 - p0
        heading = math.degrees(math.atan2(d.y, d.x)) + 90 if d.xy.length > 0.05 else yaw
        if fr < t0:
            break
        if fr <= t1:
            k = (fr - t0) / (t1 - t0)
            top = max(p0.z, p1.z) + h['apex']
            hgt = top - min(p0.z, p1.z)
            # A parabola through p0 and p1 peaking `apex` above the higher end.
            zz = p0.z + (p1.z - p0.z) * k + 4 * (top - (p0.z + p1.z) / 2) * k * (1 - k)
            pos = p0.lerp(p1, k)
            pos.z = zz
            yaw = heading
            flip_a = -360 * h['spin'] * smooth((k - 0.1) / 0.8)
            lean = 12 * math.sin(math.pi * k)
            # Stretch on the way up, round at the apex.
            squash = 1 + 0.14 * max(0, 1 - 2 * k) - 0.04 * max(0, 2 * k - 1)
            return dict(pos=pos, yaw=yaw, squash=squash, flip=flip_a, lean=lean, air=True)
        prev_end = p1
        pos = p1 if h['to'] != 'bus' else bus_pos(fr) + Vector((0, 0, BUS_ROOF))
        yaw = heading
        prev_land = t1
    # On the ground: landing squash, take-off anticipation, a slow turn to camera.
    nxt = next((h for h in T.HOPS if h['t0'] > fr), None)
    if prev_land is not None:
        t = fr - prev_land
        if t < 2:
            squash = 0.78 + 0.05 * t
        else:
            squash = 1 - 0.12 * (1 - spring(t - 2, 8, 12))
    if nxt and 0 <= nxt['t0'] - fr <= 3:
        squash = min(squash, 1 - 0.16 * (1 - (nxt['t0'] - fr) / 3))
    if prev_land is not None and T.HOPS[[h['t1'] for h in T.HOPS].index(prev_land)]['to'] == 'bus':
        yaw = 0.0
        lean = -10 + 4 * math.sin(fr * 0.4)
    elif prev_land is not None and fr - prev_land > 4:
        yaw = yaw * (1 - smooth((fr - prev_land - 4) / 10)) if abs(yaw) < 120 else yaw
    if prev_land is not None and prev_land == T.HOPS[-1]['t1']:
        yaw = -12.0
    return dict(pos=pos, yaw=yaw, squash=squash, flip=0.0, lean=lean, air=False)


def sticker(fr, st):
    """Before the pop he is a flat sticker on the glass at his spot."""
    peel_f = next(e['f'] for e in T.EVENTS if e['kind'] == 'peel')
    pop_f = next(e['f'] for e in T.EVENTS if e['kind'] == 'pop')
    flat = 0.02 + 0.98 * spring(fr - pop_f, 7, 10)
    lie = -90 * (1 - spring(fr - peel_f, 10, 8))
    knock = 0
    for e in T.EVENTS:
        if e['kind'] == 'knock' and 0 <= fr - e['f'] < 6:
            knock = math.sin(math.pi * (fr - e['f']) / 6) * 8
    st['flat'] = flat
    st['lie'] = lie + knock
    return st


SAMPLE = range(1, T.FRAMES + 1)
for fr in SAMPLE:
    st = sticker(fr, tobi_at(fr))
    hero.location = st['pos']
    hero.rotation_euler = Euler((math.radians(st['lie']), 0, math.radians(st['yaw'])))
    sq = st['squash']
    xy = 1 / math.sqrt(max(sq, 0.2))
    hero.scale = (xy, xy * st['flat'], sq)
    key(hero, fr)
    flip.rotation_euler = Euler((math.radians(st['flip'] + st['lean']), 0, 0))
    key(flip, fr, loc=False, scale=False)
linear(hero)
linear(flip)

# The danfo.
for fr in SAMPLE:
    bus.location = bus_pos(fr)
    bus.hide_render = not (F(7.8) <= fr <= F(13.4))
    key(bus, fr, rot=False, scale=False)
    bus.keyframe_insert('hide_render', frame=fr)
linear(bus)

# Shards: burst outward from his feet on the pop, spin, fall away.
pop_f = next(e['f'] for e in T.EVENTS if e['kind'] == 'pop')
centre = Vector((sx, sy, GZ))
for o in shards:
    home = o.location.copy()
    away = (home - centre)
    away.z = 0
    dist = away.length
    dirn = away.normalized() if dist > 1e-3 else Vector((1, 0, 0))
    delay = dist * 3
    v = dirn * rng.uniform(2.5, 5.5) + Vector((0, 0, rng.uniform(3.0, 6.0)))
    spin = Vector((rng.uniform(-12, 12), rng.uniform(-12, 12), rng.uniform(-6, 6)))
    for fr in SAMPLE:
        t = (fr - pop_f - delay) / T.FPS
        if t <= 0:
            o.location, o.rotation_euler, o.scale = home, (0, 0, 0), (1, 1, 1)
        else:
            o.location = home + v * t + Vector((0, 0, -4.9 * t * t))
            o.rotation_euler = Euler(tuple(s * t for s in spin))
            o.scale = (1,) * 3 if t < 0.55 else (max(0.0, 1 - (t - 0.55) / 0.25),) * 3
        key(o, fr)
    linear(o)

# Slab motion: the needs panel grows, presses dip, the phone rises, Hide
# tucks every panel away in a ripple from the button.
presses = [e for e in T.EVENTS if e['kind'] == 'press']
press_names = {'spray': 'spray', '#btn-phone': 'btn-phone', '#btn-hide': 'btn-hide',
               'cars': 'app-cars', 'events': 'app-events', 'property': 'app-property', 'boutique': 'app-boutique'}
landings = {}
for i, h in enumerate(T.HOPS):
    tgt = {5: 'spray', 6: 'btn-phone', 11: 'btn-hide'}.get(i) or (['app-cars', 'app-events', 'app-property', 'app-boutique'][i - 7] if 7 <= i <= 10 else None)
    if i < 4:
        tgt = 'me'
    if tgt:
        landings.setdefault(tgt, []).append(h['t1'])
off_f = next(e['f'] for e in T.EVENTS if e['kind'] == 'hud-off')
hide_pt = m(*T.px_inverse(0, 0)) if hasattr(T, 'px_inverse') else SLABS['btn-hide'].base
rise_f = next(e['f'] for e in T.EVENTS if e['kind'] == 'phone-rise')


def press_dip(name, fr):
    d = 0.0
    for e in presses:
        if press_names.get(e['target']) == name:
            t = fr - e['f']
            if 0 <= t < 3:
                d = max(d, 0.045 * (t + 1) / 3)
            elif 3 <= t < 12:
                d = max(d, 0.045 * (1 - spring(t - 3, 8, 12)))
    for t1 in landings.get(name, []):
        t = fr - t1
        if 0 <= t < 10:
            d = max(d, 0.02 * math.sin(math.pi * t / 10))
    return d


def flash(name, fr):
    for e in presses:
        if press_names.get(e['target']) == name and 0 <= fr - e['f'] < 8:
            return 1 + 2.2 * (1 - (fr - e['f']) / 8)
    return 1.0


for s in SLABS.values():
    s.root_home = s.root.location.copy()
    order = (s.base - SLABS['btn-hide'].base).xy.length
    tuck_f = off_f + order * 0.9 + (6 if s.name == 'btn-hide' else 0)
    if s.name == 'btn-hide':
        tuck_f = F(21.0)
    for fr in SAMPLE:
        loc = s.root_home.copy()
        scl = 1.0
        loc.z -= press_dip(s.name, fr)
        if s.name == 'me':
            g = hud_me_scale(fr)
            el = s.el
            # grow about the panel's top-left corner, and lift above its neighbours
            cx = T.NEEDS_ORIGIN[0] + (s.cx - T.NEEDS_ORIGIN[0]) * g
            cy = T.NEEDS_ORIGIN[1] + (s.cy - T.NEEDS_ORIGIN[1]) * g
            loc = m(cx, cy, s.top + hud_me_lift(fr)) - Vector((0, 0, press_dip('me', fr)))
            scl = g
        if s.name == 'phone':
            k = spring(fr - rise_f, 9, 8)
            start = SLABS['btn-phone'].base
            loc = start.lerp(s.root_home, smooth((fr - rise_f) / 9)) if fr < rise_f + 9 else loc
            scl = max(0.0001, k) if fr >= rise_f else 0.0001
        # Hide: power down, then sink and shrink into the world.
        t = fr - tuck_f
        if s.parent is None or s.name == 'btn-hide':
            if t > 0:
                k = smooth(t / 8)
                loc = loc.copy()
                loc.z -= 0.32 * k
                scl *= max(0.0001, 1 - k)
        s.root.location = loc
        s.root.scale = (scl, scl, scl if s.name != 'me' else 1)
        key(s.root, fr, rot=False)
        strength = s.strength * flash(s.name, fr)
        if fr >= off_f + order * 0.6:
            dt = fr - (off_f + order * 0.6)
            strength *= 0 if dt > 4 else (1 - dt / 4) * (0.4 if dt % 2 else 1)
        s.em.inputs['Strength'].default_value = strength
        s.em.inputs['Strength'].keyframe_insert('default_value', frame=fr)
    linear(s.root)

# Notes: kicked off Spray money, they arc out over the world and flutter down.
foot = SLABS['spray'].base + Vector((0, 0, 0.1))
for i, o in enumerate(notes):
    launch = kick['f'] + 2 * i
    tgt = m(rng.uniform(1100, 1550), rng.uniform(360, 760), GZ + 0.01 + 0.004 * i)
    spin = rng.uniform(-1, 1)
    for fr in SAMPLE:
        t = (fr - launch) / 14
        if t <= 0:
            o.location, o.scale = foot, (0.0001,) * 3
            o.rotation_euler = (0, 0, 0)
        else:
            k = min(1, t)
            pos = foot.lerp(tgt, ease_out(k))
            pos.z = foot.z + (tgt.z - foot.z) * k + 2.4 * math.sin(math.pi * k) * (1 - 0.3 * k)
            flutter = 0 if k >= 1 else math.sin(t * 9 + i) * 0.6 * (1 - k)
            o.location = pos
            o.rotation_euler = Euler((flutter, 0.4 * flutter, spin * 6 * k + i))
            o.scale = (0.52, 0.26, 1) if fr < off_f else (0.52 * max(0.0001, 1 - (fr - off_f) / 10), 0.26 * max(0.0001, 1 - (fr - off_f) / 10), 1)
        key(o, fr)
    linear(o)

# --------------------------------------------------------------- lights ---

def area(name, loc, look, size, energy, color):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.size = size
    ld.energy = energy
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    ob.visible_glossy = False      # never a hot spot on the glass
    ob.visible_camera = False
    return ob


area('key', (-9, -7, 13), (0, 0, 0), 9, 2600, (1.0, 0.93, 0.85))
area('rim', (7, 13, 5), (0, 0, 0.5), 7, 1700, (1.0, 0.55, 0.28))
area('fill', (10, -12, 6), (0, 0, 0), 10, 500, (0.85, 0.9, 1.0))

# --------------------------------------------------------------- camera ---

def tobi_eye(fr):
    st = tobi_at(fr)
    return st['pos'] + Vector((0, 0, 1.0))


def lerp(a, b, k):
    return a + (b - a) * k


def cam_key_target(c, fr, follow):
    if c['look'] == 'tobi':
        return follow[fr]
    return m(*c['look'], 0.0)


# Tobi's eye line, smoothed so the camera follows rather than tracks.
raw = {fr: tobi_eye(fr) for fr in SAMPLE}
def smoothed(rate):
    out, acc = {}, raw[1]
    for fr in SAMPLE:
        acc = acc.lerp(raw[fr], rate)
        out[fr] = acc.copy()
    return out


follow = smoothed(0.22)



def build_camera(name, CK, follow):
    """A camera keyed every frame from a list of timeline camera keys."""
    cam_data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_data)
    scene.collection.objects.link(cam)
    cam_data.sensor_width = 36
    cam_data.dof.use_dof = True
    cam_data.clip_start = 0.05
    cam_data.clip_end = 400
    for fr in SAMPLE:
        i = max(j for j, c in enumerate(CK) if c['f'] <= fr) if fr >= CK[0]['f'] else 0
        a, b = CK[i], CK[min(i + 1, len(CK) - 1)]
        k = 0 if a is b else smooth((fr - a['f']) / (b['f'] - a['f']))
        ta, tb = cam_key_target(a, fr, follow), cam_key_target(b, fr, follow)
        target = ta.lerp(tb, k)
        dist, elev, yaw = lerp(a['dist'], b['dist'], k), lerp(a['elev'], b['elev'], k), lerp(a['yaw'], b['yaw'], k)
        lens, fstop = lerp(a['lens'], b['lens'], k), lerp(a['fstop'], b['fstop'], k)
        e, y = math.radians(elev), math.radians(yaw)
        off = Vector((math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e))) * dist
        # Shake on the pop and the kick, gone in a few frames.
        shake = Vector()
        for ev in T.EVENTS:
            if ev['kind'] in ('pop', 'kick-spray', 'land-world') and 0 <= fr - ev['f'] < 8:
                amp = (0.06 if ev['kind'] == 'pop' else 0.03) * (1 - (fr - ev['f']) / 8)
                shake += Vector((math.sin(fr * 7.1), math.cos(fr * 5.3), math.sin(fr * 6.2))) * amp
        cam.location = target + off + shake
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam_data.lens = lens
        cam_data.dof.aperture_fstop = fstop
        cam_data.dof.focus_distance = (follow[fr] - cam.location).length if a['look'] == 'tobi' or b['look'] == 'tobi' else (target - cam.location).length
        key(cam, fr, scale=False)
        cam_data.keyframe_insert('lens', frame=fr)
        cam_data.dof.keyframe_insert('aperture_fstop', frame=fr)
        cam_data.dof.keyframe_insert('focus_distance', frame=fr)
    linear(cam)
    return cam


scene.camera = build_camera('cam', T.CAMERA, follow)
# Its own framing, and a tighter follow: the narrow frame loses Tobi on the flip.
build_camera('cam-9x16', T.CAMERA_9X16, smoothed(0.4))

# ------------------------------------------------------------ compositor ---

def compositor():
    tree = bpy.data.node_groups.new('comp', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    nodes, links = tree.nodes, tree.links
    rl = nodes.new('CompositorNodeRLayers')
    glare = nodes.new('CompositorNodeGlare')
    for name, val in (('Type', 'Bloom'), ('Quality', 'High')):
        if name in glare.inputs:
            try:
                glare.inputs[name].default_value = val
            except TypeError:
                pass
    if hasattr(glare, 'glare_type'):
        glare.glare_type = 'BLOOM'
    for name, val in (('Threshold', 0.85), ('Strength', 0.35), ('Size', 0.55)):
        if name in glare.inputs:
            glare.inputs[name].default_value = val
    out = tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    go = nodes.new('NodeGroupOutput')
    links.new(rl.outputs['Image'], glare.inputs['Image'])
    links.new(glare.outputs['Image'], go.inputs[0])


compositor()

# Metal GPU.
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'
prefs.get_devices()
for d in prefs.devices:
    d.use = True

out_blend = os.path.join(ROOT, 'cache', 'scene.blend')
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print('## saved', out_blend, 'shards', len(shards), 'slabs', len(SLABS))
