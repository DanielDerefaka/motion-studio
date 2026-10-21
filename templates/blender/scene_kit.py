"""scene_kit: the reusable parts of a motion-studio Blender scene.

The exploded product screen as a floor of glowing UI slabs under glass, in a
warm dark studio; a hero hopping across the buttons; cameras, anchors and the
compositor. Everything is keyed per frame from timeline.py, so the scene
holds no time or UI position of its own.

A film's src/scene.py imports it (both files sit in <studio>/src/ next to
timeline.py):

    sys.path.insert(0, os.path.dirname(__file__))
    import timeline as T
    import scene_kit as K

    K.studio()                        # empty scene, render settings, floor, world
    ...slabs, hero, hops, cameras...  # see the demo scene.py
    K.save()                          # cache/scene.blend

Space: the product's screen at T.W x T.H UI pixels, laid flat as a floor,
screen centre at the origin, +y towards the top of the screen. The cameras
sit on the -y side (the bottom of the screen is nearest the lens). A model's
front is -y (glTF imports that way), so yaw 0 faces the camera.

Tested on Blender 5.2 (layered actions, menu-socket compositor nodes); the
fallbacks keep 4.x working.
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402

ROOT = T.STUDIO
FRAMES = range(1, T.FRAMES + 1)
SW, SH = T.W * T.SCALE, T.H * T.SCALE      # the screen in metres
GZ = T.Z.get('glass', 0.03)                # the glass sheet over the base slab
SLABS = {}                                 # name -> Slab, every UI panel in the scene
rng = random.Random(404)


def scene():
    return bpy.context.scene


# ------------------------------------------------------------ the motion ---

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


def lerp(a, b, k):
    return a + (b - a) * k


def m(x, y, z=0.0):
    """UI px (+ height in metres) -> a world Vector."""
    a, b = T.px(x, y)
    return Vector((a, b, z))


def events(kind, **match):
    return [e for e in T.EVENTS if e['kind'] == kind and all(e.get(k) == v for k, v in match.items())]


def event_f(kind, default=None, **match):
    """Frame of the first event of a kind, or `default` when the film has none."""
    es = events(kind, **match)
    return es[0]['f'] if es else default


# -------------------------------------------------------------- keyframes ---

def key(obj, fr, loc=True, rot=True, scale=True):
    if loc:
        obj.keyframe_insert('location', frame=fr)
    if rot:
        obj.keyframe_insert('rotation_euler', frame=fr)
    if scale:
        obj.keyframe_insert('scale', frame=fr)


def key_value(socket, value, fr):
    """Key a node socket's default_value (an emission strength, a colour)."""
    socket.default_value = value
    socket.keyframe_insert('default_value', frame=fr)


def fcurves(action):
    """Every F-curve of an action. Blender 5 keeps them in layers -> strips ->
    channelbags instead of action.fcurves."""
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def linear(*ids):
    """Linear interpolation between the per-frame keys: motion blur samples
    between frames, and a Bezier between two keys a frame apart overshoots.
    Pass objects, camera data, materials (their node trees are keyed)."""
    for idb in ids:
        for target in (idb, getattr(idb, 'node_tree', None)):
            ad = getattr(target, 'animation_data', None)
            if ad and ad.action:
                for fc in fcurves(ad.action):
                    for p in fc.keyframe_points:
                        p.interpolation = 'LINEAR'


# -------------------------------------------------------------- materials ---

