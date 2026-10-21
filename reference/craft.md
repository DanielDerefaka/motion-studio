# Craft: fonts, sizes, safe areas, voice, mix

The look (palette, type, motion, texture) comes from the inspo through
style-guide.md (reference/inspo.md). This file is the craft that holds in
every look. One worked example of a full look is example/ph-lifestyle/LOOK.md.

## Fonts

There are no default fonts. Each film gets the fonts its recipe names:

1. The product's own font when the brand needs it (from its CSS: the
   snapshot already loads it through `<base>`; for on-screen text, download
   the same file from where its CSS loads it).
2. Otherwise the inspo's face if it is free, else the nearest free match
   (the class table in inspo.md). Sources: Google Fonts (files from the
   google/fonts GitHub repo, or the css2 API), Fontshare
   (https://www.fontshare.com), or the foundry's own free licence.
3. **Check the licence allows video and commercial use** (OFL, Apache, the
   Fontshare free licence, or the person's own licence) and note it in the
   brief's asset table. Never pull a paid face from a "free fonts" mirror.
4. Save the files into `<studio>/assets/fonts/`, never into the skill.
5. Point `FONTS` in src/timeline.py at them (`display`, `body`, more keys if
   the recipe needs them); the 2D renderer embeds every FONTS entry as a
   data: URI, Blender loads them with `bpy.data.fonts.load`.
6. Check a still: weights, numerals, accents and the tracking still read.

A variable font counts as one file; set the weight/width axes in STYLE.

## Sizes from the inspo

Measure on the full-size shot frames, as fractions of the frame height (H),
so one recipe serves every format:

- Display size = cap height / H ÷ ~0.7 (cap height is ~70 % of the font size
  for most sans faces; check yours).
- Margins, caption y and max width as fractions of H.
- At 1080 px high: 0.06 H ≈ 65 px, 0.1 H ≈ 108 px.

A 9:16 film is its own composition: same fractions of H give much smaller
text relative to the width, so check the widths and break lines again.

## Safe areas

| Where | Keep text and key action inside |
|---|---|
| X / YouTube 16:9 | 5 % margin each side |
| TikTok / Reels / Shorts 9:16 | top 8 %, bottom 22 % (caption + buttons), right 12 % (icons) clear |
| Any | Readable when the frame is 390 px wide (a phone feed): look at a still that size |

## Colour

Map the inspo's palette roles (background, ink, accent, secondary) onto the
product's colours unless the person wants the inspo's own palette. Keep the
inspo's relations: how dark the background is, how saturated the accent,
how much of the frame it covers. The product's own icons keep their colours.

## Explainer shape (when the film teaches)

A promo shows; an explainer teaches. A shape that works, styled by the recipe:

- **Hook (0-3 s):** the one sentence, spoken and on screen, over the most
  alive shot.
- **Chapters:** a marker of where we are (numeral, title, progress), changing
  as the lesson changes. Four lessons in 30 s is the ceiling.
- **One spoken word per beat** in list runs: each word lands with a visible
  change (a press, a bar, a cut). The edit follows the voice.
- **Callouts:** labels on a leader line to an anchor that moves with the
  picture (anchors.py projects 3D points each frame).
- **End card:** the product's own icon, name, line and real URL; the poster
  frame comes from here.

## Voice

Kokoro (kokoro-onnx, Apache 2.0, local, free). Write `say` when the spoken
form differs from the text on screen (numbers, names: "PH" → "P H"). Run
`voice.py --samples` and let the person pick; match the inspo's voice if it
has one (gender, accent, energy), `b*` voices are British. Trim leading and
trailing silence. Treat the voice: high-pass 90 Hz, +2.5 dB at 3 kHz,
-1.5 dB at 250 Hz, levelled per line, 2.5:1 compression.

## Music and effects

All synthesised in numpy/scipy on the timeline's beat grid, no samples, in
the inspo's tempo and energy (inspo.md "Sound"):

- Build to the film's big moment; the beat drops on the reveal.
- One effect per event, chosen by event kind (templates/sound EVENT_SFX).
- Runs of four get rising notes.
- Leave space for the voice: lead lines only between spoken lines.
- Master: -14 LUFS integrated, ≤ -1 dBTP; check loudness per half second
  against the inspo's shape (its analysis.md), and the per-line
  voice-to-bed ratio (≥ 10 dB).
