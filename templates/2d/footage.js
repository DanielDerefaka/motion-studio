// footage.js: real footage inside a 2D composition, frame-exact. Clips are
// numbered JPGs from `sh src/footage-frames.sh` (cache/clips/<clip>/NNNN.jpg,
// counts in cache/clips/index.js); frame n of a clip is always the same
// picture, so the film stays seekable.
//
//   import { clips, clipFrame, drawCover, whip, grade, bloom } from './footage.js';
//   const C = await clips();                       // { estate: 412, ... }
//   const img = await clipFrame('estate', 120);    // decoded <img>, clamped to the clip
//   drawCover(ctx, img, w, h, { zoom: 1.08, x: 0.5, y: 0.5 });
//
// Everything a look needs on top (blur, grade, wipes) is drawn from k in 0..1,
// never from a clock.
import { clamp } from './motion.js';

const BASE = new URL('../cache/clips/', import.meta.url);
let COUNTS = null;
export async function clips() {
  if (!COUNTS) {
    try { COUNTS = (await import(new URL('index.js', BASE).href)).default; }
    catch { throw new Error('cache/clips/index.js missing: run sh src/footage-frames.sh'); }
  }
  return COUNTS;
}

// A small LRU of decoded frames: a shot reads its clip forward, so a few
// dozen frames per clip is plenty.
const LRU = new Map();
const KEEP = 160;
export async function clipFrame(clip, n, { loop = false } = {}) {
  const C = await clips();
  const count = C[clip];
  if (!count) throw new Error(`no clip "${clip}" in cache/clips (have: ${Object.keys(C).join(', ')})`);
  let i = Math.round(n);
  i = loop ? ((i % count) + count) % count : clamp(i, 0, count - 1);
  const key = `${clip}/${i}`;
  if (LRU.has(key)) {
    const img = LRU.get(key);
    LRU.delete(key);
    LRU.set(key, img);
    return img;
  }
  const img = new Image();
  img.src = new URL(`${clip}/${String(i).padStart(4, '0')}.jpg`, BASE).href;
  await img.decode();
  LRU.set(key, img);
  while (LRU.size > KEEP) LRU.delete(LRU.keys().next().value);
  return img;
}

// Cover-fit like CSS object-fit: cover. zoom >= 1 pushes in; x, y (0..1) are
// the point of the source kept at the centre of the frame.
export function drawCover(ctx, img, w, h, { zoom = 1, x = 0.5, y = 0.5, dx = 0, dy = 0, alpha = 1 } = {}) {
  const s = Math.max(w / img.naturalWidth, h / img.naturalHeight) * zoom;
  const iw = img.naturalWidth * s;
  const ih = img.naturalHeight * s;
  const ox = clamp(w / 2 - x * iw, w - iw, 0) + dx;
  const oy = clamp(h / 2 - y * ih, h - ih, 0) + dy;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.drawImage(img, ox, oy, iw, ih);
  ctx.restore();
}

// Directional motion blur of whatever is on `src` (a canvas) into ctx: copies
// smeared along the move. amount is px of smear, angle in degrees (0 = horizontal).
// Taps grow with the smear (one per ~8 px) so long smears don't show ghost
// copies; scale > 1 enlarges about the centre so an offset never shows the edge.
export function smear(ctx, src, amount, { angle = 0, taps = 0, dx = 0, dy = 0, scale = 1 } = {}) {
  const a = (angle * Math.PI) / 180;
  const sw = src.width * scale;
  const sh = src.height * scale;
  const x0 = (src.width - sw) / 2 + dx;
  const y0 = (src.height - sh) / 2 + dy;
  ctx.save();
  if (amount < 0.5) {
    ctx.drawImage(src, x0, y0, sw, sh);
    ctx.restore();
    return;
  }
  const n = Math.max(2, taps || Math.min(96, Math.ceil(amount / 8)));
  for (let t = 0; t < n; t++) {
    const o = (t / (n - 1) - 0.5) * amount;
    ctx.globalAlpha = 1 / (t + 1);              // running mean: every tap weighs the same
    ctx.drawImage(src, x0 + Math.cos(a) * o, y0 + Math.sin(a) * o, sw, sh);
  }
  ctx.restore();
}

// A whip (push) between two shots: the outgoing frame and the incoming one
// travel together as a strip in `dir`, blurred along the move, and the
// incoming shot lands sharp on the cut. k is the share of the travel time:
// with n outgoing frames, outgoing frame i (1..n) is k = i / (n + 1) and the
// landing frame (k = 1) is simply the incoming shot, drawn plain.
// The recipe gives the curve (read the share of travel per frame off a step
// sheet: Sims 4 trailer 55.42-55.52 is 5 / 20 / 55 % = ease-in quad) and the
// blur at the end of the travel as a fraction of the travel axis.
//   whip(ctx, outCanvas, k, w, h, { under: inCanvas, dir: 'up', smear: 0.25 })
const DIRS = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
export function whip(ctx, src, k, w, h, { under = null, dir = 'up', ease = (x) => x * x, smear: blurAmt = 0.4 } = {}) {
  const [ux, uy] = DIRS[dir] || DIRS.up;
  const size = ux ? w : h;
  const e = ease(clamp(k));
  const t = e * size;                           // travel so far, px
  const blur = blurAmt * size * e;              // near sharp on frame 1, heaviest before the landing
  const angle = ux ? 0 : 90;
  smear(ctx, src, blur, { angle, dx: ux * t, dy: uy * t });
  if (under) smear(ctx, under, blur, { angle, dx: ux * (t - size), dy: uy * (t - size) });
}

// Grade with canvas filters (brightness, contrast, saturate as factors, blur in px).
export function grade({ brightness = 1, contrast = 1, saturate = 1, blur = 0, hue = 0 } = {}) {
  const f = [];
  if (brightness !== 1) f.push(`brightness(${brightness})`);
  if (contrast !== 1) f.push(`contrast(${contrast})`);
  if (saturate !== 1) f.push(`saturate(${saturate})`);
  if (hue) f.push(`hue-rotate(${hue}deg)`);
  if (blur) f.push(`blur(${blur}px)`);
  return f.length ? f.join(' ') : 'none';
}

// Soft highlight bloom: the frame blurred and screened over itself.
export function bloom(ctx, src, amount, h) {
  if (!amount) return;
  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  ctx.globalAlpha = clamp(amount);
  ctx.filter = `blur(${Math.round(0.012 * h)}px) brightness(0.9)`;
  ctx.drawImage(src, 0, 0);
  ctx.restore();
}