def hex_rgb(h, a=1.0):
    """'#rrggbb' -> linear RGBA, for colours taken from the brand (T.COLORS)."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (a,)


def new_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat, mat.node_tree.nodes, mat.node_tree.links


def principled(nodes):
    return next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')


def set_in(node, name, value):
    """Set an input if this Blender has it (socket names move between versions)."""
    if name in node.inputs:
        node.inputs[name].default_value = value


def path(p):
    """A path from textures.json (relative to the studio) or absolute."""
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_textures(file=None):
    """The capture step's textures.json: {id: {file, x, y, w, h, el: {x, y, w, h},
    crop?: [x, y, w, h]}}. x/y/w/h is the UI rect the PNG covers (padded for the
    panel's shadow), el the element itself; crop is a sub-rect in image pixels
    when several panels share one sheet."""
    file = file or os.path.join(ROOT, 'assets', 'ui', 'textures.json')
    data = json.load(open(file))
    return {k: v for k, v in data.items() if isinstance(v, dict) and 'file' in v}


def load_image(p, seq=None):
    """A PNG, or the first file of a numbered sequence (NNNN.png / NNNN.jpg)
    when seq is a frame count: one texture frame per film frame."""
    img = bpy.data.images.load(path(p), check_existing=True)
    if seq:
        img.source = 'SEQUENCE'
    return img


def image_node(nodes, img, seq=None):
    tn = nodes.new('ShaderNodeTexImage')
    tn.image = img
    tn.interpolation = 'Cubic'
    if seq:
        tn.image_user.frame_duration = seq
        tn.image_user.frame_start = 1
        tn.image_user.frame_offset = 0
        tn.image_user.use_auto_refresh = True
    return tn


def crop_uv(nodes, links, tn, img, crop):
    """Map the plane's 0..1 UVs onto a crop [x, y, w, h] (image px, top-left)."""
    iw, ih = img.size[0] or 1, img.size[1] or 1
    x, y, w, h = crop
    uv = nodes.new('ShaderNodeTexCoord')
    mp = nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (w / iw, h / ih, 1)
    mp.inputs['Location'].default_value = (x / iw, 1 - (y + h) / ih, 0)
    links.new(uv.outputs['UV'], mp.inputs['Vector'])
    links.new(mp.outputs['Vector'], tn.inputs['Vector'])


def black_glass(p, rough=0.32, spec=0.1):
    """Glossy black glass: almost no specular, so it reads as a dark screen
    with a soft sheen rather than a mirror of the studio."""
    p.inputs['Base Color'].default_value = (0.012, 0.012, 0.013, 1)
    p.inputs['Roughness'].default_value = rough
    set_in(p, 'Specular IOR Level', spec)     # 4.x+ name
    set_in(p, 'Specular', spec)               # 3.x name


_GLASS_BODY = None


def glass_body():
    """One shared material for every slab's body."""
    global _GLASS_BODY
    if _GLASS_BODY is None:
        _GLASS_BODY, n, _ = new_mat('slab-glass')
        black_glass(principled(n), rough=0.28, spec=0.12)
    return _GLASS_BODY


def ui_material(name, img=None, color=None, strength=1.6, seq=None, crop=None):
    """The panel's UI as emission under glossy black glass. `img` is a texture
    (its alpha cuts the panel's shape); without one, a flat `color` glows.
    Returns (material, emission-strength socket) so presses can flash it."""
    mat, n, l = new_mat(name)
    p = principled(n)
    black_glass(p)
    if img is not None:
        tn = image_node(n, img, seq)
        tn.extension = 'CLIP'
        if crop:
            crop_uv(n, l, tn, img, crop)
        l.new(tn.outputs['Color'], p.inputs['Emission Color'])
        l.new(tn.outputs['Alpha'], p.inputs['Alpha'])
    else:
        p.inputs['Emission Color'].default_value = color or (0.8, 0.8, 0.8, 1)
    p.inputs['Emission Strength'].default_value = strength
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'   # EEVEE: alpha edges without sorting
    elif hasattr(mat, 'blend_method'):
        mat.blend_method = 'HASHED'
    return mat, p.inputs['Emission Strength']


def emit_material(name, color, strength=1.0):
    mat, n, l = new_mat(name)
    n.remove(principled(n))
    em = n.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = color
    em.inputs['Strength'].default_value = strength
    l.new(em.outputs['Emission'], n['Material Output'].inputs['Surface'])
    return mat


# ----------------------------------------------------------------- meshes ---

def link(ob):
    scene().collection.objects.link(ob)
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    e = link(bpy.data.objects.new(name, None))
    e.parent = parent
    e.location = loc
    return e


def plane(name, w, h, loc=(0, 0, 0), mat=None):
    """A w x h plane facing up, UVs 0..1 (top of the texture at +y)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = c
    ob = link(bpy.data.objects.new(name, me))
    ob.location = loc
    if mat:
        me.materials.append(mat)
    return ob


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
    # Bevel the top and bottom rims so the edge catches a thin line of light.
    rim = [e for e in bm.edges if len(e.link_faces) == 2 and any(abs(fc.normal.z) > 0.9 for fc in e.link_faces)]
    bmesh.ops.bevel(bm, geom=rim, offset=min(0.012, depth * 0.3), segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    return link(bpy.data.objects.new(name, me))


def label(text, parent, size=0.3, loc=(0, 0, 0.004), color=(1, 1, 1, 1), strength=2.0):
    """Flat glowing text on a slab, for films without captured textures (the
    demo). Real films draw their labels into the captured UI instead."""
    cu = bpy.data.curves.new(f'label-{text}', 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    ob = link(bpy.data.objects.new(f'label-{parent.name}', cu))
    ob.parent = parent
    ob.location = loc
    cu.materials.append(emit_material(f'label-{parent.name}', color, strength))
    ob.visible_shadow = False
    return ob


# ----------------------------------------------------------------- studio ---

def studio(world=(0.018, 0.011, 0.007), exposure=0.0, floor=(0.05, 0.032, 0.021),
           backdrop=True, fmt='16x9'):
    """An empty scene with the film's settings, a warm dark world and a floor
    that falls off to black, curving up into a backdrop behind the screen."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = scene()
    sc.frame_start, sc.frame_end = 1, T.FRAMES
    sc.render.fps = T.FPS
    sc.render.resolution_x, sc.render.resolution_y = T.FORMATS[fmt]
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = 'AgX'
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            pass
    sc.view_settings.exposure = exposure
    # Cycles: the `cycles` render. Denoise on the GPU: on the CPU it costs ~45 s a frame.
    cy = sc.cycles
    cy.samples = 96
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.denoiser = 'OPENIMAGEDENOISE'
    if hasattr(cy, 'denoising_use_gpu'):
        cy.denoising_use_gpu = True
    cy.denoising_prefilter = 'FAST'
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 2, 3
    cy.transmission_bounces, cy.transparent_max_bounces = 4, 16
    # EEVEE: the default render.
    use_eevee(sc)

    wd = bpy.data.worlds.new('studio')
    sc.world = wd
    wd.use_nodes = True
    bg = wd.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = world + (1,)
    bg.inputs['Strength'].default_value = 1.0

    # The floor: warm under the screen, black by ~3 screen widths out.
    mat, n, l = new_mat('floor')
    p = principled(n)
    p.inputs['Roughness'].default_value = 0.34
    geo = n.new('ShaderNodeNewGeometry')
    ln = n.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    mr = n.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = SW * 0.4
    mr.inputs['From Max'].default_value = SW * 2.2
    mix = n.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = floor + (1,)
    mix.inputs['B'].default_value = tuple(c * 0.12 for c in floor) + (1,)
    l.new(geo.outputs['Position'], ln.inputs[0])
    l.new(ln.outputs['Value'], mr.inputs['Value'])
    l.new(mr.outputs['Result'], mix.inputs['Factor'])
    l.new(mix.outputs['Result'], p.inputs['Base Color'])
    sweep(mat, backdrop)
    return sc


def sweep(mat, backdrop=True, z=-0.22):
    """The floor as one mesh: flat under the screen, then (with backdrop) a
    curve up into a wall far behind it, so a low camera never sees a horizon."""
    half = 200.0
    yb, r, top = SH / 2 + 14, 8.0, 40.0
    prof = [(-half, z), (yb, z)]
    if backdrop:
        prof += [(yb + r * math.sin(a), z + r - r * math.cos(a)) for a in (math.radians(i * 9) for i in range(1, 11))]
        prof.append((yb + r, z + top))
    me = bpy.data.meshes.new('floor')
    verts = [(x, y, zz) for y, zz in prof for x in (-half, half)]
    faces = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(len(prof) - 1)]
    me.from_pydata(verts, [], faces)
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(mat)
    return link(bpy.data.objects.new('floor', me))


