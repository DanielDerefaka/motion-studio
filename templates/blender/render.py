"""Render the film's frames.

blender -b cache/scene.blend -P src/render.py -- [16x9|9x16] [first] [last] [cycles]
blender -b cache/scene.blend -P src/render.py -- 16x9 60,150,330 [cycles]   # review stills
blender -b cache/scene.blend -P src/render.py -- 16x9 40 60 50%             # a quick motion check

Writes out/frames-<fmt>/NNNN.png, or, for a comma list of frames,
reviews/stills/<fmt>/NNNN.png. Frames that already exist are skipped, so a
stopped render picks up where it left off (delete a frame to redo it).
An argument like 50% renders at that size, into out/frames-<fmt>-50/.
EEVEE by default (32 TAA samples, ray tracing, motion blur: a few seconds a
frame). `cycles` path traces the same scene at 96 samples with denoising, on
the first GPU backend found (Metal, OptiX, CUDA, HIP, oneAPI) or the CPU.
The first frame after a scene change spends minutes compiling shaders.
"""
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(__file__))
import scene_kit as K  # noqa: E402
import timeline as T  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
cycles = 'cycles' in args
pct = next((int(a[:-1]) for a in args if a.endswith('%')), 100)
args = [a for a in args if a != 'cycles' and not a.endswith('%')]
fmt = args[0] if args else '16x9'
if fmt not in T.FORMATS:
    sys.exit(f'unknown format {fmt!r}; have {sorted(T.FORMATS)}')
scene = bpy.context.scene
only = [int(x) for x in args[1].split(',') if x] if len(args) > 1 and ',' in args[1] else None
first = int(args[1]) if len(args) > 1 and not only else scene.frame_start
last = int(args[2]) if len(args) > 2 and not only else scene.frame_end

if cycles:
    print('## cycles on', K.use_cycles(scene, 96), flush=True)
else:
    K.use_eevee(scene, 32)
    print('## eevee', flush=True)
K.use_format(scene, fmt)
scene.render.resolution_percentage = pct

out = (os.path.join(T.STUDIO, 'reviews', 'stills', fmt) if only
       else os.path.join(T.STUDIO, 'out', f'frames-{fmt}' + (f'-{pct}' if pct != 100 else '')))
os.makedirs(out, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 15
T0 = time.time()
for fr in only or range(first, last + 1):
    file = os.path.join(out, f'{fr:04d}.png')
    if os.path.exists(file):
        continue
    t = time.time()
    scene.frame_set(fr)
    scene.render.filepath = file
    bpy.ops.render.render(write_still=True)
    print('## frame', fr, f'{time.time() - t:.1f}s', flush=True)
print('## done', out, f'{time.time() - T0:.0f}s', flush=True)
