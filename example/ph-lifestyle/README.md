# Motion studio: "Just Hide the HUD"

A 16.8 s PH Lifestyle promo in 16:9 and 9:16: HTML for the UI, Blender for
the world, one timeline that drives everything. See `brief.md`, `style-guide.md` and
`shotlist.md`.

## Rebuild, in order

All commands run from this folder.

```sh
python3 src/timeline.py                              # timeline.json: 504 frames, events, hops, cuts
node src/record.mjs                                  # world footage from www.phlifestyle.fun (studio guest, HUD hidden)
node src/snapshot-ui.mjs                             # live HUD + phone DOM -> assets/ui/*.html, rects.json
node src/capture-ui.mjs                              # slab textures + the per-frame needs panel
cache/venv/bin/python src/world.py                   # cache/world/: the footage cut on the beats
node src/endcard.mjs                                 # cache/screen/: world + end card (16:9)
node src/endcard.mjs --format=9x16                   # cache/screen-9x16/
blender -b --factory-startup -P src/scene.py         # cache/scene.blend
cache/venv/bin/python src/sound.py                   # out/sound.wav
```

Review stills before a full render (frames, percent, samples, optional 9x16):

```sh
blender -b cache/scene.blend -P src/stills.py -- 30,113,190 50 24 9x16
```

Full render. It resumes: frames already in `out/frames*` are skipped.

```sh
blender -b cache/scene.blend -P src/render.py -- 16x9    # out/frames/
blender -b cache/scene.blend -P src/render.py -- 9x16    # out/frames-9x16/
sh src/encode.sh 16x9                                    # out/ph-lifestyle-16x9.mp4 + poster-16x9.jpg
sh src/encode.sh 9x16
```

The film renders in EEVEE: about 3 s a frame, so about 25 min per format.
Add `cycles` (`render.py -- 16x9 1 504 cycles`) to path trace at 96 samples
instead, at 40–60 s a frame on a loaded machine. The review stills are Cycles.
The first render after a scene change spends 2–5 min compiling shaders.

## Still needs a human eye

- The look and the sound: not yet approved.
- The white blocks on Tobi's chest are in the game's own Tobi texture; kept as is.
- Jevinik (beat 5) was recorded empty: no players in the restaurant.
- The opening sticker sits on the market footage and can read as part of it.
- Heavy whip blur on the flip and the cut frames, by design.
