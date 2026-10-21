// motion.js: a style-free toolkit for frame-seekable motion. Every function is
// pure in its arguments (frame, progress, seed): no Date, no Math.random, no
// requestAnimationFrame, so frame 150 rendered alone equals frame 150 of a
// full run. No colour, font or size lives here; the look is STYLE data.
//
//   import { easing, tween, stagger, split, clip, drawPath, counter } from './motion.js';
//
// t is in FRAMES unless a name says seconds; k is 0..1 progress.

// --- numbers ---------------------------------------------------------------------
export const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a, b, k) => a + (b - a) * k;
export const progress = (v, a, b) => clamp((v - a) / (b - a || 1));
export const remap = (v, a, b, c, d) => lerp(c, d, progress(v, a, b));
export const smoothstep = (a, b, v) => { const k = progress(v, a, b); return k * k * (3 - 2 * k); };
export const mix = (a, b, k) => (Array.isArray(a) ? a.map((x, i) => lerp(x, b[i], k)) : lerp(a, b, k));

// --- easings (k in, eased k out; input clamped to 0..1) ------------------------
const c01 = (fn) => (k) => fn(clamp(k));
export const ease = {
  linear: c01((k) => k),
  inQuad: c01((k) => k * k),
  outQuad: c01((k) => 1 - (1 - k) ** 2),
  inOutQuad: c01((k) => (k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2)),
  inCubic: c01((k) => k ** 3),
  outCubic: c01((k) => 1 - (1 - k) ** 3),
  inOutCubic: c01((k) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2)),
  inQuart: c01((k) => k ** 4),
  outQuart: c01((k) => 1 - (1 - k) ** 4),
  inOutQuart: c01((k) => (k < 0.5 ? 8 * k ** 4 : 1 - (-2 * k + 2) ** 4 / 2)),
  inExpo: c01((k) => (k <= 0 ? 0 : 2 ** (10 * k - 10))),
  outExpo: c01((k) => (k >= 1 ? 1 : 1 - 2 ** (-10 * k))),
  inOutExpo: c01((k) => (k <= 0 ? 0 : k >= 1 ? 1 : k < 0.5 ? 2 ** (20 * k - 10) / 2 : (2 - 2 ** (-20 * k + 10)) / 2)),
  inBack: c01((k) => 2.70158 * k ** 3 - 1.70158 * k * k),
  outBack: c01((k) => 1 + 2.70158 * (k - 1) ** 3 + 1.70158 * (k - 1) ** 2),
};

// CSS cubic-bezier(x1, y1, x2, y2): type in a curve measured from the inspo
// (frame-stepped positions, or the numbers from AE / Figma / a site's CSS).
// Solves x(u) = k by Newton steps, bisection when that fails, returns y(u).
export function cubicBezier(x1, y1, x2, y2) {
  const bx = (u) => 3 * x1 * u * (1 - u) ** 2 + 3 * x2 * u * u * (1 - u) + u ** 3;
  const by = (u) => 3 * y1 * u * (1 - u) ** 2 + 3 * y2 * u * u * (1 - u) + u ** 3;
  const dx = (u) => 3 * x1 * (1 - u) ** 2 + 6 * (x2 - x1) * u * (1 - u) + 3 * (1 - x2) * u * u;
  return (k) => {
    k = clamp(k);
    if (k === 0 || k === 1) return k;
    let u = k;
    for (let i = 0; i < 8; i++) {
      const d = dx(u);
      if (Math.abs(d) < 1e-6) break;
      const nu = u - (bx(u) - k) / d;
      if (nu < 0 || nu > 1) break;
      u = nu;
    }
    if (Math.abs(bx(u) - k) > 1e-6) {
      let lo = 0;
      let hi = 1;
      for (let i = 0; i < 48; i++) { u = (lo + hi) / 2; if (bx(u) < k) lo = u; else hi = u; }
    }
    return by(u);
  };
}
// The CSS keywords, so a value read off a web inspo pastes as is.
Object.assign(ease, {
  ease: cubicBezier(0.25, 0.1, 0.25, 1),
  'ease-in': cubicBezier(0.42, 0, 1, 1),
  'ease-out': cubicBezier(0, 0, 0.58, 1),
  'ease-in-out': cubicBezier(0.42, 0, 0.58, 1),
});

