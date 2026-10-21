"""Render stills from cache/scene.blend at a reduced size, for review gates.

blender -b cache/scene.blend -P src/stills.py -- 1,90,200 [percent] [samples] [9x16]
Writes cache/stills/NNNN.png.
"""
import os
import sys

import time

import bpy

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
frames = [int(x) for x in args[0].split(',')] if args else [1]
pct = int(args[1]) if len(args) > 1 else 50
samples = int(args[2]) if len(args) > 2 else 32
tall = len(args) > 3 and args[3] == '9x16'
scene = bpy.context.scene
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = 'GPU'
scene.render.resolution_percentage = pct
if tall:
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.camera = bpy.data.objects['cam-9x16']
    for img in bpy.data.images:
        if bpy.path.abspath(img.filepath).endswith('cache/screen/0001.jpg'):
            img.filepath = img.filepath.replace('screen', 'screen-9x16')
scene.cycles.samples = samples
T0 = time.time()
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for fr in frames:
    scene.frame_set(fr)
    scene.render.filepath = os.path.join(root, 'cache', 'stills', f'{fr:04d}' + ('-9x16' if tall else '') + '.png')
    bpy.ops.render.render(write_still=True)
    print('## still', fr, round(time.time() - T0, 1))
