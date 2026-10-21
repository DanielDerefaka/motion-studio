# 2D templates

These pages draw a whole frame from the frame number alone, and `render2d.mjs` turns them into numbered PNGs. Every visual value comes from `STYLE` in `timeline.json`. Nothing here is a house style: the defaults are deliberately plain and neutral.

| file | what it is |
|---|---|
| `render2d.mjs` | The driver. It loads a page, injects the timeline, fonts and anchors, calls `renderFrame(f)` for each frame and takes a screenshot of each. |
| `studio.js` | Turns STYLE into pixels: the resolution order, units, type roles, enter and exit kinds. `boot()` is the first thing every page calls. |
| `motion.js` | A generic toolkit: easings, springs, stagger, split, reveals, path drawing, counters, a 2D camera, noise and grain. |
| `captions.js` | Draws CAPTIONS through STYLE. Shared by both pages. |
| `overlay.html` `.js` `.css` | Transparent captions, the lesson chip and the callouts, drawn over a Blender film (anchors). |
| `film2d.html` | An opaque 2D-only film: a starting point with stand-in panels, a camera, a cursor, a counter, the cut and an end card. |
| `presets/ph-lifestyle.js` | One example look that needs code (CSS and hooks). It is loaded only when named. |
| `footage.js`, `footage-frames.sh` | Real footage, drawn frame by frame (see their headers). Use these instead of writing a video loader. |

## Setup and commands

Copy this folder into a studio's `src/`; the studio is the folder above `src/`. Puppeteer is installed once per studio:

```sh
npm i puppeteer@25.11.0
python3 src/timeline.py                       # writes src/timeline.json
node src/render2d.mjs src/overlay.html --test=60,98 --fake
node src/render2d.mjs src/film2d.html --jobs=4
ffmpeg -framerate 30 -i cache/frames2d-16x9/%04d.png -c:v libx264 -crf 17 -pix_fmt yuv420p out/film2d-16x9.mp4
ffmpeg -i out/film2d-16x9.mp4 -vf "fps=2,scale=480:-1,tile=4x4" -frames:v 1 out/sheet.jpg
```

Flags:

| flag | what it does |
|---|---|
| `--format=16x9` \| `9x16` | A key of `FORMATS`. |
| `--from=N --to=M` | Renders that range only. |
| `--test=N,N` | Writes only those frames, to `reviews/2d-test/[name-]fmt-NNNN.png`. Transparent pages also get `-check.png`, the same frame over a checker. |
| `--opaque` | Forces opaque output. |
| `--out=dir` | Output folder. The default is `cache/overlay-<fmt>/`, or `cache/frames2d-<fmt>/` when the output is opaque. |
| `--jobs=K` | Runs K browsers, each on a slice of the frames. |
| `--fake` | Uses drifting stand-in anchors when `cache/anchors-<fmt>.json` is missing. Every run then warns about them. |
| `--style=look.json` | A partial STYLE merged over the timeline's, which may name a `preset`. |
| `--studio=dir` | Sets the studio folder when the page is not in `<studio>/src/`. |

Output always has exactly `FRAMES` files named `NNNN.png`. A frame where `renderFrame` returns `false` is a hard link to one blank PNG, which is kept beside the folder. Check the count with `ls dir | grep -c '^[0-9]*\.png$'`.

Chrome runs with two flags, and both are required:

- `--allow-file-access-from-files`: without it, module imports over `file://` fail.
- `--disable-gpu-rasterization`: without it, GPU raster state carried over from earlier frames makes frame N in a run differ by a few pixels from frame N rendered alone.

## The page contract

```html
<meta name="motion-studio" content="opaque no-anchors">   <!-- or "transparent anchors" -->
<script type="module">
import { boot } from './studio.js';
const S = await boot();          // waits for fonts, resolves STYLE
window.renderFrame = (f) => { /* set EVERYTHING from f */ return true; };   // false = blank frame
window.renderReport = () => ['lines printed once by the driver'];          // optional
</script>
```