// --- springs ---------------------------------------------------------------------
// Closed-form damped spring from 0 to rest at 1; t in SECONDS. Under-damped
// overshoots (zeta = damping / (2 sqrt(stiffness * mass)) < 1).
export function spring(t, { stiffness = 170, damping = 26, mass = 1 } = {}) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(stiffness / mass);
  const z = damping / (2 * Math.sqrt(stiffness * mass));
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + ((z * w0) / wd) * Math.sin(wd * t));
  }
  if (z === 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
  const s = Math.sqrt(z * z - 1);
  const r1 = -w0 * (z - s);
  const r2 = -w0 * (z + s);
  return 1 - (r2 * Math.exp(r1 * t) - r1 * Math.exp(r2 * t)) / (r2 - r1);
}
// Seconds until the spring stays within tol of rest (to size holds by).
export function springSettles(p, tol = 0.005, fps = 60) {
  let last = 0;
  for (let i = 1; i < fps * 10; i++) if (Math.abs(1 - spring(i / fps, p)) > tol) last = i;
  return (last + 1) / fps;
}

// Any easing a STYLE can hold, as a function of k:
//   [x1, y1, x2, y2] (cubic-bezier control points, the STYLE default form)
//   | 'outCubic' | 'ease-out' | 'cubic-bezier(.2,.8,.2,1)'
//   | { spring: { stiffness, damping, mass } }: k = 1 maps to the spring's
//     settle time, so `frames` still means "has landed by".
const EASE_CACHE = new Map();
export function easing(spec = 'outCubic') {
  if (typeof spec === 'function') return spec;
  if (spec == null) return ease.linear;
  const key = typeof spec === 'string' ? spec : JSON.stringify(spec);
  if (EASE_CACHE.has(key)) return EASE_CACHE.get(key);
  let fn;
  if (Array.isArray(spec)) fn = cubicBezier(...spec);
  else if (typeof spec === 'string') {
    const m = spec.match(/^cubic-bezier\(([^)]+)\)$/);
    if (m) fn = cubicBezier(...m[1].split(',').map(Number));
    else if (ease[spec]) fn = ease[spec];
    else throw new Error(`unknown easing "${spec}"`);
  } else if (spec.spring) {
    const T = springSettles(spec.spring);
    fn = (k) => (k <= 0 ? 0 : k >= 1 ? 1 : spring(k * T, spec.spring));
  } else if (spec.bezier) fn = cubicBezier(...spec.bezier);
  else throw new Error(`bad easing ${key}`);
  EASE_CACHE.set(key, fn);
  return fn;
}
// An easing that passes its target by about `overshoot` (0.1 = 10 %) and
// settles back by k = 1: STYLE.move.overshoot.
export function withOvershoot(spec, overshoot = 0) {
  const e = easing(spec);
  if (!overshoot) return e;
  return (k) => { const v = e(k); return v + overshoot * Math.sin(Math.PI * clamp((k - 0.3) / 0.7)) * v; };
}

// Progress of a move t frames after it starts. spec = { frames, ease, delay }.
// 0 before, eased 0..1 during (a spring may pass 1), 1 after.
export function tween(t, spec = {}) {
  const k = (t - (spec.delay || 0)) / Math.max(1e-6, spec.frames ?? 8);
  return k <= 0 ? 0 : k >= 1 ? 1 : easing(spec.ease)(k);
}

// --- lifetimes --------------------------------------------------------------------
// Shown from f_in until (not including) f_out. in: 0 -> 1 over inDur frames;
// out: 0 until the last outDur frames, then 0 -> 1 ending on f_out - 1.
export function life(f, f_in, f_out, inDur = 8, outDur = 6) {
  return {
    on: f >= f_in && f < f_out,
    t: f - f_in,
    in: clamp((f - f_in) / Math.max(1, inDur)),
    out: outDur > 0 ? clamp((f - (f_out - outDur - 1)) / (outDur + 1)) : 0,
  };
}
export { life as window };

