"""Render the film's frames on the Metal GPU.

blender -b cache/scene.blend -P src/render.py -- [16x9|9x16] [first] [last] [cycles]
Writes out/frames/NNNN.png (16:9) or out/frames-9x16/NNNN.png. Frames that
already exist are skipped, so a stopped render picks up where it left off.
EEVEE by default (a few seconds a frame); `cycles` path traces the same scene
at 96 samples (40-60 s a frame on a loaded machine).
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
fmt = args[0] if args else '16x9'
scene = bpy.context.scene
first = int(args[1]) if len(args) > 1 else scene.frame_start
last = int(args[2]) if len(args) > 2 else scene.frame_end
cycles = 'cycles' in args
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = 'GPU'
if not cycles:
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.eevee.use_raytracing = True
    scene.render.use_motion_blur = True
    # Cycles hides the lights from glossy rays; in EEVEE that is no specular.
    for o in scene.objects:
        if o.type == 'LIGHT':
            o.data.specular_factor = 0.0
scene.render.resolution_percentage = 100
if fmt == '9x16':
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.camera = bpy.data.objects['cam-9x16']
    # The world slab shows the tall end card.
    for img in bpy.data.images:
        if bpy.path.abspath(img.filepath).replace('\\', '/').endswith('cache/screen/0001.jpg'):
            img.filepath = img.filepath.replace('screen', 'screen-9x16')
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, 'out', 'frames' if fmt == '16x9' else 'frames-9x16')
os.makedirs(out, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 15
for fr in range(first, last + 1):
    path = os.path.join(out, f'{fr:04d}.png')
    if os.path.exists(path):
        continue
    scene.frame_set(fr)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('## frame', fr, flush=True)
