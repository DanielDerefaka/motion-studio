// studio.js: what every composition needs before it draws. It waits for the
// fonts render2d.mjs embedded, resolves the look (STYLE) and turns it into
// pixels for this format, so a composition never holds a colour, size or
// curve of its own.
//
//   import { boot } from './studio.js';
//   const S = await boot();   // { T, fmt, w, h, tall, anchors, style, u, type, enter, exit, ... }
//   window.renderFrame = (f) => { ...; return drewSomething; };
//
// STYLE comes from timeline.json (timeline.py STYLE), resolved as
//   DEFAULTS <- T.STYLE <- preset.style (STYLE.preset) <- --style=file.json
//   <- STYLE.formats[fmt]
// Sizes in STYLE are fractions of the frame HEIGHT (u() makes them px), so one
// recipe serves 16:9 and 9:16; tracking is em; eases are cubic-bezier points.
import { clamp, lerp, easing, withOvershoot, timing, maskRise } from './motion.js';

const SANS = 'system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif';

// The neutral look (timeline.py's demo values) plus the keys timeline.py does
// not have yet, each with a default. None of this is a house style.
export const DEFAULTS = {
  preset: null,               // name of a presets/<name>.js to load (optional)
  formats: {},                // per-format partial STYLE, merged last (optional)
  inspo: [],
  bg: '#101010', ink: '#f2f2f2', accent: '#7a7a7a', palette: [],
  type: {
    display: { font: 'display', weight: 700, size: 0.075, tracking: -0.02, line: 1.0, case: 'none', style: 'normal' },
    body: { font: 'body', weight: 400, size: 0.032, tracking: 0, line: 1.25, case: 'none', style: 'normal' },
    // accent: { font, weight, style, scale, color } (optional: *words* in captions)
  },
  caption: {
    style: 'plain', y: 0.86, max_w: 0.8, align: 'center', bg: null, radius: 0, pad: 0.012,
    type: 'body',              // which type role the captions use
    size: null,                // overrides that role's size for captions
    color: null,               // text colour (default ink)
    shadow: 0,                 // 0..1 soft dark shadow, for plain text over busy footage
    rule: 0.006,               // underline thickness
  },
  enter: { kind: 'fade', by: 'line', frames: 8, stagger: 2, ease: [0.25, 0.1, 0.25, 1.0], dist: 0.03 },
  exit: { kind: 'fade', frames: 6, ease: [0.42, 0.0, 1.0, 1.0] },
  move: { ease: [0.65, 0.0, 0.35, 1.0], overshoot: 0 },
  cut: { kind: 'hard', frames: 0 },
  hold_min_s: 1.0,
  texture: { grain: 0, vignette: 0, blur: 0, chroma: 0, bloom: 0 },
  safe: 0.05,                  // margin kept clear on every side
  chip: { x: null, y: null, size: null, style: null }, // lesson chip: corner (default safe margins), title size (default body), treatment (default caption's)
  callout: {
    style: null,               // label treatment (default caption.style; 'plain' falls back to 'box')
    line: 0.0022, dot: 0.008, off: 0.07, gap: 0.012,
    spend: null,               // money-out colour (default palette[0], else ink)
    max: { '16x9': 4, '9x16': 2 }, // labels on screen at once, per format
    pulse: 0,                  // frames per ring pulse on a pin (0 = no ring)
  },
};

const plainObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
export function merge(a, b) {
  if (!plainObj(a) || !plainObj(b)) return b === undefined ? a : b;
  const o = { ...a };
  for (const [k, v] of Object.entries(b)) o[k] = v === null && plainObj(a[k]) ? a[k] : merge(a[k], v);
  return o;
}

export async function boot() {
  const S0 = globalThis.STUDIO;
  if (!S0) {
    document.body.textContent = 'No studio data: render this page through src/render2d.mjs.';
    throw new Error('window.STUDIO missing: open this composition with node src/render2d.mjs');
  }
  await S0.fontsReady;
  await document.fonts.ready;
  let style = merge(DEFAULTS, S0.T.STYLE || {});
  let preset = null;
  const name = S0.styleOverride?.preset ?? style.preset;
  if (name) {
    preset = await import(`./presets/${name}.js`);
    style = merge(style, preset.style || {});
  }
  if (S0.styleOverride) style = merge(style, S0.styleOverride);
  // STYLE.formats = { '9x16': { partial STYLE } }: when a measured look really
  // differs per format (most recipes need none: sizes are fractions of H).
  if (style.formats?.[S0.fmt]) style = merge(style, style.formats[S0.fmt]);
  const S = { ...S0, style, preset, hooks: preset?.hooks || {}, time: timing(S0.T) };
  const { w, h } = S;
  S.u = (x) => (x == null ? 0 : x * h);           // STYLE length -> px
  S.safe = { l: S.u(style.safe), r: w - S.u(style.safe), t: S.u(style.safe), b: h - S.u(style.safe) };
  S.family = (key) => (S0.fonts?.[key] ? `"${S0.fonts[key]}", ${SANS}` : SANS);
  S.type = (role, extra = {}) => typeCSS(S, role, extra);
  S.enter = (k, unit, spec) => enterPose(S, k, unit, { ...style.enter, ...spec });
  S.exit = (k, unit, spec) => exitPose(S, k, unit, { ...style.exit, dist: style.enter.dist, ...spec });
  S.ease = (spec) => easing(spec);
  S.moveEase = withOvershoot(style.move.ease, style.move.overshoot);
  S.kinds = { ...KINDS, ...(S.hooks.kinds || {}) };

  const root = document.documentElement.style;
  root.setProperty('--w', `${w}px`);
  root.setProperty('--h', `${h}px`);
  root.setProperty('--bg', style.bg);
  root.setProperty('--ink', style.ink);
  root.setProperty('--accent', style.accent);
  style.palette.forEach((c, i) => root.setProperty(`--p${i}`, c));
  document.documentElement.classList.add(S.tall ? 'tall' : 'wide', `fmt-${S.fmt}`);
  if (S.hooks.css) document.head.append(Object.assign(document.createElement('style'), { textContent: S.hooks.css(S) }));
  return S;
}