// keys(f, [[frame, value, ease?], ...]): values are numbers or arrays.
export function keys(f, list, e = 'inOutCubic') {
  if (f <= list[0][0]) return list[0][1];
  for (let i = 1; i < list.length; i++) {
    const [f1, v1, ei] = list[i];
    if (f < f1) {
      const [f0, v0] = list[i - 1];
      return mix(v0, v1, easing(ei || e)((f - f0) / (f1 - f0)));
    }
  }
  return list[list.length - 1][1];
}

// --- stagger ----------------------------------------------------------------------
// Delay in frames of item i of n. each: frames between neighbours (or total:
// frames over all of them). from: 'start' | 'end' | 'center' | 'edges' |
// 'random' (seeded) | an index. ease: spread the delays along a curve.
export function stagger(i, n, { each = 2, total = null, from = 'start', seed = 1, ease: e = null } = {}) {
  const step = total != null ? total / Math.max(1, n - 1) : each;
  let r;
  if (from === 'end') r = n - 1 - i;
  else if (from === 'center') r = Math.abs(i - (n - 1) / 2);
  else if (from === 'edges') r = (n - 1) / 2 - Math.abs(i - (n - 1) / 2);
  else if (from === 'random') r = rng(`${seed}:${i}`)() * (n - 1);
  else if (typeof from === 'number') r = Math.abs(i - from);
  else r = i;
  if (!e) return r * step;
  const span = Math.max(1, n - 1);
  return easing(e)(r / span) * span * step;
}