def use_eevee(sc=None, samples=32):
    sc = sc or scene()
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    sc.eevee.taa_render_samples = samples
    if hasattr(sc.eevee, 'use_raytracing'):
        sc.eevee.use_raytracing = True
    sc.render.use_motion_blur = True
    hide_lights_from_glass(sc)


def use_cycles(sc=None, samples=96, denoise=True):
    sc = sc or scene()
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = denoise
    return gpu(sc)


def gpu(sc=None):
    """Use the first GPU backend this machine has for Cycles; CPU otherwise.
    Returns its name. (EEVEE always draws on the GPU Blender started with.)"""
    sc = sc or scene()
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == kind]
        if devs:
            for d in prefs.devices:
                d.use = d.type == kind
            sc.cycles.device = 'GPU'
            return f'{kind} ({", ".join(d.name for d in devs)})'
    prefs.compute_device_type = 'NONE'
    sc.cycles.device = 'CPU'
    return 'CPU'


def use_format(sc, fmt):
    """Resolution and camera for a format; the base slab's footage switches to
    cache/world-<fmt>/ when the film made one (a tall end card, say)."""
    sc.render.resolution_x, sc.render.resolution_y = T.FORMATS[fmt]
    name = 'cam' if fmt == '16x9' else f'cam-{fmt}'
    sc.camera = bpy.data.objects.get(name) or bpy.data.objects['cam']
    for img in bpy.data.images:
        home = img.get('home') or img.filepath.replace('\\', '/')
        if '/cache/world/' not in home:
            continue
        img['home'] = home
        alt = home.replace('/cache/world/', f'/cache/world-{fmt}/')
        img.filepath = alt if os.path.isdir(os.path.dirname(bpy.path.abspath(alt))) else home
    return sc.camera


# ----------------------------------------------------------------- lights ---

def area(name, loc, look, size, energy, color):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.size = size
    ld.energy = energy
    ld.color = color
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    ob.visible_camera = False
    ob.visible_glossy = False      # Cycles: never a white block on the glass
    ld.specular_factor = 0.0       # EEVEE's way of saying the same
    return ob


def hide_lights_from_glass(sc=None):
    """The prompt pack's lesson: glass reflects the lights as white blocks.
    Every light stays out of glossy rays (Cycles) and specular (EEVEE)."""
    for o in (sc or scene()).objects:
        if o.type == 'LIGHT':
            o.visible_glossy = False
            o.data.specular_factor = 0.0


def studio_lights(energy=1.0):
    """Key from the top left, a warm rim from behind, a soft top; scaled to the
    screen so a bigger UI space gets the same light."""
    s = max(SW, SH) / 19.2
    e = energy * s * s
    return dict(
        key=area('key', (-9 * s, -7 * s, 13 * s), (0, 0, 0), 9 * s, 2600 * e, (1.0, 0.93, 0.85)),
        rim=area('rim', (7 * s, 13 * s, 5 * s), (0, 0, 0.5), 7 * s, 1700 * e, (1.0, 0.55, 0.28)),
        top=area('top', (0, -2 * s, 16 * s), (0, 0, 0), 12 * s, 900 * e, (1.0, 0.96, 0.92)),
    )


# ------------------------------------------------------------- base slab ---

class Base:
    """The base slab: the world under the UI (live footage, one frame per film
    frame) on a dark bezel. Hops with on='world' land on the glass above it."""

    def __init__(self, img=None, seq=None, color=(0.02, 0.02, 0.025, 1), strength=1.15):
        self.name = 'world'
        self.top = GZ + 0.004
        mat, n, l = new_mat('world-screen')
        n.remove(principled(n))
        em = n.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = strength
        if img is not None:
            tn = image_node(n, img, seq)
            l.new(tn.outputs['Color'], em.inputs['Color'])
        else:
            em.inputs['Color'].default_value = color
        # A little gloss on top so the screen reads as glass, not a sticker.
        gl = n.new('ShaderNodeBsdfGlossy')
        gl.inputs['Roughness'].default_value = 0.08
        fr = n.new('ShaderNodeFresnel')
        fr.inputs['IOR'].default_value = 1.5
        mix = n.new('ShaderNodeMixShader')
        l.new(fr.outputs['Fac'], mix.inputs['Fac'])
        l.new(em.outputs['Emission'], mix.inputs[1])
        l.new(gl.outputs['BSDF'], mix.inputs[2])
        l.new(mix.outputs['Shader'], n['Material Output'].inputs['Surface'])
        self.em = em.inputs['Strength']
        self.strength = strength
        self.mat = mat
        self.slab = plane('world-slab', SW, SH, (0, 0, 0), mat)
        bm_mat, bn, _ = new_mat('bezel')
        p = principled(bn)
        p.inputs['Base Color'].default_value = (0.012, 0.011, 0.010, 1)
        p.inputs['Roughness'].default_value = 0.22
        set_in(p, 'Coat Weight', 0.6)
        # Its top sits 5 mm under the world slab: coplanar, EEVEE z-fights them black.
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.115))
        bz = bpy.context.object
        bz.name = 'bezel'
        bz.scale = (SW + 0.5, SH + 0.5, 0.22)
        bz.data.materials.append(bm_mat)
        bv = bz.modifiers.new('bevel', 'BEVEL')
        bv.width, bv.segments = 0.05, 3
        self.bezel = bz


