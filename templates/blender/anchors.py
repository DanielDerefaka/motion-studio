"""Where every callout anchor lands on screen, every frame, for each camera.

blender -b cache/scene.blend -P src/anchors.py

Projects each 'anchor-<id>' empty (made by scene_kit.anchors from
T.ANCHORS) through each format's camera. Writes cache/anchors-<fmt>.json for
the 2D overlay: {"fmt", "w", "h", "frames", "anchors": {id: [[x, y, visible],
...]}}, one entry per frame 1..FRAMES, x and y in output pixels from the top
left, visible = in front of the lens and within 0.02-0.98 of the frame.
"""
import json
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, os.path.dirname(__file__))
import scene_kit as K  # noqa: E402
import timeline as T  # noqa: E402

scene = bpy.context.scene
empties = {aid: bpy.data.objects[f'anchor-{aid}'] for aid in T.ANCHORS if f'anchor-{aid}' in bpy.data.objects}

for fmt, (w, h) in T.FORMATS.items():
    K.use_format(scene, fmt)
    scene.render.resolution_percentage = 100
    track = {aid: [] for aid in empties}
    for fr in range(1, T.FRAMES + 1):
        scene.frame_set(fr)
        for aid, e in empties.items():
            x, y, z = world_to_camera_view(scene, scene.camera, e.matrix_world.translation)
            vis = z > 0 and 0.02 <= x <= 0.98 and 0.02 <= y <= 0.98
            track[aid].append([round(x * w, 1), round((1 - y) * h, 1), int(vis)])
    out = os.path.join(T.STUDIO, 'cache', f'anchors-{fmt}.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(fmt=fmt, w=w, h=h, frames=T.FRAMES, anchors=track), open(out, 'w'))
    seen = {aid: sum(v[2] for v in t) for aid, t in track.items()}
    print('## anchors', fmt, out, 'visible frames', seen, flush=True)