const CASE = { none: 'none', upper: 'uppercase', lower: 'lowercase', title: 'capitalize', uppercase: 'uppercase', lowercase: 'lowercase', capitalize: 'capitalize' };
// A type role as CSS properties (camelCase, ready for Object.assign(el.style, ...)).
export function typeCSS(S, role, extra = {}) {
  const r = { ...(S.style.type[role] || S.style.type.body), ...extra };
  return {
    fontFamily: S.family(r.font),
    fontWeight: String(r.weight ?? 400),
    fontStyle: r.style || 'normal',
    fontSize: `${S.u(r.size).toFixed(2)}px`,
    letterSpacing: `${r.tracking || 0}em`,
    lineHeight: String(r.line ?? 1.2),
    textTransform: CASE[r.case] || 'none',
  };
}

// Entry kinds: k is eased progress 0..1 (it may pass 1 on a spring), unit is
// { w, h } of the thing moving (px), d = STYLE dist in px. Each returns a pose
// for applyPose(). A preset can add kinds (hooks.kinds) with the same shape.
const KINDS = {
  fade: (k) => ({ opacity: clamp(k) }),
  rise: (k, unit, d) => ({ transform: `translateY(${((1 - k) * d).toFixed(2)}px)`, opacity: clamp(k * 1.6) }),
  slide: (k, unit, d) => ({ transform: `translateX(${((k - 1) * d).toFixed(2)}px)`, opacity: clamp(k * 1.6) }),
  // grows from 1 - 5 * dist (dist 0.03 -> 85 %)
  scale: (k, unit, d, S) => ({ transform: `scale(${lerp(1 - Math.min(0.9, (5 * d) / S.h), 1, k).toFixed(4)})`, opacity: clamp(k * 1.6) }),
  // blur from dist / 2 px (dist 0.03 at 1080 high -> 16 px)
  blur: (k, unit, d) => ({ opacity: clamp(k * 1.3), filter: `blur(${Math.max(0, (1 - k) * d * 0.5).toFixed(2)}px)` }),
  mask: (k, unit) => maskRise(k, unit.h),
  // typewriter: the unit (normally a char) is either there or not
  type: (k) => ({ opacity: k > 0 ? 1 : 0 }),
  none: () => ({}),
};
function full(p) {
  return { transform: 'none', opacity: 1, filter: 'none', clip: 'none', hidden: false, ...p };
}
export function enterPose(S, k, unit, spec) {
  const fn = S.kinds[spec.kind] || S.kinds.fade;
  return full(fn(k, unit, S.u(spec.dist), S, spec));
}
// Exits mirror the entry: rise leaves upwards, slide carries on, mask drops
// back through the top of its box, scale shrinks, blur blurs, type and fade fade.
export function exitPose(S, k, unit, spec) {
  if (k <= 0) return full({});
  const d = S.u(spec.dist);
  const o = clamp(1 - k);
  switch (spec.kind) {
    case 'rise': return full({ transform: `translateY(${(-k * d).toFixed(2)}px)`, opacity: o });
    case 'slide': return full({ transform: `translateX(${(k * d).toFixed(2)}px)`, opacity: o });
    case 'scale': return full({ transform: `scale(${lerp(1, 1 - Math.min(0.9, (5 * d) / S.h), k).toFixed(4)})`, opacity: o });
    case 'blur': return full({ opacity: o, filter: `blur(${(k * d * 0.5).toFixed(2)}px)` });
    case 'mask': return full(maskRise(1 - k, unit.h, { dir: -1 }));
    case 'none': case 'hard': return full({ hidden: k >= 1 });
    default:
      if (S.hooks.exits?.[spec.kind]) return full(S.hooks.exits[spec.kind](k, unit, d, S, spec));
      return full({ opacity: o });
  }
}
// Combine an entry pose and an exit pose on one element (exit wraps entry).
export function stack(a, b) {
  const tf = [b.transform, a.transform].filter((x) => x && x !== 'none').join(' ') || 'none';
  const fl = [a.filter, b.filter].filter((x) => x && x !== 'none').join(' ') || 'none';
  return { transform: tf, opacity: a.opacity * b.opacity, filter: fl, clip: b.clip !== 'none' ? b.clip : a.clip, hidden: a.hidden || b.hidden };
}

// The box treatment STYLE names (caption.style, or callout.style) as CSS for
// the element behind the words. Returns null when nothing is drawn there.
export function boxCSS(S, kind, { bg, radius, h } = {}) {
  const fill = bg || S.style.caption.bg || S.style.bg;
  if (kind === 'pill') return { background: fill, borderRadius: `${(radius ? S.u(radius) : h / 2).toFixed(2)}px` };
  if (kind === 'box') return { background: fill, borderRadius: `${S.u(radius ?? S.style.caption.radius).toFixed(2)}px` };
  if (kind === 'underline') return { background: S.style.accent, borderRadius: '0px' };
  return null;
}

// Where an anchor is on frame f (1-based): [x, y, visible] or null.
export function anchorAt(S, id, f) {
  const a = S.anchors[id];
  if (!a) return null;
  return a[Math.min(a.length, Math.max(1, f)) - 1];
}
