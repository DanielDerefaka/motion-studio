"""Review stills from cache/scene.blend at a reduced size, for the gates.

blender -b cache/scene.blend -P src/stills.py -- 1,90,200 [percent] [samples] [16x9|9x16] [cycles]

Writes reviews/stills/<fmt>/NNNN.png (overwriting: stills are for looking at
the latest scene). percent of the format's size (default 50); samples are
EEVEE's TAA samples (default 16) or, with `cycles`, Cycles samples.
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
args = [a for a in args if a != 'cycles']
frames = [int(x) for x in args[0].split(',') if x] if args else [1]
pct = int(args[1]) if len(args) > 1 else 50
samples = int(args[2]) if len(args) > 2 else (16 if not cycles else 24)
fmt = args[3] if len(args) > 3 else '16x9'
scene = bpy.context.scene
if cycles:
    print('## cycles on', K.use_cycles(scene, samples), flush=True)
else:
    K.use_eevee(scene, samples)
K.use_format(scene, fmt)
scene.render.resolution_percentage = pct
out = os.path.join(T.STUDIO, 'reviews', 'stills', fmt)
os.makedirs(out, exist_ok=True)
T0 = time.time()
for fr in frames:
    t = time.time()
    scene.frame_set(fr)
    scene.render.filepath = os.path.join(out, f'{fr:04d}.png')
    bpy.ops.render.render(write_still=True)
    print('## still', fmt, fr, f'{time.time() - t:.1f}s', flush=True)
print('## stills', out, f'{time.time() - T0:.0f}s total', flush=True)
