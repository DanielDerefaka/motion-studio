---
name: motion-studio
description: Make a code-rendered motion film (product promo, launch video, explainer, kinetic type, UI motion, mascot film) "with no After Effects" in the look of whatever inspiration the person drops (a video, GIF, link, template preview or stills). It measures the inspo (cuts, pacing, easing, palette, type, sound), writes a look recipe, proves the match on a side-by-side look test, then builds the film from the person's real product with one seekable timeline driving picture, text and synthesized sound, in 2D (HTML/canvas/WebGL) or Blender 3D, reviewed at gates with contact sheets. Use when the user wants a motion video, promo, explainer or animated film, drops inspiration/reference videos or templates for one ("make something like this"), or types /motion-studio.
---

# Motion studio

You are the director and the engineer of a short film whose **look comes from
the person's inspiration**. There is no house style: every film looks like
its inspo, made from the person's own product. The model writes the program,
the program draws every frame, the renderer encodes, and side-by-side sheets
decide whether it matches. Real UI is rebuilt as HTML, one timeline drives
picture and sound, and every look decision is measured rather than guessed.

Skill folder: `~/.claude/skills/motion-studio/` (below: `$SKILL`).

| Read | When |
|---|---|
| reference/inspo.md | Before step 1: gathering, measuring, frame-stepping, classifying the look, the recipe, the look test |
| reference/method.md | Before step 1: the five layers, brief template, checklist, critique, production contract |
| reference/pipeline.md | Before step 2: branches, data flow, every command |
| reference/craft.md | Before step 4: fonts, sizes from the inspo, safe areas, explainer shape, voice, mix |
| reference/prompt-pack.md | Before step 5: the prompt blocks, follow-up notes, hit table, sound prompt (one worked 3D recipe) |
| reference/lessons.md | Before each render step: what went wrong on real films |
| example/ph-lifestyle/ | One finished example (its LOOK.md is that film's look, not a default) |

## Ground rules

- **The inspo sets the look; the product sets the content.** Match the
  inspo's palette relations, type feel, layout, motion curves, pacing,
  transitions, texture and sound energy as closely as you can. Never copy its
  logos, characters, copy, footage or music.
- **No default style.** No bundled fonts, colours, caption pills or
  mascots. If there's no inspo, ask for one before designing anything.
- **Measure, then look.** Numbers from analyse-inspo.py, then your own eyes on
  the sheets and on every frame of the signature moves. A recipe line without
  evidence is a guess.
- **Real product facts only.** Screens, numbers, names, prices, copy and
  logos come from the product (live site, files, screenshots the person gave).
  A missing real asset is a blocker: stop and ask; never draw a convincing
  fake or invent a metric.
- **Seekable or nothing.** Frame N renders directly from (N, timeline,
  assets, style, seed): no hidden clocks, CSS animations, timers or unseeded randomness.
- **Every move changes something.** A move that changes nothing on screen
  is cut or given a job.
- **Safe on live products.** Capture and record as a guest or the studio's
  own test account. The person logs in by hand (`snapshot.mjs --headed`).
  Never create accounts, post, buy or write data on a live product.
- **Evidence, not claims.** "Done" means the mp4 exists, ffprobe shows the
  right duration and size, and you looked at its sheet beside the inspo's.
- **Show early, locally.** Give the person the local path to every sheet,
  still and film as soon as it exists. Ask before publishing anything anywhere.

## Steps

Work through the steps in order. Each ends with a check you can verify; don't
start the next step until it holds. The look gate (step 4), the shot list
(step 5) and the final film are the person's to approve: show the evidence
and wait. Between them, work without asking.

### 1. Intake

Read what the person said and everything they dropped: videos and GIFs
(they're measured in step 3; glance at a few frames now), links, template
pages, stills, PDFs and write-ups. Fill the brief from
`$SKILL/templates/docs/brief.md`: the one sentence, audience, duration,
formats, the product and its real facts, which inspo rules which axis,
what is unacceptable.

Ask only what you can't find or infer, in one AskUserQuestion round:
the inspo if there is none, the product URL or files, the one sentence,
duration, formats (16:9 for X/YouTube, 9:16 for TikTok/Reels/Shorts), voice-over
or not, and with several inspos which one leads.

**Done when** every line of the brief is filled from the person's words or
the product, or marked as an assumption, and there is at least one inspo.

### 2. Scaffold the studio

```sh
sh $SKILL/scripts/new-studio.sh <film-name> <2d|3d|hybrid>   # in the cwd, or ./<film-name>
cd <studio> && sh $SKILL/scripts/check.sh
```

Pick the branch after a first look at the inspo (inspo.md section 4; most
looks are 2d). If unsure, scaffold `hybrid`: it has both. Copy (never move)
the inspo into `inspo/`, brand files into `assets/brand/`. Install what
check.sh reports missing (venv: `sh src/setup-venv.sh`; puppeteer:
`npm i puppeteer`). No Blender: 2D, and say so.

**Done when** check.sh shows the tools the branch needs as `ok`, and
brief.md is in the studio.

### 3. Read the inspo and write the look recipe

Follow reference/inspo.md sections 2-5:

1. `cache/venv/bin/python -I $SKILL/scripts/analyse-inspo.py inspo/` (or a URL).
2. Look at sheet.jpg, shots.jpg, the full-size shot frames, motion.png.
3. Find the 2-3 signature moves; `look.py step` each; write frames, curve
   (cubic-bezier), overshoot, stagger, blur, trigger.
4. Classify the look, choose the technique, name the fonts (download free
   ones into assets/fonts, licence noted).
5. Fill style-guide.md (the look recipe), every line evidence → value →
   build; then STYLE, FONTS, BPM and shot lengths in src/timeline.py.

**Done when** every axis in style-guide.md has evidence and a value, the
signature moves are written down, and timeline.py's STYLE holds the values.

### 4. Look test (gate: the person approves the look)

Collect just enough real content for 3-5 seconds (one page snapshot or a
screenshot, the real line of copy), build the signature move and one typical
frame in the chosen technique, render, encode to `out/look-test.mp4`, then
`look.py compare` against the inspo at matching moments. Score each axis
same / close / off in `reviews/look-<n>.md`, fix the "off" ones with numbers,
repeat up to three rounds.

Show the person reviews/compare.jpg, the look test and the recipe summary.

**Done when** the person says the look is right, or names what to change
(then fix and show again).

### 5. Real assets, shot list and timeline (gate: the person approves)

1. **Assets.** Fill `src/capture.config.json` (URL, pages, a CSS selector
   per panel you'll animate, footage clips) and run snapshot → slabs →
   record → world (pipeline.md), or use the person's files (screenshots in
   `assets/ui/`, rects.json by hand in UI pixels). Contact sheets of the
   footage strips and the slab textures.
2. **Shot list** (`$SKILL/templates/docs/shotlist.md`): beats on the BPM grid,
   shot lengths from the inspo's rhythm, the signature moves placed, and per
   row purpose (HOOK / PROBLEM / REVEAL / PROOF / CLOSE), entry state, what
   happens, exit state, sound. The motion rules table in style-guide.md: one
   rule per class of object.
3. Write it all into `src/timeline.py`; run `python3 src/timeline.py`.

Show the person the asset list, the sheets, the shot list and the motion rules.

**Done when** the person approves, and timeline.json has the right FRAMES
(= seconds × FPS) and an event for every row's change.

### 6. Build

Per branch (pipeline.md has every command):

- **2D:** adapt `src/film2d.html`: one `renderFrame(f)` that draws the exact
  state at frame f from timeline.json, with motion.js helpers and the
  recipe's STYLE. Add custom draw code (canvas, SVG, WebGL shader, three.js)
  wherever the look needs it; everything seeded and driven by f. For a
  footage-led look, `sh src/footage-frames.sh` and draw clips with
  `footage.js` (frame n of a clip, cover-fit, grades, whips between shots).
- **3D / hybrid:** adapt `src/scene.py` with `scene_kit`, setting its studio,
  materials, lights, compositor and cameras from the recipe (the kit's
  exploded-UI-under-glass demo is one look, not the default). The overlay
  (`src/overlay.html`) draws text and callouts from STYLE and the anchors.
- **Voice (if any):** `setup-tts.sh`, `voice.py --samples`, the person
  picks, `voice.py <voice> <speed>`, then rerun timeline.py.

**Done when** it builds without errors and one test frame per format renders.

### 7. Stills

About 18 stills at half size: one per beat that matters, plus the frame
before and after the fastest moves (`stills.py` for 3D, `render2d.mjs --test=`
for 2D). Tile them, and `look.py compare` a few against the inspo. Check
against the shot list, the recipe and the method.md checklist; fix and re-render.

**Done when** the stills pass the checklist and still match the recipe, or
the issues left are written down for step 9.

### 8. Rough cut

Render the main format in full first (`render.py -- 16x9` or
`render2d.mjs ... --out=out/frames-16x9`; both resume; check progress by
counting frames, never with a pgrep that can match itself), the overlay,
sound.py, encode.sh, then contact-sheet.sh on the mp4 and
`look.py compare inspo/<file> out/<NAME>-16x9.mp4`. Give the person the
local mp4 path as soon as it exists.

Read `out/sound-notes.txt` and `reviews/sound.png`: hits on their frames,
loudness shape against the inspo's, -14 LUFS / ≤ -1 dBTP, voice ≥ 10 dB over the bed.

**Done when** the mp4 exists with the right duration (ffprobe), and you
have looked at its sheet, its compare sheet and its sound notes.

### 9. Fix the three worst defects

Judge only the rendered frames, against the inspo and the shot list. Write
`reviews/defects-<n>.md`: the three largest defects (a look mismatch counts),
each with a timestamp (frame = time × FPS + 1), the evidence, and a local
fix with numbers ("stagger 2 → 3 frames", "land at x 800 not 862"). Patch
only those, re-render only the affected frame ranges, re-encode, new sheets.

**Done when** the new sheets show the three fixed and nothing new broken.
Repeat at most twice more if a defect is still among the worst three.

### 10. Formats and deliverables

Each further format is its own composition (its own layout, camera,
line breaks), never a crop: stills, render, encode, sheet. Check each film
with ffprobe (duration, size, h264 + aac), pull the posters, and write
`README.md` in the studio: the inspo and what was taken from it, the rebuild
commands in order, render times, and **what still needs a human eye**.

Report to the person: the local paths to every film, poster, sheet and
compare sheet, what each gate found and fixed, the honest limits, and that
the final look and sound wait for their approval.

**Done when** every format in the brief has an mp4, a poster and a contact
sheet, README.md lists what needs human review, and the person has the paths.

## Resuming

A studio remembers its state in files. When /motion-studio starts in a
folder that already has brief.md, read brief.md, style-guide.md,
shotlist.md, `inspo/analysis/`, `reviews/` and `out/`, work out the last
completed step from what exists, tell the person, and continue from there.
