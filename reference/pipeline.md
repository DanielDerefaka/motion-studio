# Pipeline: branches, data flow, commands

Everything runs from the studio folder. One file, `src/timeline.py`, holds
every number (beats, frames, layout in UI pixels, hops, cuts, events, VO,
captions, cameras, music, fonts, colours) and writes `src/timeline.json`.
Every other step reads it: the picture, the overlay and the sound can't drift.

## Pick the branch

| Branch | When | Picture | Text |
|---|---|---|---|
| **A. 3D** | The inspo has real depth, light or a character: exploded UI, devices, a hero acting on the UI (a character pressing real buttons) | Blender: slabs + hero + cameras | Optional overlay |
| **B. 2D** | Most inspos: kinetic type, flat motion graphics, 2D walkthroughs, shader looks, collage, data, footage edits; also when there's no Blender | One HTML composition, `renderFrame(f)` (DOM, canvas, SVG, WebGL, three.js) | In the composition |
| **C. Hybrid** | Explainer: 3D world + captions, chapter chip, callouts pinned to 3D points (the PH Lifestyle explainer) | Blender | 2D overlay from anchors |

The inspo's class decides (inspo.md section 4). Choose the smallest one that
reaches the look. Say which and why in brief.md.

## Data flow

```
inspo/ ──analyse-inspo.py, look.py──▶ inspo/analysis/ ──▶ style-guide.md (look recipe) ──▶ STYLE in timeline.py
                                          product URL ──snapshot.mjs──▶ assets/ui/<page>.html, rects.json
brief.md, shotlist.md ──▶ src/timeline.py ──▶ src/timeline.json
                                                │
  assets/ui/*.html ──slabs.mjs──▶ assets/ui/tex/*.png + textures.json ─┐
  product URL ──record.mjs──▶ assets/footage/*.webm ──world.py──▶ cache/world/NNNN.jpg ─┤
                                                │                                        ▼
                          (A, C)  blender -P scene.py ──▶ cache/scene.blend ──render.py──▶ out/frames-<fmt>/
                                                         └──anchors.py──▶ cache/anchors-<fmt>.json
                          (C)     render2d.mjs overlay.html ──▶ cache/overlay-<fmt>/NNNN.png (transparent)
                          (B)     render2d.mjs film.html --opaque --out=out/frames-<fmt>
  voice.py ──▶ cache/vo/<voice>/*.wav + lines.json ──(rerun timeline.py)
  sound.py ──▶ out/sound.wav, music.wav, sound-notes.txt, reviews/sound.png
  encode.sh <fmt> ──▶ out/<NAME>-<fmt>.mp4 + out/poster-<fmt>.jpg
  contact-sheet.sh ──▶ reviews/*.jpg
```

## Files in a studio