# ------------------------------------------------------------- the slabs ---

class Slab:
    """A UI panel lifted off the screen: a black-glass body at the element's
    rect, its texture glowing just above the top face. Origin (root) at the
    centre of the top face, `top` metres up. `parent` stacks it on another
    slab (a button on its bar) so it rides that slab's motion.

    rect   the element, UI px {x, y, w, h}
    tex    image path (studio-relative or absolute); seq = frame count when
           it is a per-frame sequence (NNNN.png); crop = [x, y, w, h] px
    face   the UI rect the texture covers (capture pads it for the shadow)
    color  flat emission when there is no texture
    """

    def __init__(self, name, rect, top, tex=None, seq=None, crop=None, face=None, color=None,
                 radius_px=16, depth=None, parent=None, strength=1.6):
        depth = depth or T.Z.get('slab', 0.05)
        self.name, self.el, self.top, self.parent = name, rect, top, parent
        self.cx, self.cy = T.centre(rect)
        self.base = m(self.cx, self.cy, top)
        self.root = empty(f'{name}-root')
        self.root.location = self.base
        if parent:
            self.root.parent = parent.root
            self.root.location = self.base - parent.base
        self.body = rounded_rect(f'{name}-body', rect['w'] * T.SCALE, rect['h'] * T.SCALE, radius_px * T.SCALE, depth)
        self.body.data.materials.append(glass_body())
        self.body.parent = self.root
        img = load_image(tex, seq) if tex else None
        self.mat, self.em = ui_material(f'{name}-ui', img, color, strength, seq, crop)
        self.strength = strength
        face = face or rect
        fcx, fcy = T.centre(face)
        self.face = plane(f'{name}-face', face['w'] * T.SCALE, face['h'] * T.SCALE,
                          ((fcx - self.cx) * T.SCALE, -(fcy - self.cy) * T.SCALE, 0.0015), self.mat)
        self.face.parent = self.root
        self.face.visible_shadow = False
        SLABS[name] = self

    @classmethod
    def from_tex(cls, name, t, top, **kw):
        """A slab from one textures.json entry."""
        rect = t.get('el') or t
        face = dict(x=t['x'], y=t['y'], w=t['w'], h=t['h'])
        return cls(name, rect, top, tex=t['file'], crop=t.get('crop'), face=face, **kw)

    def at(self, x=None, y=None):
        """A UI px on this slab -> local offset from its root (anchors, landings)."""
        x = self.cx if x is None else x
        y = self.cy if y is None else y
        return Vector(((x - self.cx) * T.SCALE, -(y - self.cy) * T.SCALE, 0))


def layer_top(z):
    """Top of a slab on a named layer (T.Z): the layer height plus its thickness."""
    return T.Z.get(z, 0.0) + T.Z.get('slab', 0.05)


# ------------------------------------------------------ presses + flashes ---

def presses():
    return [e for e in T.EVENTS if e['kind'] == 'press']


def landings():
    out = {}
    for h in T.HOPS:
        out.setdefault(h.get('on'), []).append(h['t1'])
    return out


_PRESSES, _LANDINGS = None, None


def press_dip(name, fr, depth=0.045):
    """How far a slab is pushed down at a frame: a press drives it in over 3
    frames and springs it back; a plain landing gives a small give."""
    global _PRESSES, _LANDINGS
    if _PRESSES is None:
        _PRESSES, _LANDINGS = presses(), landings()
    d = 0.0
    for e in _PRESSES:
        if e.get('target') == name:
            t = fr - e['f']
            if 0 <= t < 3:
                d = max(d, depth * (t + 1) / 3)
            elif 3 <= t < 12:
                d = max(d, depth * (1 - spring(t - 3, 8, 12)))
    for t1 in _LANDINGS.get(name, []):
        t = fr - t1
        if 0 <= t < 10:
            d = max(d, 0.02 * math.sin(math.pi * t / 10))
    return d


def flash(name, fr, peak=2.2, frames=8):
    """Emission multiplier: a press lights the slab up and fades over `frames`."""
    k = 1.0
    for e in _PRESSES or presses():
        if e.get('target') == name and 0 <= fr - e['f'] < frames:
            k = max(k, 1 + peak * (1 - (fr - e['f']) / frames))
    return k


def animate_slabs(motion=None):
    """Key every slab every frame: press dips and flashes, plus the film's own
    motion. motion(slab, fr, loc, scale, strength) -> (loc, scale, strength)
    lets a scene grow, raise or power down a panel on its events."""
    for s in SLABS.values():
        home = s.root.location.copy()
        for fr in FRAMES:
            loc = home.copy()
            loc.z -= press_dip(s.name, fr)
            scl, strength = 1.0, s.strength * flash(s.name, fr)
            if motion:
                loc, scl, strength = motion(s, fr, loc, scl, strength)
            s.root.location = loc
            s.root.scale = (scl,) * 3 if not isinstance(scl, (tuple, list)) else scl
            key(s.root, fr, rot=False)
            key_value(s.em, strength, fr)
        linear(s.root, s.mat)


# ------------------------------------------------------------- the glass ---

def glass_material():
    """Thin glass: a fresnel gloss over a clear pass. No refraction, so the
    footage under it stays sharp and the frames stay cheap."""
    mat = bpy.data.materials.get('screen-glass')
    if mat:
        return mat
    mat, n, l = new_mat('screen-glass')
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
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED'
    return mat


