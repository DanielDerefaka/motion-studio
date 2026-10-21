# Inspo: read it, measure it, build its look

The skill has no house style. The look of every film comes from the
inspiration the person drops: a video, a GIF, a link, a template preview,
stills or a website. The job is to make a film that a viewer would place
next to the inspo and say "same hand", built from the person's own content.

Copy the craft, not the content:

| Copy (match it as closely as you can) | Never copy |
|---|---|
| Palette relations (bg / ink / accent, contrast, saturation) | Its logos, brand names, characters, mascots |
| Type feel (family class, weight, width, case, tracking, scale) | Its copy, claims, numbers |
| Layout grid, margins, where the eye goes | Its footage, photos, 3D models, illustrations |
| Motion curves, durations, stagger, overshoot | Its music or voice |
| Pacing, cut rhythm, transitions, camera language | |
| Texture and finish (grain, blur, glow, frame rate on twos) | |
| Sound energy (tempo, genre feel, hit density, loudness shape) | |

If the product has brand colours or fonts, map the inspo's roles onto them
(the inspo's accent becomes the brand's accent) unless the person asks for
the inspo's own palette.

## 1. Gather

| The person gives | Do |
|---|---|
| A video / GIF file | Copy it into `inspo/` (never move or edit their original) |
| A link (X, TikTok, YouTube, Instagram, Vimeo, Dribbble video) | `analyse-inspo.py <url>` downloads it with yt-dlp into inspo/downloads/. If that fails (login wall), ask them for the file |
| A template page (After Effects, Motion Array, Envato, Jitter, Rive) | Download its preview video the same way; its structure (slots, scene order) is part of the look |
| Stills, screenshots, Dribbble shots | Copy into `inspo/`; they give palette, type and layout, not motion; ask whether a motion reference exists |
| A website whose motion they like | Record it with `record.mjs` (a clip per interaction), then analyse the webm |
| Several inspos | Write which one rules which axis ("type and palette from A, pacing from B"); ask if it isn't obvious |
| Words only ("clean, Apple-like") | Ask for one example; if they have none, find 2-3 candidates and let them pick |

## 2. Measure

```sh
cache/venv/bin/python -I $SKILL/scripts/analyse-inspo.py inspo/<file-or-folder-or-url>
```