The page must be seekable. Frame f drawn alone must be pixel-identical to frame f drawn in a full run. In practice:

- Set every property you ever touch on every frame. `applyPose` does this for transform, opacity, filter, clip-path and visibility.
- Never read a clock.
- Seed all randomness (`rng`, `noise`, `grainShift`).

Canvas, SVG, CSS and WebGL are all fine as long as they meet these rules.

`window.STUDIO` is `{ T, fmt, w, h, tall, opaque, fake, anchors, fonts, fontsReady, styleOverride }`. Every non-null `FONTS` entry (`{display: path|None, body: path|None}`) is embedded as a `data:` URI. Its font family is the key name, with weights 1 to 1000, so the browser never synthesises bold. A `None` entry means the system sans.

## STYLE

Units:

- Every size, `y`, `max_w`, `pad`, `radius` and `dist` is a fraction of the frame height. `S.u(x)` converts it to px. One recipe therefore serves both 16:9 and 9:16.
- Tracking is in em.
- Eases are cubic-bezier control points `[x1, y1, x2, y2]`. A preset may also pass a name or a function.

Resolution order: `studio.js DEFAULTS` ← `T.STYLE` ← `presets/<preset>.js` style ← `--style` file ← `STYLE.formats[fmt]`. A `null` in an override keeps the default object.

### Keys from timeline.py

| key | fields |
|---|---|
| `inspo` | |
| `bg`, `ink`, `accent` | |
| `palette` | A list. film2d uses `palette[0]` as a soft background glow. |
| `type.display`, `type.body` | `{font, weight, size, tracking, line, case}`. `font` is a FONTS key. `case` is `none`, `upper`, `lower` or `title`. |
| `caption` | `{style: plain\|pill\|box\|underline\|none, y (bottom edge of the card), max_w, align, bg, radius, pad}`. `pad` may be `[y, x]`. |
| `enter` | `{kind: rise\|fade\|mask\|scale\|blur\|type\|slide, by: line\|word\|char\|block, frames, stagger, ease, dist}` |
| `exit` | `{kind, frames, ease}`. Each exit mirrors its entry; `mask` drops back through the top of the box. |
| `move` | `{ease, overshoot}`. Used for camera moves, leaders, the cursor and the chip width. |
| `cut` | `{kind: hard\|flash\|whip\|dissolve\|match, frames}`. Used by film2d at the endcard. `match` is treated as `hard`. |
| `hold_min_s` | Captions that hold for less than this are reported. |
| `texture` | `{grain (0..1 opacity), vignette (0..1), blur (fraction of H), chroma (channel split, fraction of H), bloom (0..1)}`. film2d applies these. The overlay ignores them; leave texture to the final grade. |

### Extra keys, read with defaults

These are not in timeline.py:

- `preset`
- `formats`
- `safe` (0.05)
- `type.*.style`
- `type.accent {font, weight, style, scale, color}`, used for `*accent*` words
- `caption.{type, size, color, shadow, rule}`
- `chip {x, y, size, style}`
- `callout {style, line, dot, off, gap, spend, max: {fmt: n}, pulse}`
- `panel {fill, radius, line}`, used by film2d's stand-in panels
- `T.CURRENCY` (film2d's counter prefix)

`COLORS` is ignored.

## Building a look from an inspo

1. **Measure it.** Take stills of the reference:
   - Cap height as a fraction of the frame height, which gives `type.*.size`.
   - Line gap.
   - Tracking.
   - Where captions sit and how wide they run.
   - The treatment behind the text.
   - Frame-step the motion: how many frames an entry takes, the gap between words, whether it overshoots and how far it travels. That gives `enter`.
2. **Write STYLE.** Put it in timeline.py, or in a `looks/<name>.json` passed with `--style`. Most looks need nothing more. For example, the following gives masked words, an accent underline, uppercase display type, a whip cut and grain:

   ```json
   { "bg": "#f1ede4", "ink": "#151412", "accent": "#c2401c",
     "type": { "display": { "size": 0.09, "case": "upper", "tracking": -0.03 } },
     "caption": { "style": "underline", "align": "left", "max_w": 1.1 },
     "enter": { "kind": "mask", "by": "word", "frames": 10, "stagger": 2, "ease": [0.16, 1, 0.3, 1] },
     "cut": { "kind": "whip", "frames": 10 }, "texture": { "grain": 0.12, "vignette": 0.25 } }
   ```

3. **Add code only for what data can't say.** A preset is `presets/<name>.js`, exporting `style` (a partial STYLE) and `hooks`:
   - `hooks.kinds.<name>(k, unit, distPx, S, spec)` → a pose (`{transform, opacity, filter, clip, hidden}`). This adds a new `enter.kind`.
   - `hooks.exits.<name>(...)` is the same thing for `exit.kind`.
   - `hooks.caption.accent(el, {S, card, seed})` returns `(framesSinceWordArrived) => void`, which decorates each `*accent*` word.
   - `hooks.css(S)` returns a CSS string. These are the classes it can target:
     - Captions: `.ms-card`, `.ms-unit`, `.w`, `.w.acc`, `.c`, and `.ms-bg` with `.ms-pill`, `.ms-box` or `.ms-underline`.
     - Chip: `.ms-chip`, `.ms-slot`, `.ms-num`, `.ms-ttl`.
     - Callouts: `.ms-lab`, `.ms-tip`, `.t`, `.s`, `.ms-dot`, `.ms-ring`, `.ms-leader`, and `.ms-money` with `.earn` or `.spend`.
   - Name the preset with `STYLE.preset`, or with `{"preset": "<name>"}` in a `--style` file. `presets/ph-lifestyle.js` is a worked example.
4. **Draw anything else in the page.** If the look is really a drawing (a custom background, particles, a WebGL shader, real footage through `footage.js`), copy `film2d.html` and draw it in `renderFrame` from `f`. Keep values in STYLE so the next look is a data change.

Then check the result:

- Run `--test` at a few frames in both formats.
- Look at the frames at phone size.
- Run `--test=150` and compare it with `0150.png` from a full run:
  `ffmpeg -i a.png -f rawvideo -pix_fmt rgba - | md5`

## motion.js exports

- **Numbers:** `clamp`, `lerp`, `progress`, `remap`, `smoothstep`, `mix`.
- **Easing:**
  - `ease` (linear; in, out and inOut for Quad, Cubic, Quart and Expo; inBack, outBack; and the CSS keywords).
  - `cubicBezier(x1,y1,x2,y2)`, `easing(spec)`, `withOvershoot(spec, o)`.
  - `spring(tSec, {stiffness, damping, mass})`, `springSettles`.
  - `tween(t, {frames, ease, delay})`.
- **Time:**
  - `life` / `window(f, in, out, inDur, outDur)`.
  - `keys(f, [[frame, value, ease?]...], ease)`.
  - `timing(T)`, which returns `{FPS, BEAT, f(beat), beatAt, sec, phase, events(kind, match)}`.
- **Stagger:** `stagger(i, n, {each, total, from: start|end|center|edges|random|index, seed, ease})`.
- **Randomness:** `hash`, `rng`, `noise`, `fbm`, `shake(seed, f, {amp, freq, rot, fps})`.
- **Texture:** `grainTile(size, seed)`, `grainShift(f, size, seed)`.
- **Camera:** `camera2d({x, y, zoom, rot}, w, h)` (a CSS transform for a world layer with origin 0 0), and `project(pt, cam, w, h)`.
- **Poses and reveals:**
  - `pose(k, from)`, `applyPose(el, pose, baseTransform)`.
  - `clip(k, dir)`, with dir `left|right|up|down|center|middle|circle`.
  - `maskRise(k, h, {pad, dir})`.
  - `drawPath(svgPath, k, from)`.
- **Counter:** `counter(k, from, to, {decimals, locale, prefix, suffix, pad, grouping})`.
- **Text:**
  - `accents`, `plain`, `esc`.
  - `split(el, text, {chars})`, which returns `{words, chars, lines()}`.