def glass_sheet(hole_at=None, hole=(2.6, 2.0), grid=(9, 7), seed=404):
    """The glass over the base slab. With hole_at (UI px) the panes leave a
    hole there filled with triangle shards, ready for shatter(). Returns the
    shards (empty without a hole)."""
    mat = glass_material()
    r = random.Random(seed)

    def pane(name, x0, y0, x1, y1):
        o = plane(name, x1 - x0, y1 - y0, ((x0 + x1) / 2, (y0 + y1) / 2, GZ), mat)
        o.visible_shadow = False
        return o

    if hole_at is None:
        pane('glass', -SW / 2, -SH / 2, SW / 2, SH / 2)
        return []
    sx, sy = T.px(*hole_at)
    hx0, hx1 = sx - hole[0] / 2, sx + hole[0] / 2
    hy0, hy1 = sy - hole[1] * 0.18, sy + hole[1] * 0.82    # more of the hole behind the hero
    pane('glass-l', -SW / 2, -SH / 2, hx0, SH / 2)
    pane('glass-r', hx1, -SH / 2, SW / 2, SH / 2)
    pane('glass-b', hx0, -SH / 2, hx1, hy0)
    pane('glass-t', hx0, hy1, hx1, SH / 2)
    nx, ny = grid
    jit = lambda i, n, span: r.uniform(-0.4, 0.4) * span / n if 0 < i < n else 0  # noqa: E731
    pts = [[Vector((hx0 + (hx1 - hx0) * i / nx + jit(i, nx, hx1 - hx0),
                    hy0 + (hy1 - hy0) * j / ny + jit(j, ny, hy1 - hy0), 0))
            for j in range(ny + 1)] for i in range(nx + 1)]
    shards = []
    for i in range(nx):
        for j in range(ny):
            a, b, c, d = pts[i][j], pts[i + 1][j], pts[i + 1][j + 1], pts[i][j + 1]
            for tri in ((a, b, c), (a, c, d)) if r.random() < 0.5 else ((a, b, d), (b, c, d)):
                if (tri[1] - tri[0]).cross(tri[2] - tri[0]).z < 0:     # every shard faces up
                    tri = (tri[0], tri[2], tri[1])
                cen = sum(tri, Vector()) / 3
                me = bpy.data.meshes.new('shard')
                me.from_pydata([v - cen for v in tri], [], [(0, 1, 2)])
                o = link(bpy.data.objects.new('shard', me))
                o.location = (cen.x, cen.y, GZ)
                me.materials.append(mat)
                o.visible_shadow = False
                shards.append(o)
    return shards


def shatter(shards, at, f0, seed=405, life=0.8):
    """Burst the shards out from a UI px at frame f0: outward and up, spinning,
    falling under gravity, shrinking away after `life` seconds. Each shard is
    keyed only while it moves; constant before and after."""
    r = random.Random(seed)
    c = m(*at, GZ)
    for o in shards:
        home = o.location.copy()
        away = home - c
        away.z = 0
        dist = away.length
        dirn = away.normalized() if dist > 1e-3 else Vector((1, 0, 0))
        delay = dist * 3                       # frames: the crack runs outward
        v = dirn * r.uniform(2.5, 5.5) + Vector((0, 0, r.uniform(3.0, 6.0)))
        spin = Vector((r.uniform(-12, 12), r.uniform(-12, 12), r.uniform(-6, 6)))
        start = int(f0 + delay)
        end = int(start + (life + 0.3) * T.FPS) + 1
        for fr in [1] + list(range(max(1, start), min(T.FRAMES, end) + 1)):
            t = (fr - f0 - delay) / T.FPS
            if t <= 0:
                o.location, o.rotation_euler, o.scale = home, (0, 0, 0), (1, 1, 1)
            else:
                o.location = home + v * t + Vector((0, 0, -4.9 * t * t))
                o.rotation_euler = Euler(tuple(s * t for s in spin))
                o.scale = (1,) * 3 if t < life * 0.7 else (max(0.0, 1 - (t - life * 0.7) / (life * 0.3)),) * 3
            key(o, fr)
        linear(o)


# ------------------------------------------------------------------ hero ---

class Hero:
    """Two empties drive any hero: `root` at the feet (position, yaw, squash)
    and `flip` at the centre of mass (flips, leans). The model hangs under
    `flip`. height (m) places the camera's eye line and the head anchor."""

    def __init__(self, height):
        self.height = height
        self.root = empty('hero-root')
        self.flip = empty('hero-flip', self.root, (0, 0, height * 0.5))
        self.arm, self.clips, self.parts = None, {}, []

    # -- clips on the NLA (glb heroes) --
    def clip(self, track, name, start, end=None, scale=1.0, blend=2, fill=True):
        """Lay clip `name` on NLA track `track` from frame `start`; it repeats
        to `end` (default: the film's end). Higher tracks play over lower."""
        if not self.arm or name not in self.clips:
            print(f'## hero: no clip {name!r}; have {sorted(self.clips)}')
            return None
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = None
        tr = next((t for t in ad.nla_tracks if t.name == track), None) or ad.nla_tracks.new()
        tr.name = track
        act = self.clips[name]
        s = tr.strips.new(f'{track}-{name}-{int(start)}', int(start), act)
        s.scale = scale
        end = end or T.FRAMES + 1
        length = max(1.0, (act.frame_range[1] - act.frame_range[0]) * scale)
        if fill:
            s.repeat = max(1.0, (end - start) / length)
        s.frame_end = min(s.frame_end, end) if fill else s.frame_end
        s.blend_in = s.blend_out = blend
        return s

    def air(self, name, min_apex=0.9, min_frames=12):
        """A run/air clip in the air on the long or high hops."""
        for h in T.HOPS:
            if h['apex'] >= min_apex or h['t1'] - h['t0'] >= min_frames:
                try:
                    self.clip('air', name, h['t0'], h['t1'] + 1, blend=2)
                except RuntimeError:      # strips on one track cannot overlap
                    pass


