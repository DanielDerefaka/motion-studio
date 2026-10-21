"""Where every callout anchor lands on screen, every frame, for each camera.

blender -b cache/scene.blend -P src/anchors.py
Writes cache/anchors-16x9.json and cache/anchors-9x16.json for overlay.mjs:
{"fmt", "w", "h", "frames", "anchors": {id: [[x, y, visible], ...]}}, one
entry per frame, x and y in output pixels from the top left.
"""
import json
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402

FORMATS = {'16x9': ('cam', 1920, 1080), '9x16': ('cam-9x16', 1080, 1920)}
scene = bpy.context.scene
empties = {aid: bpy.data.objects[f'anchor-{aid}'] for aid in T.ANCHORS}

for fmt, (cam_name, w, h) in FORMATS.items():
    scene.camera = bpy.data.objects[cam_name]
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    track = {aid: [] for aid in empties}
    for fr in range(1, T.FRAMES + 1):
        scene.frame_set(fr)
        for aid, e in empties.items():
            x, y, z = world_to_camera_view(scene, scene.camera, e.matrix_world.translation)
            # In front of the lens and inside the frame, with a small margin.
            vis = z > 0 and 0.02 <= x <= 0.98 and 0.02 <= y <= 0.98
            track[aid].append([round(x * w, 1), round((1 - y) * h, 1), int(vis)])
    out = os.path.join(T.STUDIO, 'cache', f'anchors-{fmt}.json')
    json.dump(dict(fmt=fmt, w=w, h=h, frames=T.FRAMES, anchors=track), open(out, 'w'))
    print('## anchors', fmt, out)
