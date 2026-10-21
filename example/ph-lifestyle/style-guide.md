# Style guide

## From the reference (in.MP4), measured from its frames

- Palette: near-black UI (#141414–#1f1f1f), warm brown studio falloff
  (#2a1a12 → #0c0806), one hero colour, blue hairline selection.
- Composition: the whole app as one tilted plane at the start, then the
  camera at hero height with shallow focus; the eye always goes to the hero.
- Pacing: a meaningful change every 0.5 s beat.
- Motion: squash on landing, snap presses, the camera whips between targets
  and settles; nothing floats without a reason.
- Texture: emissive UI under glossy black glass, bloom on the brightest
  pixels only, 0.5 shutter motion blur, AgX.

## Ours (from the game, docs/UI-STYLE.md)

- The HUD is smoked glass: white text, one green #008751, Poppins 400–700.
  No new colours on the UI. App icons keep their own logo colours.
- The world keeps its own colours (red earth, zinc roofs, green trees).
- Studio: warm dark floor (#120c08) so the green and the red earth pop.
- Hero: Tobi's senator in its own navy (#2a3f7a); the outfit swap at the
  Boutique press uses the game's own outfit palette.
- Light: a big soft key from top-left hidden from glossy rays, a warm rim,
  the world slab as the main light source at night.

## Motion rules

| Class | Rule |
| --- | --- |
| Buttons and app tiles | 3-frame press, 6-frame spring back, emission flash |
| Panels | rise and settle over 9 frames, fall with gravity at the end |
| Camera | smooth, follows the hero at his height; whips on 4-frame ease |
| World cuts | hard cut on the beat with a 2-frame white flash on the tile |
| Hero | playful, every take-off a stretch, every landing a squash |

## Banned defaults

Centred big text with a gradient, everything fading in, the logo arriving
from nowhere, a jump that changes nothing.