def hero_glb(file, height=None, hide=()):
    """Import a rigged .glb; its animations become clips for Hero.clip().
    height scales it (m); `hide` drops helper meshes by name prefix."""
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path(file))
    objs = [o for o in bpy.data.objects if o not in before]
    arm = next((o for o in objs if o.type == 'ARMATURE'), None)
    # The glTF importer adds a bone display shape ('Icosphere'): not the hero.
    shapes = {pb.custom_shape for pb in arm.pose.bones if pb.custom_shape} if arm else set()
    for o in objs:
        if o in shapes or (o.type == 'MESH' and any(o.name.startswith(p) for p in hide)):
            o.hide_render = o.hide_viewport = True
    meshes = [o for o in objs if o.type == 'MESH' and not o.hide_render and o not in shapes]
    if arm and arm.animation_data:
        arm.animation_data.action = None        # clips play from the NLA only
        for t in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(t)
    # Measure the deformed mesh in its rest pose: a skinned mesh's own
    # bounding box is in bind space and can sit metres off.
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    pts = [o.evaluated_get(dg).matrix_world @ Vector(c) for o in meshes for c in o.evaluated_get(dg).bound_box]
    pts = pts or [Vector((0, 0, 0)), Vector((0, 0, 1.8))]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    h0 = hi.z - lo.z
    k = (height / h0) if height and h0 > 1e-4 else 1.0
    hero = Hero(h0 * k)
    hero.parts, hero.arm = objs, arm
    pivot = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    rig = empty('hero-model', hero.flip, (0, 0, -hero.height * 0.5))
    rig.scale = (k, k, k)
    for o in [o for o in objs if o.parent is None]:
        o.parent = rig
        o.location = o.location - pivot        # feet at the root, centred
    hero.clips = {a.name: a for a in bpy.data.actions if a not in acts_before}
    print(f'## hero glb {os.path.basename(file)}: {hero.height:.2f} m, clips {sorted(hero.clips)}')
    return hero


def toy_hero(color=None, height=1.1, blink_every=2.6):
    """The fallback hero: a rounded toy (a bevelled box with two eyes) so the
    kit runs with no assets. Blinks every `blink_every` seconds."""
    color = color or hex_rgb(getattr(T, 'COLORS', {}).get('accent', '#e8743b'))
    hero = Hero(height)
    w, d = height * 0.82, height * 0.66
    mat, n, _ = new_mat('toy-body')
    p = principled(n)
    p.inputs['Base Color'].default_value = color
    p.inputs['Roughness'].default_value = 0.42
    set_in(p, 'Subsurface Weight', 0.15)
    set_in(p, 'Coat Weight', 0.4)
    set_in(p, 'Coat Roughness', 0.2)
    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.object
    body.name = 'toy-body'
    body.scale = (w, d, height)
    bpy.ops.object.transform_apply(scale=True)
    bv = body.modifiers.new('round', 'BEVEL')
    bv.width, bv.segments, bv.limit_method = height * 0.24, 6, 'NONE'
    body.data.materials.append(mat)
    for poly in body.data.polygons:
        poly.use_smooth = True
    body.parent = hero.flip
    body.location = (0, 0, 0)          # flip sits at half height: the box's centre
    white = emit_material('toy-eye', (0.95, 0.95, 0.93, 1), 0.9)
    ink, _, _ = new_mat('toy-pupil')
    principled(ink.node_tree.nodes).inputs['Base Color'].default_value = (0.01, 0.01, 0.012, 1)
    principled(ink.node_tree.nodes).inputs['Roughness'].default_value = 0.15
    hero.eyes = []
    for sx in (-1, 1):
        eye = empty(f'toy-eye-{sx:+d}', hero.flip, (sx * w * 0.2, -d / 2 - 0.005, height * 0.12))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=height * 0.1, segments=24, ring_count=12)
        ball = bpy.context.object
        ball.name = f'toy-eyeball-{sx:+d}'
        ball.scale = (1, 0.45, 1.25)
        ball.data.materials.append(white)
        ball.parent = eye
        bpy.ops.mesh.primitive_uv_sphere_add(radius=height * 0.05, segments=16, ring_count=8)
        pup = bpy.context.object
        pup.name = f'toy-pupil-{sx:+d}'
        pup.scale = (1, 0.4, 1.2)
        pup.location = (0, -height * 0.035, 0)
        pup.data.materials.append(ink)
        pup.parent = eye
        for o in (ball, pup):
            o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
        hero.eyes.append(eye)
    # Blink: the eyes squash shut for 4 frames.
    every = max(8, int(blink_every * T.FPS))
    for eye in hero.eyes:
        for fr in FRAMES:
            t = (fr - 20) % every
            eye.scale = (1, 1, 0.12 if t in (1, 2) else 0.5 if t in (0, 3) else 1)
            eye.keyframe_insert('scale', frame=fr)
        linear(eye)
    hero.parts = [body] + hero.eyes
    return hero


# ------------------------------------------------------------------ hops ---