// --- seeded randomness -------------------------------------------------------------
export function hash(s) {
  let h = 2166136261;
  for (const ch of String(s)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}
// rng(seed)() -> 0..1, the same sequence every run (mulberry32).
export function rng(seed) {
  let a = (typeof seed === 'number' ? seed : hash(seed)) >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// Smooth 1D value noise in -1..1: noise(seed)(t). fbm adds octaves.
export function noise(seed) {
  const s = typeof seed === 'number' ? seed >>> 0 : hash(seed);
  const at = (i) => rng((s ^ Math.imul(i | 0, 2654435761)) >>> 0)() * 2 - 1;
  return (t) => {
    const i = Math.floor(t);
    const k = t - i;
    return lerp(at(i), at(i + 1), k * k * (3 - 2 * k));
  };
}
export function fbm(seed, octaves = 3) {
  const ns = Array.from({ length: octaves }, (_, i) => noise(`${seed}:${i}`));
  const norm = 2 - 2 ** (1 - octaves);
  return (t) => ns.reduce((a, n, i) => a + n(t * 2 ** i) / 2 ** i, 0) / norm;
}
// Handheld shake at frame f: [dx px, dy px, rot deg].
export function shake(seed, f, { amp = 6, freq = 9, rot = 0.4, fps = 30 } = {}) {
  const t = (f / fps) * freq;
  return [amp * fbm(`${seed}x`)(t), amp * fbm(`${seed}y`)(t + 31), rot * fbm(`${seed}r`)(t + 77)];
}

// --- texture -----------------------------------------------------------------------
// grainTile: one seeded noise tile on a canvas, made once. grainShift(f)
// moves it per frame (seeded), which reads as live grain and still seeks.
export function grainTile(size = 256, seed = 'grain', { mono = true } = {}) {
  const cv = document.createElement('canvas');
  cv.width = cv.height = size;
  const g = cv.getContext('2d');
  const img = g.createImageData(size, size);
  const R = rng(seed);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = R() * 255;
    img.data[i] = v;
    img.data[i + 1] = mono ? v : R() * 255;
    img.data[i + 2] = mono ? v : R() * 255;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return cv;
}
export const grainShift = (f, size = 256, seed = 'grain') => {
  const R = rng(`${seed}:${f}`);
  return [-Math.floor(R() * size), -Math.floor(R() * size)];
};

// --- 2D camera ---------------------------------------------------------------------
// cam = { x, y, zoom, rot (deg) } puts world point (x, y) at the screen centre;
// returns the CSS transform for a world layer (transform-origin 0 0).
export function camera2d({ x = 0, y = 0, zoom = 1, rot = 0 } = {}, w, h) {
  return `translate(${w / 2}px,${h / 2}px) rotate(${rot}deg) scale(${zoom}) translate(${-x}px,${-y}px)`;
}
// Where a world point lands on screen under the same camera.
export function project([px, py], { x = 0, y = 0, zoom = 1, rot = 0 } = {}, w, h) {
  const a = (rot * Math.PI) / 180;
  const dx = (px - x) * zoom;
  const dy = (py - y) * zoom;
  return [w / 2 + dx * Math.cos(a) - dy * Math.sin(a), h / 2 + dx * Math.sin(a) + dy * Math.cos(a)];
}

// --- poses -------------------------------------------------------------------------
// pose(k, from): CSS for an element at progress k between a start pose
// (k = 0) and rest (k = 1). from = { x, y (px), scale, rotate (deg), blur (px),
// opacity }. Keys left out stay at rest.
export function pose(k, from = {}) {
  const at = (key, rest) => (from[key] == null ? rest : lerp(from[key], rest, k));
  const tf = [];
  if (from.x != null || from.y != null) tf.push(`translate(${at('x', 0)}px,${at('y', 0)}px)`);
  if (from.rotate != null) tf.push(`rotate(${at('rotate', 0)}deg)`);
  if (from.scale != null) tf.push(`scale(${at('scale', 1)})`);
  return {
    transform: tf.join(' ') || 'none',
    opacity: from.opacity == null ? 1 : clamp(at('opacity', 1)),
    filter: from.blur ? `blur(${Math.max(0, at('blur', 0)).toFixed(2)}px)` : 'none',
  };
}
// Set all of a pose every frame (a property left over from another frame
// would break seeking). `base` is a transform that goes first.
export function applyPose(el, p, base = '') {
  const tf = `${base} ${p.transform === 'none' ? '' : p.transform}`.trim();
  el.style.transform = tf || 'none';
  el.style.opacity = String(p.opacity);
  el.style.filter = p.filter || 'none';
  el.style.clipPath = p.clip || 'none';
  el.style.visibility = p.hidden ? 'hidden' : '';
}

// --- reveals -------------------------------------------------------------------------
// clip(k, dir): a clip-path uncovering the element; k = 0 hidden, 1 shown.
// dir: 'left' (wipes on from the left edge) | 'right' | 'up' (from the bottom)
// | 'down' | 'center' (opens sideways from the middle) | 'middle'
// (vertically) | 'circle' (from cx, cy in %).
export function clip(k, dir = 'left', { cx = 50, cy = 50, round = 0 } = {}) {
  const r = (1 - clamp(k)) * 100;
  const rr = round ? ` round ${round}px` : '';
  switch (dir) {
    case 'right': return `inset(0 0 0 ${r}%${rr})`;
    case 'up': return `inset(${r}% 0 0 0${rr})`;
    case 'down': return `inset(0 0 ${r}% 0${rr})`;
    case 'center': return `inset(0 ${r / 2}% 0 ${r / 2}%${rr})`;
    case 'middle': return `inset(${r / 2}% 0 ${r / 2}% 0${rr})`;
    case 'circle': return `circle(${clamp(k) * 150}% at ${cx}% ${cy}%)`;
    default: return `inset(0 ${r}% 0 0${rr})`;
  }
}
// maskRise(k, h): an element rising into view through its own box (the line
// or word "mask" reveal) without a wrapper: it moves down by its height and is
// clipped to where it will rest. pad leaves room for ascenders/descenders.
export function maskRise(k, h, { pad = 0.3, dir = 1 } = {}) {
  const d = (1 - clamp(k)) * h * (1 + pad) * dir;
  const p = h * pad;
  const clipPath = dir > 0
    ? `inset(${-p}px ${-p}px ${(d - p).toFixed(2)}px ${-p}px)`
    : `inset(${(-d - p).toFixed(2)}px ${-p}px ${-p}px ${-p}px)`;
  return { transform: `translateY(${d.toFixed(2)}px)`, opacity: 1, filter: 'none', clip: clipPath, hidden: k <= 0 };
}

// --- path draw -------------------------------------------------------------------------
// Draws an SVG path on from its start: k = 0 nothing, 1 whole. from > 0 also
// trims the start (a travelling dash). pathLength = 1, so nothing is measured.
export function drawPath(el, k, from = 0) {
  el.setAttribute('pathLength', '1');
  const a = clamp(from);
  const b = clamp(k);
  el.setAttribute('stroke-dasharray', `${Math.max(0, b - a)} 2`);
  el.setAttribute('stroke-dashoffset', String(-a));
}

// --- counters ---------------------------------------------------------------------------
// counter(k, from, to, opts) -> string; k >= 1 always shows exactly `to`.
export function counter(k, from, to, { decimals = 0, locale = 'en-US', prefix = '', suffix = '', pad = 0, grouping = true } = {}) {
  const v = k >= 1 ? to : lerp(from, to, clamp(k));
  let s = Number(v.toFixed(decimals)).toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: grouping });
  if (pad) s = s.padStart(pad, '0');
  return `${prefix}${s}${suffix}`;
}