Per inspo it writes `inspo/analysis/<name>/`: analysis.md (format, shots,
cuts per second, shot lengths, holds vs moves, ease shape per move, global
pan per move, tone, background, palette, BPM, cuts and moves on the beat,
loudness per half second), analysis.json, sheet.jpg, shots.jpg (first,
middle and last frame of every shot), shots/*.png at full size, palette.png
and motion.png.

Then look, in this order:

1. **sheet.jpg**: the whole film at a glance. What class of film is it
   (section 4)? What changes between cells: type, layout, camera, colour?
2. **shots.jpg** and **shots/*.png at full size**: read the type (letterforms,
   weight, width, case, tracking), measure sizes against the frame height
   (cap height / frame height), margins, alignment, the grid.
3. **motion.png**: where the energy is. Steady body or bursts? Moves on the
   beat ticks? A quiet open and a big moment?
4. **The audio numbers**: tempo and loudness shape for sound.py. When a
   second octave is listed ("or ~170 BPM"), listen to the inspo and pick.

Cuts come from two detectors. The shot table's "cut in" column says which: a
**hard** cut changes the whole picture; a **soft** cut is one frame that
differs far more than its neighbours, the picture is otherwise the same or
blurred: a subject swapped on the same backdrop, a whip-blur push, a wipe,
a day/night flip. Soft cuts are often where the signature moves are; step
through each run of them (on the Sims 4 trailer they were the outfit-swap
montage, the whip-blurs between houses and the end-card wipe).

The numbers are evidence; your eyes make the recipe. If a number disagrees
with what you see (a "cut" that is a whip pan, a "hold" with a slow drift),
trust the frames and note it.

## 3. Frame-step the signature moves

Every inspo has 2-3 moves that make it recognisable: the way text arrives,
the transition between scenes, the camera push, the hit on the drop. Find
them on the sheet, then look at every frame:

```sh
cache/venv/bin/python -I $SKILL/scripts/look.py step inspo/<file> 1.8 2.6
```

For each signature move write in style-guide.md:

- **Frames**: how many from rest to rest (at the inspo's fps; convert to ours).
- **Curve**: track one point (a word's baseline, a panel's edge) and note
  what share of the travel is done at each frame. Match it with the table
  below; write the cubic-bezier.
- **Overshoot**: goes past and comes back? By what share of the travel, over
  how many frames? (Spring or back ease.)
- **Order and stagger**: what moves first, the frames between elements, by
  line, word or character.
- **Blur**: motion blur, a directional smear, or crisp frames.
- **Trigger**: on the beat, on a word of the voice, on a cut, on a press.
- **Frame rate feel**: smooth, or held on twos/threes (each pose 2-3 frames:
  collage, hand-made, stop-motion looks).

| Ease | 50 % of travel at | cubic-bezier |
|---|---|---|
| linear | 50 % of the time | 0, 0, 1, 1 |
| ease-out sine | 33 % | 0.61, 1, 0.88, 1 |
| ease-out quad | 29 % | 0.5, 1, 0.89, 1 |
| ease-out cubic | 21 % | 0.33, 1, 0.68, 1 |
| ease-out quart | 16 % | 0.25, 1, 0.5, 1 |
| ease-out quint | 13 % | 0.22, 1, 0.36, 1 |
| ease-out expo | 10 % | 0.16, 1, 0.3, 1 |
| ease-in-out cubic | 50 % (slow both ends) | 0.65, 0, 0.35, 1 |
| ease-in-out quart | 50 % (slower ends) | 0.76, 0, 0.24, 1 |
| ease-in cubic | 79 % | 0.32, 0, 0.67, 0 |
| back out (overshoot ~10 %) | 18 % | 0.34, 1.56, 0.64, 1 |

Modern UI and type motion is mostly ease-out quart to expo on 8-20 frames;
elegant/editorial looks use ease-in-out on long moves; playful looks
overshoot; cuts on hard hits use no easing at all.

## 4. Classify the look and pick the technique

Name every class the inspo uses and its share of screen time. The
technique follows from the class, not from habit:

| Class | Looks like | Build it with |
|---|---|---|
| Kinetic type | Type is the picture: words slam, mask, scale, track | 2D: DOM/canvas text, split by line/word/char, masks, clip-paths |
| Flat motion graphics | Shapes, icons, lines drawing on, Lottie-style | 2D: SVG/canvas, path draw, shape morphs |
| 2D product walkthrough | Real screens sliding, zooming, a cursor, highlight boxes | 2D: captured slabs + screencast footage, a 2D camera transform |
| 3D UI / devices | Panels in space, exploded layers, phones turning | Blender (A/C); light 3D can be three.js inside the 2D renderer |
| 3D character / mascot | A hero acting on the UI | Blender with a rigged .glb (or the kit's toy for tests) |
| Footage-led edit | Recordings or live footage, beat cuts, overlays | 2D comp drawing the clips with footage.js (footage-frames.sh first): grades, whips, type over; or world.py cuts + overlay |
| Shader looks | Liquid gradients, glows, noise fields, particles | 2D: WebGL fragment shader, uniform time = f / FPS, seeded |
| Hand-made / collage | Paper, grain, cut-outs, jitter, on twos | 2D: textures, seeded jitter, poses held 2-3 frames |
| Data story | Charts growing, counters, maps | 2D: SVG, counters, eased values |

Choose the smallest technique that reaches the look. Most inspos are
branch B (2D); Blender is for real depth, light and characters. Write the
choice and why in brief.md.

## 5. Write the look recipe

Fill style-guide.md (the template has every axis). Each line is
**evidence → value → how we build it**, e.g.

> Text enter: shots/003-m-04.10s.png + step 3.9-4.4 s → by word, 11 frames,
> 50 % at frame 2 (expo out), 2-frame stagger, 6 % rise, no blur →
> STYLE.enter = rise / word / 11 / 2 / [0.16,1,0.3,1] / 0.06

Then copy the values into STYLE, FONTS, the BPM and the shot lengths in
src/timeline.py. Shot list durations follow the inspo's rhythm (its median
shot length and cuts per second), adjusted to the person's content.

**Fonts.** Name the inspo's typeface or its class from the letterforms (a, g,
R, Q, terminals, apertures). Use the product's own font if the brand needs
it; otherwise the same face if it's free, else the nearest free one.
Free families that cover most looks (check each licence, note it in brief.md):

| Class | Free options |
|---|---|
| Neo-grotesk (Helvetica/Neue Montreal feel) | Inter, Geist, Manrope, Hanken Grotesk |
| Geometric sans | Satoshi, General Sans (Fontshare), Outfit, Plus Jakarta Sans |
| Display grotesk with character | Clash Display, Cabinet Grotesk (Fontshare), Bricolage Grotesque, Syne |
| Wide / extended | Unbounded, Archivo (wdth axis), Krona One |
| Condensed / poster | Anton, Bebas Neue, Oswald, Archivo Condensed |
| Editorial serif | Instrument Serif, Fraunces, DM Serif Display, Newsreader |
| Mono / tech | JetBrains Mono, Geist Mono, IBM Plex Mono, Space Mono |
| Rounded / friendly | Nunito, Quicksand, M PLUS Rounded 1c |

Download into `<studio>/assets/fonts/` (craft.md, "Fonts"). Never from a
"free fonts" mirror of a paid face.

**Sound.** Same tempo (round to a BPM whose beat is whole frames: 100 = 18,
120 = 15, 90 = 20, 150 = 12), same genre feel and hit density, same loudness
shape; synthesised by sound.py, never the inspo's track. If the inspo has
no audio, choose what fits its energy and say so.

## 6. The look test (the match gate)

Before the shot list is final, build 3-5 seconds that hold the signature
move and one typical frame, with the person's real content. Render it,
encode it, and compare:

```sh
cache/venv/bin/python -I $SKILL/scripts/look.py compare inspo/<file> out/look-test.mp4 \
  --pairs=4.10:1.20,4.40:1.50,7.50:3.10        # inspo time : our time, the same moment
```

Score every axis of the recipe **same / close / off** in
`reviews/look-<n>.md` with the evidence (which cell of the compare sheet).
Fix every "off" with numbers ("display size 0.075 → 0.11 of H", "stagger
2 → 3 frames", "bg #101010 → #0b0d12") and render again. At most three
rounds; then show the person reviews/compare.jpg and the look test: they
approve the look here, before the full film is built.

## 7. What makes it "nice", whatever the style

The inspo sets the style; these hold in every style:

- One idea per shot; the eye knows where to go in the first 5 frames.
- Hierarchy: one big thing, one or two small things.
- Contrast in time: holds make moves read. A film that never rests is noise.
- Every move lands on something (a beat, a word, a cut) and changes something.
- Consistency: one ease family per class of object, the whole film.
- Readable at phone size: hold a still at 390 px wide.
- The ending is a held, composed frame (it is also the poster).