class Hops:
    """The hero's path from T.HOPS: ballistic arcs between landings, take-off
    stretch, landing squash, front flips, a turn back to camera on the ground.

    start      UI px the hero stands on at frame 1 (T.START)
    start_on   the slab under the start ('world' = on the glass)
    landing    optional landing(i, fr) -> Vector, for hops onto moving things
    """

    def __init__(self, hero, start=None, start_on='world', landing=None, flip_dir=1):
        self.hero, self.flip_dir = hero, flip_dir
        self.start = start or getattr(T, 'START', (T.W / 2, T.H / 2))
        self.start_on = start_on
        self.custom = landing

    def top(self, on, z=None):
        if on in SLABS:
            return SLABS[on].top
        if on in (None, 'world', 'glass'):
            return GZ + 0.004
        return layer_top(z) if z else GZ + 0.004

    def landing(self, i, fr):
        if self.custom:
            p = self.custom(i, fr)
            if p is not None:
                return p
        h = T.HOPS[i]
        return m(*h['to'], self.top(h.get('on'), h.get('z')))

    def ride(self, on, fr):
        """Standing on a slab, the hero rides its press dip."""
        return press_dip(on, fr) if on in SLABS else 0.0

    def state(self, fr):
        """Feet position, yaw (deg), squash (z scale), flip angle, lean, air."""
        p_end = m(*self.start, self.top(self.start_on))
        on, pos, yaw, prev_land = self.start_on, p_end.copy(), 0.0, None
        for i, h in enumerate(T.HOPS):
            t0, t1 = h['t0'], h['t1']
            p0, p1 = p_end, self.landing(i, t1)
            d = p1 - p0
            heading = math.degrees(math.atan2(d.y, d.x)) + 90 if d.xy.length > 0.05 else yaw
            if fr < t0:
                break
            if fr <= t1:
                k = (fr - t0) / max(1, t1 - t0)
                top = max(p0.z, p1.z) + h.get('apex', 0.8)
                # A parabola through p0 and p1 peaking `apex` above the higher end.
                pos = p0.lerp(p1, k)
                pos.z = p0.z + (p1.z - p0.z) * k + 4 * (top - (p0.z + p1.z) / 2) * k * (1 - k)
                flip = 360 * self.flip_dir * h.get('spin', 0) * smooth((k - 0.1) / 0.8)
                # Stretch on the way up, round at the apex.
                squash = 1 + 0.14 * max(0, 1 - 2 * k) - 0.04 * max(0, 2 * k - 1)
                return dict(pos=pos, yaw=heading, squash=squash, flip=flip, lean=12 * math.sin(math.pi * k), air=True, on=None)
            p_end, pos, yaw, on, prev_land = p1, p1.copy(), heading, h.get('on'), t1
        pos = pos.copy()
        pos.z -= self.ride(on, fr)
        squash = 1.0
        if prev_land is not None:
            t = fr - prev_land
            squash = 0.78 + 0.05 * t if t < 2 else 1 - 0.12 * (1 - spring(t - 2, 8, 12))
            if t > 4:      # turn back to the camera, the short way round
                yaw = ((yaw + 180) % 360) - 180
                yaw *= 1 - smooth((t - 4) / 10)
        nxt = next((h for h in T.HOPS if h['t0'] > fr), None)
        if nxt and 0 <= nxt['t0'] - fr <= 3:      # crouch before take-off
            squash = min(squash, 1 - 0.16 * (1 - (nxt['t0'] - fr) / 3))
        return dict(pos=pos, yaw=yaw, squash=squash, flip=0.0, lean=0.0, air=False, on=on)

    def eye(self, fr):
        return self.state(fr)['pos'] + Vector((0, 0, self.hero.height * 0.55))


def key_hero(hero, state):
    """Key the hero's two empties every frame from state(fr) (Hops.state, or a
    scene's wrapper around it that adds its own beats)."""
    for fr in FRAMES:
        st = state(fr)
        hero.root.location = st['pos']
        hero.root.rotation_euler = Euler((math.radians(st.get('tilt', 0.0)), 0, math.radians(st['yaw'])))
        sq = st['squash']
        xy = 1 / math.sqrt(max(sq, 0.2))
        g = st.get('grow', 1.0)
        hero.root.scale = (xy * g, xy * g, sq * g)
        key(hero.root, fr)
        hero.flip.rotation_euler = Euler((math.radians(st['flip'] + st['lean']), 0, 0))
        key(hero.flip, fr, loc=False, scale=False)
    linear(hero.root, hero.flip)


# ---------------------------------------------------------------- camera ---

def follow(fn, rate=0.22):
    """fn(fr) -> Vector, smoothed so the camera follows rather than tracks.
    The film is known ahead, so the smoothing runs forward then backward: as
    soft as a lagging follow, but centred on the hero (a one-way follow
    leaves him at the frame edge on every landing). Lower rate = softer."""
    raw = {fr: fn(fr) for fr in FRAMES}
    fwd, acc = {}, raw[1]
    for fr in FRAMES:
        acc = acc.lerp(raw[fr], rate)
        fwd[fr] = acc.copy()
    out, acc = {}, fwd[T.FRAMES]
    for fr in reversed(FRAMES):
        acc = acc.lerp(fwd[fr], rate)
        out[fr] = acc.copy()
    return out