| File | From | Job |
|---|---|---|
| src/timeline.py | templates/timeline.py | The contract. Edit per film. |
| src/capture.config.json | templates/capture | URL, viewport, pages and their panel selectors, clips |
| src/snapshot.mjs | templates/capture | Live DOM → static HTML + rects.json; `--headed` for a one-time login |
| src/slabs.mjs | templates/capture | Panels isolated at DPR 3 → tex/*.png + textures.json; perFrame() for changing panels |
| src/record.mjs | templates/capture | Footage clips via page.screencast + strips |
| src/world.py | templates/capture | Footage cut on T.CUTS → cache/world/ |
| src/scene_kit.py, scene.py | templates/blender | Studio, slabs, glass, lights, hero, hops, cameras, anchors |
| src/render.py, stills.py, anchors.py | templates/blender | Frames (GPU auto), review stills, anchor projection |
| src/render2d.mjs, motion.js, overlay.html, film2d.html | templates/2d | The seekable 2D renderer, helpers, overlay, demo 2D film |
| src/footage.js, footage-frames.sh | templates/2d | Real footage inside a 2D comp: clips as numbered JPGs, clipFrame / drawCover / smear / whip (a push between two shots) / grade / bloom |
| src/synth.py, sound.py, setup-venv.sh | templates/sound | Synth library, film mix on the beat grid, venv |
| src/voice.py, setup-tts.sh | templates/voice | Kokoro VO, voice samples, TTS venv + models |
| src/encode.sh, contact-sheet.sh | templates | mp4 + poster; review sheets |

## Commands, in order

```sh
sh src/setup-venv.sh                                   # cache/venv: numpy scipy soundfile pillow (optional arg: studio dir)
npm init -y >/dev/null && npm i puppeteer              # capture + 2D
python3 src/timeline.py                                # src/timeline.json

# Gate 1: the inspo, then the real assets
cache/venv/bin/python -I $SKILL/scripts/analyse-inspo.py inspo/          # inspo/analysis/<name>/
cache/venv/bin/python -I $SKILL/scripts/look.py step inspo/<file> 1.8 2.6 # frame-step a signature move
node src/snapshot.mjs [--headed]                       # assets/ui/*.html, rects.json, live-*.png
node src/slabs.mjs                                     # assets/ui/tex/*.png, textures.json
node src/record.mjs                                    # assets/footage/*.webm + strips
cache/venv/bin/python -I src/world.py                  # cache/world/NNNN.jpg

# Voice (explainers): sample, pick, generate, then re-time
sh src/setup-tts.sh
cache/tts-venv/bin/python -I src/voice.py --samples "The one line of the film."
cache/tts-venv/bin/python -I src/voice.py af_heart 1.1
python3 src/timeline.py

# A / C: the 3D scene
blender -b --factory-startup -P src/scene.py           # cache/scene.blend
blender -b cache/scene.blend -P src/stills.py -- 30,113,190 50 24 16x9   # Gate 3 stills
blender -b cache/scene.blend -P src/anchors.py         # cache/anchors-<fmt>.json (C)
blender -b cache/scene.blend -P src/render.py -- 16x9  # out/frames-16x9/, resumes

# B with footage (a footage-led edit): clips as frames, then draw them in the comp
sh src/footage-frames.sh [clip ...]                    # cache/clips/<clip>/NNNN.jpg + cache/clips/index.js

# C: overlay / B: the whole 2D film
node src/render2d.mjs src/overlay.html --test=60,200,400                 # check stills
node src/render2d.mjs src/overlay.html --format=16x9 --jobs=4            # cache/overlay-16x9/
node src/render2d.mjs src/film2d.html --opaque --out=out/frames-16x9 --jobs=4   # B

cache/venv/bin/python -I $SKILL/scripts/look.py compare inspo/<file> out/look-test.mp4 --pairs=4.1:1.2  # look gate
cache/venv/bin/python -I src/sound.py                  # out/sound.wav + notes + reviews/sound.png
sh src/encode.sh 16x9                                  # out/<NAME>-16x9.mp4 + poster
sh src/contact-sheet.sh out/<NAME>-16x9.mp4 reviews/sheet-16x9.jpg
```

Then the same for 9x16: its own camera (`CAMERA_9X16`), stills, render,
overlay, encode and sheet.

## Times (measured, Apple silicon)

| Step | Time |
|---|---|
| EEVEE frame, 1080p | ~3.4 s (900 frames ≈ 50 min) |
| Cycles frame, 96 samples | 40–60 s |
| First frame after a scene change | +2–5 min shader compile |
| 2D overlay frame (puppeteer) | well under 1 s with --jobs |
| Kokoro line | ~1 s |
| sound.py, 30 s film | under a minute |

## Re-rendering a defect

Delete the affected range only, rerun with the range:

```sh
for i in $(seq 105 145); do rm -f out/frames-16x9/$(printf %04d $i).png; done
blender -b cache/scene.blend -P src/render.py -- 16x9 105 145
sh src/encode.sh 16x9
```