// --- text ---------------------------------------------------------------------------------
// '*Get paid.* Now' -> [{ text: 'Get paid.', accent: true }, { text: ' Now', accent: false }]
export const accents = (s) => String(s).split(/(\*[^*]+\*)/).filter(Boolean)
  .map((p) => (p.length > 2 && p.startsWith('*') && p.endsWith('*') ? { text: p.slice(1, -1), accent: true } : { text: p, accent: false }));
export const plain = (s) => String(s).replace(/\*/g, '');
export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// split(el, text, { chars }): fills el with one inline-block span per word
// (class "w", plus "acc" for *accent* words) and, with chars, one span per
// character inside it (class "c"). Returns { words, chars, lines() }, where
// lines() groups the words by rendered line (call it after layout). The spans
// get only the display a transform needs; the look is the caller's.
export function split(el, text, { chars = false } = {}) {
  el.textContent = '';
  const words = [];
  const charEls = [];
  for (const part of accents(text)) {
    for (const tok of part.text.split(/(\s+)/)) {
      if (!tok) continue;
      if (/^\s+$/.test(tok)) { el.append(document.createTextNode(' ')); continue; }
      const w = document.createElement('span');
      w.className = part.accent ? 'w acc' : 'w';
      w.style.display = 'inline-block';
      if (chars) {
        for (const ch of tok) {
          const cs = document.createElement('span');
          cs.className = 'c';
          cs.style.display = 'inline-block';
          cs.textContent = ch;
          w.append(cs);
          charEls.push(cs);
        }
      } else w.textContent = tok;
      el.append(w);
      words.push({ el: w, accent: part.accent, text: tok });
    }
  }
  return {
    words,
    chars: charEls,
    lines() {
      const out = [];
      // same line = vertical centres within half the smaller word's height
      for (const w of words) {
        const hh = w.el.offsetHeight;
        const y = w.el.offsetTop + hh / 2;
        const ln = out.find((l) => Math.abs(l.y - y) < Math.min(l.h, hh) / 2);
        if (ln) ln.words.push(w); else out.push({ y, h: hh, words: [w] });
      }
      return out.map((l) => l.words);
    },
  };
}

// --- time from the timeline ---------------------------------------------------------------
// f(beat) matches timeline.py: round(beat * BEAT) + 1.
export function timing(T) {
  const FPS = T.FPS || 30;
  const BEAT = T.BEAT || FPS / 2;
  return {
    FPS,
    BEAT,
    f: (beat) => Math.round(beat * BEAT) + 1,
    beatAt: (frame) => (frame - 1) / BEAT,
    sec: (frames) => frames / FPS,
    phase: (frame) => ((((frame - 1) % BEAT) + BEAT) % BEAT) / BEAT,
    events: (kind, match = {}) => (T.EVENTS || []).filter((e) => e.kind === kind && Object.entries(match).every(([k, v]) => e[k] === v)),
  };
}