def build_camera(name, keys, follow, targets=None, shake=None):
    """A camera keyed every frame from timeline camera keys: look (UI px, or
    'hero' = the smoothed `follow` path, or a name in `targets`), dist (m),
    elev and yaw (deg), lens (mm), fstop; optional 'z' lifts a UI-px look.
    Focus sits on the look target. shake: {event kind: amplitude m}."""
    sc = scene()
    shake = shake if shake is not None else getattr(T, 'SHAKE', {'pop': 0.06})
    targets = dict(targets or {}, hero=follow)
    cd = bpy.data.cameras.new(name)
    cam = link(bpy.data.objects.new(name, cd))
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.clip_start, cd.clip_end = 0.05, 400
    keys = sorted(keys, key=lambda c: c['f'])

    def look(c, fr):
        if isinstance(c['look'], str):
            return targets[c['look']][fr]
        return m(*c['look'], c.get('z', 0.0))

    for fr in FRAMES:
        i = max((j for j, c in enumerate(keys) if c['f'] <= fr), default=0)
        a, b = keys[i], keys[min(i + 1, len(keys) - 1)]
        k = 0 if a is b else smooth((fr - a['f']) / (b['f'] - a['f']))
        target = look(a, fr).lerp(look(b, fr), k)
        dist, elev, yaw = lerp(a['dist'], b['dist'], k), lerp(a['elev'], b['elev'], k), lerp(a['yaw'], b['yaw'], k)
        e, y = math.radians(elev), math.radians(yaw)
        off = Vector((math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e))) * dist
        jolt = Vector()
        for ev in T.EVENTS:
            amp = shake.get(ev['kind'])
            if amp and 0 <= fr - ev['f'] < 8:      # gone in a few frames
                jolt += Vector((math.sin(fr * 7.1), math.cos(fr * 5.3), math.sin(fr * 6.2))) * amp * (1 - (fr - ev['f']) / 8)
        cam.location = target + off + jolt
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cd.lens = lerp(a['lens'], b['lens'], k)
        cd.dof.aperture_fstop = lerp(a.get('fstop', 4.0), b.get('fstop', 4.0), k)
        cd.dof.focus_distance = (target - cam.location).length
        key(cam, fr, scale=False)
        cd.keyframe_insert('lens', frame=fr)
        cd.dof.keyframe_insert('aperture_fstop', frame=fr)
        cd.dof.keyframe_insert('focus_distance', frame=fr)
    linear(cam, cd)
    if name == 'cam':
        sc.camera = cam
    return cam


def cameras(hops, rate_16x9=0.22, rate_9x16=0.4, **kw):
    """Both cameras from T.CAMERA and T.CAMERA_9X16. The tall frame follows
    tighter: it loses the hero on a flip otherwise."""
    cam = build_camera('cam', T.CAMERA, follow(hops.eye, rate_16x9), **kw)
    tall = getattr(T, 'CAMERA_9X16', None)
    if tall:
        build_camera('cam-9x16', tall, follow(hops.eye, rate_9x16), **kw)
    scene().camera = cam
    return cam


# --------------------------------------------------------------- anchors ---

def anchors(objs=None):
    """One empty 'anchor-<id>' per T.ANCHORS entry, for anchors.py to project.
    {slab, at}: on the slab at UI px `at` (None = its centre), riding it.
    {obj}: over an object's head; objs maps names to (object, height m),
    else the object's bounding-box top. {screen}: 2D only, skipped."""
    objs = objs or {}
    out = {}
    for aid, a in getattr(T, 'ANCHORS', {}).items():
        if 'screen' in a:
            continue
        e = empty(f'anchor-{aid}')
        if 'slab' in a:
            sl = SLABS[a['slab']]
            e.parent = sl.root
            e.location = sl.at(*(a.get('at') or (None, None))) + Vector((0, 0, 0.01))
        elif 'obj' in a:
            if a['obj'] in objs:
                ob, hgt = objs[a['obj']]
            else:
                ob = bpy.data.objects[a['obj']]
                hgt = max(Vector(c).z for c in ob.bound_box) * ob.scale.z
            e.parent, e.location = ob, (0, 0, hgt + 0.15)
        out[aid] = e
    return out


# ------------------------------------------------------------ compositor ---

def compositor(threshold=1.0, bloom=0.3, size=0.55, vignette=0.32):
    """Bloom on the brightest pixels only (a press flash, the hot UI), then a
    soft round vignette (`vignette` = how dark the corners go)."""
    sc = scene()
    if hasattr(sc, 'compositing_node_group'):           # Blender 5
        tree = bpy.data.node_groups.new('comp', 'CompositorNodeTree')
        sc.compositing_node_group = tree
        out = tree.nodes.new('NodeGroupOutput')
        tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        sink = out.inputs[0]
    else:                                               # 4.x
        sc.use_nodes = True
        tree = sc.node_tree
        tree.nodes.clear()
        sink = tree.nodes.new('CompositorNodeComposite').inputs['Image']
    sc.render.use_compositing = True
    nodes, links = tree.nodes, tree.links
    rl = nodes.new('CompositorNodeRLayers')
    gl = nodes.new('CompositorNodeGlare')
    for name, val in (('Type', 'Bloom'), ('Quality', 'High'), ('Threshold', threshold),
                      ('Strength', bloom), ('Size', size), ('Smoothness', 0.4)):
        if name in gl.inputs:
            try:
                gl.inputs[name].default_value = val
            except (TypeError, ValueError):
                pass
    if hasattr(gl, 'glare_type'):
        gl.glare_type = 'BLOOM'
        gl.threshold = threshold
    links.new(rl.outputs['Image'], gl.inputs['Image'])
    img = gl.outputs['Image']
    try:
        # Distance from the centre in aspect-correct units -> a smooth falloff.
        ic = nodes.new('CompositorNodeImageCoordinates')
        links.new(img, ic.inputs['Image'])
        ln = nodes.new('ShaderNodeVectorMath')
        ln.operation = 'LENGTH'
        links.new(ic.outputs['Uniform'], ln.inputs[0])
        mr = nodes.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value = 0.45
        mr.inputs['From Max'].default_value = 1.25
        mr.inputs['To Min'].default_value = 1.0
        mr.inputs['To Max'].default_value = 1.0 - vignette
        links.new(ln.outputs['Value'], mr.inputs['Value'])
        mx = nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.inputs['Factor'].default_value = 1.0
        links.new(img, mx.inputs['A'])
        links.new(mr.outputs['Result'], mx.inputs['B'])
        img = mx.outputs['Result']
    except (RuntimeError, KeyError) as err:
        print('## compositor: no vignette on this Blender:', err)
    links.new(img, sink)
    return tree


# ------------------------------------------------------------------ save ---

def save(file=None):
    file = file or os.path.join(ROOT, 'cache', 'scene.blend')
    os.makedirs(os.path.dirname(file), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=file)
    print('## saved', file, 'slabs', len(SLABS))
    return file
