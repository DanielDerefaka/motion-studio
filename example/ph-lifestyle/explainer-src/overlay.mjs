// The 2D overlay: captions, lesson chips, callouts and money pops, one
// transparent PNG per frame, composited over the Blender film in ffmpeg.
// Everything is laid out from the frame number by render(frame) in one page:
// no CSS animations, no state carried between frames.
//
//   node src/overlay.mjs [--format=9x16] [--from=N --to=M] [--test=N,N,...]
//
// Reads src/timeline.json and cache/anchors-<fmt>.json (the Blender exporter's
// projected anchor points). Until that exists it writes and uses
// cache/anchors-fake-<fmt>.json, loudly. Writes cache/overlay-<fmt>/NNNN.png
// (empty frames hard-link one shared _blank.png); --test writes only the
// listed frames to reviews/overlay-test/, transparent and over a dark checker.
import { readFile, writeFile, mkdir, rm, link, access } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import puppeteer from 'puppeteer';
import { STUDIO } from './live.mjs';

const arg = (k) => process.argv.find((a) => a.startsWith(`--${k}=`))?.split('=')[1];
const FMT = arg('format') === '9x16' ? '9x16' : '16x9';
const TALL = FMT === '9x16';
const T = JSON.parse(await readFile(path.join(STUDIO, 'src', 'timeline.json'), 'utf8'));
const W = TALL ? 1080 : 1920;
const H = TALL ? 1920 : 1080;
const N = T.FRAMES;
const TEST = arg('test')?.split(',').map(Number).filter(Boolean);
const FROM = Math.max(1, Number(arg('from') || 1));
const TO = Math.min(N, Number(arg('to') || N));
const exists = (p) => access(p).then(() => true, () => false);

// --- anchors ----------------------------------------------------------------
const REAL = path.join(STUDIO, 'cache', `anchors-${FMT}.json`);
const FAKE = path.join(STUDIO, 'cache', `anchors-fake-${FMT}.json`);

// Slowly drifting stand-ins laid out roughly like the game screen: the needs
// rows clustered top left, the dock along the bottom, the phone in the middle.
function fakeAnchors() {
  const ui = {};
  for (const [id, a] of Object.entries(T.ANCHORS)) {
    let p;
    if (a.slab === 'me') {
      const [ox, oy] = T.NEEDS_ORIGIN;
      p = [ox + (a.at[0] - ox) * T.NEEDS_GROW, oy + (a.at[1] - oy) * T.NEEDS_GROW];
    } else if (a.at) p = a.at;
    else {
      const r = { jobs: T.DOCK['work-hire'], spray: T.DOCK.spray, cars: T.APPS.cars, property: T.APPS.property,
        boutique: T.APPS.boutique, hail: T.APPS.hail, hide: T.HUD['#btn-hide'] }[id];
      p = r ? [r.x + r.w / 2, r.y + r.h / 2] : { bus: [900, 900], tobi: [1000, 520] }[id];
    }
    ui[id] = p;
  }
  const map = TALL
    ? ([x, y]) => [(x - 960) * 0.62 + 540, (y - 540) * 1.05 + 900]
    : ([x, y]) => [(x - 960) * 0.92 + 960, (y - 540) * 0.92 + 520];
  const anchors = {};
  for (const [id, p0] of Object.entries(ui)) {
    const seed = [...id].reduce((s, c) => s * 31 + c.charCodeAt(0), 7) % 1000;
    const [bx, by] = map(p0);
    anchors[id] = Array.from({ length: N }, (_, i) => {
      const t = i / 30;
      const x = bx + 40 * Math.sin(t * 0.7 + seed) + 18 * Math.sin(t * 1.9 + seed * 2);
      const y = by + 26 * Math.cos(t * 0.6 + seed) + 10 * Math.sin(t * 2.3 + seed);
      let vis = x > 0 && x < W && y > 0 && y < H ? 1 : 0;
      if (id === 'cars' && i >= 478 && i < 492) vis = 0;               // a dropout to test the fade
      if (TALL && id === 'chat') vis = 0;                              // off the tall camera all along
      return [Math.round(x * 10) / 10, Math.round(y * 10) / 10, vis];
    });
  }
  return { fmt: FMT, w: W, h: H, frames: N, fake: true, anchors };
}

let A;
if (await exists(REAL)) {
  A = JSON.parse(await readFile(REAL, 'utf8'));
  if (A.w !== W || A.h !== H || A.anchors[Object.keys(T.ANCHORS)[0]]?.length !== N) {
    throw new Error(`${REAL}: expected ${W}x${H} and ${N} entries per anchor`);
  }
  const missing = Object.keys(T.ANCHORS).filter((k) => !A.anchors[k]);
  if (missing.length) console.warn(`overlay: anchors missing from ${path.basename(REAL)}: ${missing.join(', ')} (their callouts never show)`);
  console.log(`overlay: real anchors from ${path.relative(STUDIO, REAL)}`);
} else {
  A = fakeAnchors();
  await writeFile(FAKE, JSON.stringify(A));
  const bar = '!'.repeat(78);
  console.warn(`\n${bar}\n!! overlay: ${path.relative(STUDIO, REAL)} does not exist yet.\n!! Using FAKE drifting anchors (${path.relative(STUDIO, FAKE)}).\n!! Callout positions in this render are placeholders. Re-run once the exporter has written the real file.\n${bar}\n`);
}

// --- fonts (embedded: file:// fonts don't load into a setContent page) -------
const fontUrl = async (p) => `url(data:font/otf;base64,${(await readFile(p)).toString('base64')})`;
const LIB = path.join(os.homedir(), 'Library', 'Fonts');
const EN = (cut) => path.join(LIB, `Editor'sNote-${cut}.otf`);
const FONT_CSS = `
@font-face{font-family:MZ;src:${await fontUrl(T.FONTS.bold)};font-weight:700}
@font-face{font-family:ENS;src:${await fontUrl(EN('Semibold'))};font-weight:600}
@font-face{font-family:ENR;src:${await fontUrl(EN('Regular'))};font-weight:400}`;

// --- per-format layout -------------------------------------------------------
const L = TALL ? {
  cap: { cx: 540, cy: 1462, size: 74, maxW: 940, lh: 1.14 },
  chip: { x: 56, y: 150, num: 58, title: 32 },
  safe: { l: 56, r: 1024, t: 130, b: 1330 },
  label: { title: 32, sub: 23, off: 84 },
  money: 100,
} : {
  cap: { cx: 960, cy: 938, size: 64, maxW: 1500, lh: 1.14 },
  chip: { x: 64, y: 56, num: 54, title: 30 },
  safe: { l: 48, r: 1872, t: 48, b: 862 },
  label: { title: 30, sub: 22, off: 92 },
  money: 90,
};

const DATA = {
  W, H, N, L, GREEN: T.GREEN,
  captions: T.CAPTIONS, chapters: T.CHAPTERS, callouts: T.CALLOUTS,
  anchors: Object.fromEntries(T.CALLOUTS.map((c) => [c.anchor, A.anchors[c.anchor] || null])),
};

// --- the page ----------------------------------------------------------------
const HTML = `<!doctype html><html><head><meta charset="utf-8"><style>
${FONT_CSS}
:root{--green:${T.GREEN};--glass:rgba(20,22,24,.72);--edge:rgba(255,255,255,.14)}
html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden;background:transparent}
html.check{background:repeating-conic-gradient(#2b2d30 0 25%,#1f2124 0 50%) 0 0/48px 48px}
html.check body{background:radial-gradient(ellipse at 50% 40%,rgba(120,90,60,.25),transparent 70%)}
body{position:relative;font-family:MZ,system-ui,sans-serif;font-weight:700;color:#fff;-webkit-font-smoothing:antialiased}
.abs{position:absolute;left:0;top:0;will-change:transform,opacity}
.hide{display:none!important}

/* captions */
.card{position:absolute;left:0;top:0;width:${L.cap.maxW}px;text-align:center;font-size:${L.cap.size}px;line-height:${L.cap.lh};
  letter-spacing:-.012em;text-wrap:balance}
.frag{display:inline-block;white-space:nowrap;position:relative;transform-origin:50% 80%;z-index:2;
  text-shadow:0 2px 3px rgba(0,0,0,.45),0 4px 22px rgba(0,0,0,.55)}
.acc{font-family:ENS;font-weight:600;font-style:italic;font-size:1.16em;letter-spacing:-.005em;position:relative;
  display:inline-block;line-height:1;padding:0 .04em}
.acc svg{position:absolute;left:-5%;width:110%;bottom:-.1em;height:.44em;overflow:visible;z-index:-1}
.pill{position:absolute;left:0;top:0;border-radius:22px;background:rgba(14,16,18,.42);z-index:1;
  box-shadow:0 10px 40px rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.06)}

/* lesson chip */
#chip{position:absolute;left:${L.chip.x}px;top:${L.chip.y}px;height:${Math.round(L.chip.num * 1.42)}px;border-radius:999px;
  background:var(--glass);border:1px solid var(--edge);box-shadow:0 12px 36px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.06);
  transform-origin:0 50%;overflow:hidden}
#chip .slot{position:absolute;left:0;top:0;height:100%;display:flex;align-items:center;gap:16px;padding:0 30px 0 26px;
  white-space:nowrap;transform-origin:50% 50%;backface-visibility:hidden}
#chip .num{font-family:ENR;font-style:italic;font-weight:400;font-size:${L.chip.num}px;line-height:1;color:#fff;
  letter-spacing:-.02em;margin-top:-.04em;min-width:1.1em}
#chip .col{display:flex;flex-direction:column;gap:9px}
#chip .ttl{font-size:${L.chip.title}px;line-height:1;letter-spacing:-.01em}
#chip .segs{display:flex;gap:6px;height:6px}
#chip .seg{height:6px;border-radius:3px;background:rgba(255,255,255,.22)}
#chipwrap{position:absolute;left:0;top:0;perspective:600px}

/* callouts */
#lines{position:absolute;left:0;top:0;width:${W}px;height:${H}px;overflow:visible;filter:drop-shadow(0 1px 3px rgba(0,0,0,.5))}
.lab{position:absolute;left:0;top:0;padding:13px 20px 15px;border-radius:16px;background:var(--glass);border:1px solid var(--edge);
  box-shadow:0 10px 30px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.06);white-space:nowrap}
.lab .t{font-size:${L.label.title}px;line-height:1.08;letter-spacing:-.01em}
.lab .s{font-size:${L.label.sub}px;line-height:1.2;color:rgba(255,255,255,.7);margin-top:5px;letter-spacing:0}
.lab.tip{padding:9px 16px 10px 12px;border-radius:999px;display:flex;align-items:center;gap:10px}
.lab.tip .t{font-size:${Math.round(L.label.sub * 1.0)}px}
.lab.tip .s{margin:0;font-size:${Math.round(L.label.sub * 0.86)}px;color:#1b1406;background:#f2b134;padding:4px 10px 5px;border-radius:999px;line-height:1}
.lab.tip i{display:inline-flex;width:${Math.round(L.label.sub * 1.15)}px;height:${Math.round(L.label.sub * 1.15)}px;border-radius:50%;background:#f2b134;color:#1b1406;
  font-style:normal;font-size:${Math.round(L.label.sub * 0.85)}px;align-items:center;justify-content:center;line-height:1}
.dot{position:absolute;left:0;top:0;width:0;height:0}
.dot b{position:absolute;left:-7px;top:-7px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 0 0 3px var(--green),0 2px 8px rgba(0,0,0,.6)}
.dot u{position:absolute;left:-12px;top:-12px;width:24px;height:24px;border-radius:50%;border:3px solid var(--green);box-sizing:border-box}
.money{position:absolute;left:0;top:0;font-size:${L.money}px;line-height:1;letter-spacing:-.02em;white-space:nowrap;
  transform-origin:50% 100%;filter:drop-shadow(0 6px 14px rgba(0,0,0,.45))}
.money .ol{position:absolute;left:0;top:0;color:#fff;-webkit-text-stroke:${Math.round(L.money / 6)}px #fff}
.money .fi{position:relative}
.money.earn .fi{color:var(--green)}
.money.spend .fi{color:#e8452c}
</style></head><body>
<div id="caps"></div>
<svg id="lines"></svg>
<div id="calls"></div>
<div id="chipwrap"><div id="chip"></div></div>
</body></html>`;

// Everything below runs inside the page.
function pageMain(D) {
  const { L, W, H } = D;
  const $ = (tag, cls, parent, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    parent?.append(n);
    return n;
  };
  const SVGNS = 'http://www.w3.org/2000/svg';
  const svg = (tag, attrs, parent) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    parent?.append(n);
    return n;
  };
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, k) => a + (b - a) * k;
  // Springs in frames: overshoot ~12% then settle; 0 before t=0, 1 after dur.
  const spring = (t, dur = 8) => (t <= 0 ? 0 : t >= dur ? 1 : 1 - Math.exp(-6 * (t / dur)) * Math.cos(9 * (t / dur)));
  const easeOut = (k) => 1 - (1 - clamp(k)) ** 3;
  const easeIn = (k) => clamp(k) ** 2;
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

  // A hand-drawn brush swash, as a filled tapered stroke along a gentle wave.
  function swashPath(seed) {
    const n = 28;
    const top = [];
    const bot = [];
    for (let i = 0; i <= n; i++) {
      const u = i / n;
      const x = u * 100;
      const y = 50 + 16 * Math.sin(u * Math.PI * 1.15 + seed) - 18 * u + 9;
      const w = 6 + 40 * Math.sin(Math.PI * clamp(u * 0.92 + 0.04)) ** 0.6;
      top.push([x, y - w / 2]);
      bot.push([x + 1.2, y + w / 2]);
    }
    const pts = [...top, ...bot.reverse()];
    return `M${pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('L')}Z`;
  }

  // --- captions --------------------------------------------------------------
  const capsEl = document.getElementById('caps');
  const cards = D.captions.map((c, ci) => {
    const el = $('div', 'card abs', capsEl);
    const frags = c.parts.map((p, pi) => {
      const f = $('span', 'frag', el);
      const segs = p.text.split(/(\*[^*]+\*)/).filter(Boolean);
      let acc = null;
      for (const s of segs) {
        if (s.startsWith('*')) {
          acc = $('span', 'acc', f);
          acc.append(document.createTextNode(s.slice(1, -1)));
          const sv = svg('svg', { viewBox: '0 0 100 100', preserveAspectRatio: 'none' }, acc);
          const id = `cl${ci}_${pi}`;
          const cp = svg('clipPath', { id }, svg('defs', {}, sv));
          const rect = svg('rect', { x: -2, y: -50, width: 0, height: 200 }, cp);
          svg('path', { d: swashPath(ci * 1.7 + pi), fill: D.GREEN, 'clip-path': `url(#${id})` }, sv);
          acc._clip = rect;
        } else f.append(document.createTextNode(s));
      }
      if (pi < c.parts.length - 1) el.append(document.createTextNode(' '));
      return { ...p, el: f, acc };
    });
    return { ...c, el, frags };
  });
  // Measure: each fragment's box inside its card, grouped into lines.
  for (const c of cards) {
    const w = c.el.offsetWidth;
    const h = c.el.offsetHeight;
    c.box = { w, h };
    const LH = L.cap.size * L.cap.lh;
    const lines = [];
    for (const fr of c.frags) {
      fr.x = fr.el.offsetLeft;
      fr.y = fr.el.offsetTop;
      fr.w = fr.el.offsetWidth;
      fr.h = fr.el.offsetHeight;
      const mid = fr.y + fr.h / 2;
      let ln = lines.find((x) => Math.abs(x.mid - mid) < LH * 0.5);
      if (!ln) lines.push((ln = { mid, frs: [] }));
      ln.frs.push(fr);
    }
    c.lines = lines.map(({ frs }) => {
      const pill = $('div', 'pill');
      c.el.prepend(pill);
      const top = Math.min(...frs.map((f) => f.y));
      const bot = Math.max(...frs.map((f) => f.y + f.h));
      return { frs, pill, top, bot };
    });
    c.left = L.cap.cx - w / 2;
    c.top = L.cap.cy - h / 2;
    c.el.style.transform = `translate(${c.left}px,${c.top}px)`;
  }

  function renderCaptions(f) {
    let any = false;
    for (const c of cards) {
      const on = f >= c.f_in && f < c.f_out;
      c.el.classList.toggle('hide', !on);
      if (!on) continue;
      any = true;
      // Leave fast: the last 4 frames of the card lift and vanish.
      const last = c.frags[c.frags.length - 1].f;
      const X = Math.max(1, Math.min(4, c.f_out - last - 2));
      const e = clamp((f - (c.f_out - X)) / X);
      const ex = e > 0 ? (f - (c.f_out - X - 1)) / (X + 1) : 0;
      c.el.style.opacity = String(1 - easeIn(ex));
      c.el.style.transform = `translate(${c.left}px,${c.top - 22 * easeIn(ex)}px) scale(${1 - 0.03 * ex})`;
      c.el.style.transformOrigin = '50% 50%';
      for (const fr of c.frags) {
        const t = f - fr.f;
        if (t < 0) { fr.el.style.visibility = 'hidden'; continue; }
        fr.el.style.visibility = 'visible';
        const s = spring(t, 8);
        const big = fr.acc ? 1.08 : 1;
        const sc = lerp(0.5, 1, s) * (t < 8 ? lerp(big, 1, clamp(t / 8)) : 1);
        fr.el.style.opacity = String(clamp((t + 1) / 2));
        fr.el.style.transform = `translateY(${(1 - s) * 30}px) scale(${sc}) rotate(${(1 - s) * (fr.acc ? -6 : -3)}deg)`;
        if (fr.acc) fr.acc._clip.setAttribute('width', String(104 * easeOut((t - 2) / 7)));
      }
      // Pills behind each line follow the words as they arrive.
      for (const ln of c.lines) {
        const shown = ln.frs.filter((fr) => f >= fr.f);
        if (!shown.length) { ln.pill.style.opacity = '0'; continue; }
        const ext = (k) => {
          const frs = ln.frs.slice(0, k);
          return [Math.min(...frs.map((x) => x.x)), Math.max(...frs.map((x) => x.x + x.w))];
        };
        const k = shown.length;
        const [l1, r1] = ext(k);
        const [l0, r0] = k > 1 ? ext(k - 1) : [(l1 + r1) / 2 - 20, (l1 + r1) / 2 + 20];
        const s = spring(f - shown[k - 1].f, 8);
        const l = lerp(l0, l1, s) - 26;
        const r = lerp(r0, r1, s) + 26;
        const pad = 6;
        ln.pill.style.opacity = String(clamp((f - shown[0].f + 1) / 3));
        ln.pill.style.width = `${r - l}px`;
        ln.pill.style.height = `${ln.bot - ln.top + pad * 2}px`;
        ln.pill.style.transform = `translate(${l}px,${ln.top - pad}px)`;
      }
    }
    return any;
  }

  // --- lesson chip -----------------------------------------------------------
  const chipWrap = document.getElementById('chipwrap');
  const chip = document.getElementById('chip');
  const SEG = { on: 34, off: 12 };
  const chapters = D.chapters.map((c, i) => {
    const slot = $('div', 'slot abs', chip, `<span class="num">${esc(c.n)}</span><span class="col"><span class="ttl">${esc(c.title)}</span><span class="segs">${
      D.chapters.map(() => '<i class="seg"></i>').join('')}</span></span>`);
    return { ...c, i, slot, segs: [...slot.querySelectorAll('.seg')] };
  });
  for (const c of chapters) {
    c.segs.forEach((s, j) => { s.style.width = `${j === c.i ? SEG.on : SEG.off}px`; });
    c.w = c.slot.offsetWidth;
  }
  const CH0 = chapters[0].f_in;
  const CH1 = chapters[chapters.length - 1].f_out;
  const CHIP = { x: L.chip.x, y: L.chip.y, w: Math.max(...chapters.map((c) => c.w)), h: chip.offsetHeight };

  function renderChip(f) {
    const on = f >= CH0 && f < CH1;
    chipWrap.classList.toggle('hide', !on);
    if (!on) return false;
    const cur = chapters.findIndex((c) => f >= c.f_in && f < c.f_out);
    const c = chapters[cur];
    const prev = chapters[cur - 1];
    // In from the left on a spring; out to the left in the last 5 frames.
    const sIn = spring(f - CH0, 10);
    const ex = clamp((f - (CH1 - 5) + 1) / 5);
    const x = (1 - sIn) * -(CHIP.w + L.chip.x + 40) - easeIn(ex) * 60;
    chip.style.transform = `translateX(${x}px) scale(${lerp(0.9, 1, clamp(sIn))})`;
    chip.style.opacity = String(clamp((f - CH0 + 1) / 2) * (1 - easeIn(ex)));
    // The width springs from one title to the next at each swap.
    const sw = prev ? spring(f - c.f_in, 9) : 1;
    chip.style.width = `${prev ? lerp(prev.w, c.w, sw) : c.w}px`;
    for (const ch of chapters) {
      const s = ch.slot;
      if (ch === c) {
        // Flip in from below, a split-flap on a spring.
        const t = prev ? f - c.f_in - 2 : 99;
        const sp = spring(t, 9);
        s.style.visibility = t < 0 ? 'hidden' : 'visible';
        s.style.transform = `translateY(${(1 - sp) * 26}px) rotateX(${(1 - sp) * -80}deg)`;
        s.style.opacity = String(clamp((t + 1) / 2));
        // The current segment fills green, wide; passed ones stay white.
        ch.segs.forEach((g, j) => {
          const grow = j === ch.i ? spring(f - ch.f_in, 10) : 1;
          g.style.width = `${j === ch.i ? lerp(SEG.off, SEG.on, grow) : SEG.off}px`;
          g.style.background = j === ch.i ? D.GREEN : j < ch.i ? 'rgba(255,255,255,.78)' : 'rgba(255,255,255,.22)';
        });
      } else if (ch === prev && f - c.f_in < 4) {
        const k = (f - c.f_in + 1) / 4;
        s.style.visibility = 'visible';
        s.style.transform = `translateY(${-24 * easeIn(k)}px) rotateX(${80 * easeIn(k)}deg)`;
        s.style.opacity = String(1 - easeIn(k));
      } else s.style.visibility = 'hidden';
    }
    return true;
  }

  // --- callouts ----------------------------------------------------------------
  const callsEl = document.getElementById('calls');
  const linesEl = document.getElementById('lines');
  const S = L.safe;
  const anchorAt = (id, f) => {
    const a = D.anchors[id];
    if (!a) return null;
    return a[clamp(f, 1, D.N) - 1];
  };
  // Where the point is on frame f: its own place when seen, else the nearest
  // frame it was seen (back first), so a fading callout holds still.
  const posAt = (id, f) => {
    const a = D.anchors[id];
    for (let d = 0; d < D.N; d++) {
      const b = a[clamp(f - d, 1, D.N) - 1];
      if (b[2]) return [b[0], b[1]];
      const n = a[clamp(f + d, 1, D.N) - 1];
      if (n[2]) return [n[0], n[1]];
    }
    return [a[f - 1][0], a[f - 1][1]];
  };
  // Seen-ness over the last 3 frames: a 3-frame fade when the point leaves.
  const visAt = (id, f) => {
    let v = 0;
    for (let d = 0; d < 3; d++) v += anchorAt(id, f - d)?.[2] ? 1 : 0;
    return v / 3;
  };

  const calls = D.callouts.map((c, i) => {
    const o = { ...c, i, kind: c.kind || 'label' };
    const a = D.anchors[c.anchor];
    o.first = null;
    if (a) for (let f = c.f_in; f < c.f_out; f++) if (a[f - 1][2]) { o.first = f; break; }
    o.live = o.first != null;
    if (o.kind === 'money') {
      o.el = $('div', `money abs ${c.tone === 'spend' ? 'spend' : 'earn'}`, callsEl, `<span class="ol">${esc(c.title)}</span><span class="fi">${esc(c.title)}</span>`);
    } else if (o.kind === 'tip') {
      o.el = $('div', 'lab tip abs', callsEl, `<i>!</i><span class="t">${esc(c.title)}</span>${c.sub ? `<span class="s">${esc(c.sub)}</span>` : ''}`);
    } else {
      o.el = $('div', 'lab abs', callsEl, `<div class="t">${esc(c.title)}</div>${c.sub ? `<div class="s">${esc(c.sub)}</div>` : ''}`);
      o.dot = $('div', 'dot abs', callsEl, '<u></u><b></b>');
      o.line = svg('path', { fill: 'none', stroke: '#fff', 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, linesEl);
    }
    o.w = o.el.offsetWidth;
    o.h = o.el.offsetHeight;
    return o;
  });
  // Groups: callouts whose lives overlap (transitively) are laid out together.
  const groups = [];
  for (const c of [...calls].sort((a, b) => a.f_in - b.f_in)) {
    const g = groups.find((x) => c.f_in < x.f_out && c.f_out > x.f_in);
    if (g) { g.m.push(c); g.f_out = Math.max(g.f_out, c.f_out); } else groups.push({ f_in: c.f_in, f_out: c.f_out, m: [c] });
  }
  for (const g of groups) for (const c of g.m) c.g = g;
  // A tip rides under the label of the same anchor.
  for (const c of calls) if (c.kind === 'tip') c.parent = c.g.m.find((x) => x.kind === 'label' && x.anchor === c.anchor);

  const chipBox = { l: CHIP.x, t: CHIP.y, r: CHIP.x + CHIP.w + 24, b: CHIP.y + CHIP.h + 18 };
  const topFor = (l, r) => (l < chipBox.r && r > chipBox.l ? Math.max(S.t, chipBox.b) : S.t);
  // Placement. A label and its tips move as one block; tips sit under the
  // label (over it when the block is above its point).
  const OFF = L.label.off;
  const GAP = 14;
  const RISE = 40;
  const lifeMeet = (a, b) => a.f_in < b.f_out && b.f_in < a.f_out;
  const inter = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x))
    * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  const dotBox = ([x, y]) => ({ x: x - 22, y: y - 22, w: 44, h: 44 });
  for (const c of calls) {
    if (c.kind !== 'label') continue;
    c.tips = calls.filter((t) => t.kind === 'tip' && t.parent === c && t.live);
    c.bw = Math.max(c.w, ...c.tips.map((t) => t.w));
    c.bh = c.h + c.tips.reduce((s, t) => s + 10 + t.h, 0);
  }
  const VSIDE = { up: 1, ul: 1, ur: 1 };
  function sideBox(side, [x, y], c) {
    const w = c.bw;
    const h = c.bh;
    const top = VSIDE[side] ? h - c.h : 0;           // where the label sits inside its block
    switch (side) {
      case 'right': return { x: x + OFF, y: y - RISE - c.h / 2 - top, w, h };
      case 'left': return { x: x - OFF - w, y: y - RISE - c.h / 2 - top, w, h };
      case 'ur': return { x: x + OFF * 0.45, y: y - OFF * 0.8 - h, w, h };
      case 'ul': return { x: x - OFF * 0.45 - w, y: y - OFF * 0.8 - h, w, h };
      case 'up': return { x: x - w / 2, y: y - OFF - h, w, h };
      default: return { x: x - w / 2, y: y + OFF, w, h };
    }
  }
  function clampBox(b) {
    const x = clamp(b.x, S.l, S.r - b.w);
    const y = clamp(b.y, topFor(x, x + b.w), S.b - b.h);
    return { ...b, x, y };
  }
  // Split a block into the label's box and its tips' boxes.
  function split(c, b, box) {
    const up = VSIDE[c.side];
    const lx = (w) => (c.side === 'left' || c.side === 'ul' ? b.x + b.w - w : b.x);
    let y = up ? b.y + b.h - c.h : b.y;
    box.set(c, { x: lx(c.w), y, w: c.w, h: c.h });
    let ty = up ? y : y + c.h;
    for (const t of c.tips) {
      ty = up ? ty - 10 - t.h : ty + 10;
      box.set(t, { x: lx(t.w), y: ty, w: t.w, h: t.h });
      if (!up) ty += t.h;
    }
  }
  const segNear = (p, a, b) => {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const k = clamp(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1));
    return Math.hypot(p[0] - a[0] - k * dx, p[1] - a[1] - k * dy);
  };
  const segHitsBox = (a, b, r) => {
    for (let i = 1; i < 12; i++) {
      const k = i / 12;
      const x = lerp(a[0], b[0], k);
      const y = lerp(a[1], b[1], k);
      if (x > r.x && x < r.x + r.w && y > r.y && y < r.y + r.h) return true;
    }
    return false;
  };

  for (const g of groups) {
    const labs = g.m.filter((c) => c.live && c.kind === 'label');
    if (!labs.length) continue;
    // Column mode: three or more points stacked up (the needs rows) get one
    // aligned column of labels beside them.
    const ref = Math.max(...labs.map((c) => c.first));
    const ps = labs.map((c) => posAt(c.anchor, ref));
    const xs = ps.map((p) => p[0]);
    const ys = ps.map((p) => p[1]);
    g.column = labs.length >= 3 && Math.max(...xs) - Math.min(...xs) < 0.7 * (Math.max(...ys) - Math.min(...ys));
    if (g.column) {
      const maxW = Math.max(...labs.map((c) => c.bw));
      const side = Math.max(...xs) + OFF + maxW <= S.r && (Math.min(...xs) - OFF - maxW < S.l || Math.max(...xs) < W * 0.6) ? 'right' : 'left';
      for (const c of g.m) if (c.live && c.kind !== 'money') c.side = side;
      continue;
    }
    // Scatter mode: each label (in order of arrival) takes the side, chosen
    // once where its point first shows, that keeps it in the frame, off the
    // other points and labels, its leader clear, and pointing outward.
    const chosen = [];
    for (const c of [...labs].sort((a, b) => a.f_in - b.f_in || a.i - b.i)) {
      const fr = c.first;
      const a = posAt(c.anchor, fr);
      const peers = labs.filter((o) => o !== c && lifeMeet(o, c));
      const dots = peers.map((o) => posAt(o.anchor, fr));
      const all = [a, ...dots];
      const cx = all.reduce((s, p) => s + p[0], 0) / all.length;
      const cy = all.reduce((s, p) => s + p[1], 0) / all.length;
      let ox = a[0] - cx;
      let oy = a[1] - cy;
      const on = Math.hypot(ox, oy);
      if (on > 1) { ox /= on; oy /= on; } else { ox = a[0] < W * 0.56 ? 1 : -1; oy = 0; }
      const placed = chosen.filter((o) => lifeMeet(o, c)).map((o) => clampBox(sideBox(o.side, posAt(o.anchor, fr), o)));
      const DIR = { right: [1, -0.3], left: [-1, -0.3], ur: [0.7, -0.7], ul: [-0.7, -0.7], up: [0, -1], down: [0, 1] };
      const BASE = { right: 0, left: 0, ur: 40, ul: 40, up: 70, down: 160 };
      let best = null;
      for (const side of Object.keys(DIR)) {
        const raw = sideBox(side, a, c);
        const b = clampBox(raw);
        const lb = new Map();
        c.side = side;
        split(c, b, lb);
        const pts = leaderGeom(side, a, lb.get(c)).pts;
        let cost = BASE[side] + (Math.abs(b.x - raw.x) + Math.abs(b.y - raw.y)) * 4;
        // Over the rest of its life the point drifts: penalise a side that
        // ends up pinned to the safe edge or sitting on its own point.
        for (let k = 1; k <= 4; k++) {
          const a2 = posAt(c.anchor, Math.round(lerp(fr, c.f_out - 1, k / 4)));
          const r2 = sideBox(side, a2, c);
          const b2 = clampBox(r2);
          cost += (Math.abs(b2.x - r2.x) + Math.abs(b2.y - r2.y)) * 1.5 + inter(b2, dotBox(a2)) * 4;
        }
        const [dx, dy] = DIR[side];
        cost -= 300 * (dx * ox + dy * oy) / Math.hypot(dx, dy);
        for (const d of dots) {
          cost += inter(b, dotBox(d)) * 3;
          for (let i = 1; i < pts.length; i++) if (segNear(d, pts[i - 1], pts[i]) < 26) cost += 3000;
        }
        for (const pb of placed) {
          cost += inter(b, pb) * 3;
          for (let i = 1; i < pts.length; i++) if (segHitsBox(pts[i - 1], pts[i], pb)) cost += 2000;
        }
        if (!best || cost < best.cost) best = { side, cost };
      }
      c.side = best.side;
      chosen.push(c);
    }
  }
  for (const c of calls) if (c.kind === 'tip' && c.parent) c.side = c.parent.side;

  // Lay out one group on frame f. Every live member is placed whether or not
  // it is showing yet, so nothing jumps when the next one arrives.
  function layout(g, f) {
    const box = new Map();
    const P = new Map();
    for (const c of g.m) if (c.live) P.set(c, posAt(c.anchor, f));
    const labs = g.m.filter((c) => c.live && c.kind === 'label').sort((a, b) => a.f_in - b.f_in || a.i - b.i);
    const blocks = new Map();
    if (g.column && labs.length) {
      // One aligned column, in the order of the points, centred on them.
      const side = labs[0].side;
      const col = [...labs].sort((a, b) => posAt(a.anchor, a.first)[1] - posAt(b.anchor, b.first)[1] || a.f_in - b.f_in);
      const pts = col.map((c) => P.get(c));
      const maxW = Math.max(...col.map((c) => c.bw));
      let lx = side === 'right' ? Math.max(...pts.map((p) => p[0])) + OFF : Math.min(...pts.map((p) => p[0])) - OFF - maxW;
      lx = clamp(lx, S.l, S.r - maxW);
      const yc = [];
      let prevBot = -1e9;
      col.forEach((c, j) => {
        const y = Math.max(pts[j][1] - c.h / 2, prevBot + GAP);
        yc.push(y);
        prevBot = y + c.bh;
      });
      const top0 = yc[0];
      const bot0 = prevBot;
      const mid = (Math.min(...pts.map((p) => p[1])) + Math.max(...pts.map((p) => p[1]))) / 2;
      let shift = mid - (top0 + bot0) / 2;
      const top = topFor(lx, lx + maxW);
      if (bot0 + shift > S.b) shift = S.b - bot0;
      if (top0 + shift < top) shift = top - top0;
      col.forEach((c, j) => {
        const b = { x: side === 'right' ? lx : lx + maxW - c.bw, y: yc[j] + shift, w: c.bw, h: c.bh };
        blocks.set(c, b);
        split(c, b, box);
      });
    } else {
      for (const c of labs) {
        let b = clampBox(sideBox(c.side, P.get(c), c));
        // A label clamped against the safe edge can slide over its own point
        // as the point drifts. Ease it above (or below) the point instead,
        // by how far the point has gone in, so it never jumps.
        {
          const [ax, ay] = P.get(c);
          const depth = Math.min(ax - b.x, b.x + b.w - ax) + 14;
          if (depth > 0 && ay > b.y - 14 && ay < b.y + b.h + 14) {
            const upY = ay - 18 - b.h;
            const target = upY >= topFor(b.x, b.x + b.w) ? upY : ay + 18;
            b = clampBox({ ...b, y: lerp(b.y, target, clamp(depth / 30)) });
          }
        }
        const obst = [dotBox(P.get(c))];
        for (const o of labs) {
          if (o === c || !lifeMeet(o, c)) continue;
          obst.push(dotBox(P.get(o)));
          if (blocks.has(o)) obst.push(blocks.get(o));
        }
        // Clear the other points and labels with the smallest move: try the
        // spot itself, then just above, below, left or right of each thing
        // in the way (and of pairs of them), keeping the cleanest, nearest one.
        const hit = (q) => obst.reduce((s2, r) => s2 + inter(q, r), 0);
        if (hit(b) > 0) {
          const b0 = b;
          const cands = [];
          const around = (q) => {
            const out = [];
            for (const r of obst) {
              out.push({ ...q, y: r.y - GAP - q.h }, { ...q, y: r.y + r.h + GAP }, { ...q, x: r.x - GAP - q.w }, { ...q, x: r.x + r.w + GAP });
            }
            return out.map(clampBox);
          };
          for (const q of around(b0)) { cands.push(q); for (const q2 of around(q)) cands.push(q2); }
          let pick = null;
          for (const q of cands) {
            let sc = hit(q) * 1000 + Math.abs(q.x - b0.x) + Math.abs(q.y - b0.y);
            // A leader that crosses another label or point is worse than a longer move.
            const lb = new Map();
            split(c, q, lb);
            const pts = leaderGeom(c.side, P.get(c), lb.get(c)).pts;
            for (const o of labs) {
              if (o === c || !lifeMeet(o, c)) continue;
              const ob = blocks.get(o);
              for (let i = 1; i < pts.length; i++) {
                if (ob && segHitsBox(pts[i - 1], pts[i], ob)) sc += 1500;
                if (segNear(P.get(o), pts[i - 1], pts[i]) < 26) sc += 1500;
              }
            }
            if (!pick || sc < pick.sc) pick = { q, sc };
          }
          b = pick.q;
        }
        blocks.set(c, b);
        split(c, b, box);
      }
    }
    // Money pops off its point on the side away from that point's label,
    // clear of the labels around it.
    for (const c of g.m) {
      if (!c.live || c.kind !== 'money') continue;
      const [px, py] = P.get(c);
      const peer = labs.find((x) => x.anchor === c.anchor && lifeMeet(x, c));
      const toRight = peer ? !['right', 'ur'].includes(peer.side) : px < W / 2;
      let b = clampBox({ x: toRight ? px - 10 : px - c.w + 10, y: py - 40 - c.h, w: c.w, h: c.h });
      for (let it = 0; it < 6; it++) {
        const o = labs.filter((x) => lifeMeet(x, c) && blocks.has(x)).map((x) => blocks.get(x)).find((r) => inter(b, { x: r.x - GAP, y: r.y - GAP, w: r.w + 2 * GAP, h: r.h + 2 * GAP }) > 0);
        if (!o) break;
        b = clampBox({ ...b, y: o.y - GAP - b.h });
      }
      box.set(c, b);
    }
    return { box, P };
  }

  function leaderGeom(side, [ax, ay], b) {
    let p;
    let e;
    let hs = side === 'ur' ? 'right' : side === 'ul' ? 'left' : side;
    // Point sits under or over the label: run the leader vertically.
    if ((hs === 'right' || hs === 'left') && ax > b.x + 10 && ax < b.x + b.w - 10) hs = ay > b.y + b.h / 2 ? 'up' : 'down';
    if (hs === 'right' || hs === 'left') {
      const px = hs === 'right' ? b.x : b.x + b.w;
      const py = clamp(ay, b.y + 18, b.y + b.h - 18);
      const run = Math.min(30, Math.abs(px - ax) * 0.45);
      p = [px - (hs === 'right' ? 6 : -6), py];
      e = [p[0] + (hs === 'right' ? -run : run), py];
    } else {
      const px = clamp(ax, b.x + 24, b.x + b.w - 24);
      const py = hs === 'up' ? b.y + b.h : b.y;
      const run = Math.min(26, Math.abs(py - ay) * 0.45);
      p = [px, py + (hs === 'up' ? -4 : 4)];
      e = [px, p[1] + (hs === 'up' ? run : -run)];
    }
    const pts = [[ax, ay], e, p];
    let len = 0;
    for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    return { pts, d: `M${pts.map((q) => q.map((v) => v.toFixed(1)).join(',')).join('L')}`, len };
  }

  function renderCallouts(f) {
    let any = false;
    for (const c of calls) {
      c.el.classList.add('hide');
      c.dot?.classList.add('hide');
      if (c.line) c.line.style.display = 'none';
    }
    for (const g of groups) {
      if (f < g.f_in || f >= g.f_out) continue;
      const { box, P } = layout(g, f);
      for (const c of g.m) {
        if (!c.live || f < c.f_in || f >= c.f_out) continue;
        const v = visAt(c.anchor, f);
        if (v <= 0) continue;
        const t = f - c.f_in;
        const b = box.get(c);
        const life = c.f_out - c.f_in;
        const ex = clamp((f - (c.f_out - 4) + 1) / 4);
        const alpha = v * (1 - easeIn(ex));
        if (alpha <= 0.001) continue;
        any = true;
        if (c.kind === 'money') {
          const k = t / Math.max(1, life - 1);
          const s = spring(t, 9);
          const rise = 80 * easeOut(k);
          const fade = 1 - easeIn(clamp((k - 0.5) / 0.5));
          c.el.classList.remove('hide');
          c.el.style.opacity = String(clamp((t + 1) / 2) * fade * v);
          c.el.style.transform = `translate(${b.x}px,${b.y - rise + (1 - s) * 40}px) scale(${lerp(0.3, 1, s)}) rotate(${(1 - s) * -10 - 3}deg)`;
          continue;
        }
        if (c.kind === 'tip') {
          const s = spring(t, 9);
          c.el.classList.remove('hide');
          c.el.style.opacity = String(clamp((t + 1) / 2) * alpha);
          c.el.style.transformOrigin = ['left', 'ul'].includes(c.side) ? '100% 0' : '0 0';
          c.el.style.transform = `translate(${b.x}px,${b.y + (1 - s) * -18}px) scale(${lerp(0.6, 1, s)})`;
          continue;
        }
        const a = P.get(c);
        // Point: pops in on a spring; its green ring pulses.
        const sd = spring(t, 6);
        c.dot.classList.remove('hide');
        c.dot.style.opacity = String(alpha);
        c.dot.style.transform = `translate(${a[0]}px,${a[1]}px) scale(${sd})`;
        const ph = ((f - c.f_in) % 30) / 30;
        const ring = c.dot.firstChild;
        ring.style.transform = `scale(${1 + ph * 1.5})`;
        ring.style.opacity = String((1 - ph) * 0.9);
        // Leader draws on over 6 frames from the point.
        const { d, len } = leaderGeom(c.side, a, b);
        const k = easeOut((t - 2) / 6);
        c.line.style.display = '';
        c.line.setAttribute('d', d);
        c.line.setAttribute('stroke-dasharray', `${len} ${len + 10}`);
        c.line.setAttribute('stroke-dashoffset', String(len * (1 - k)));
        c.line.style.opacity = String(alpha);
        // Label springs in at the end of the line.
        const tl = t - 6;
        const s = spring(tl, 9);
        if (tl >= 0) {
          c.el.classList.remove('hide');
          const ox = { right: '0 50%', left: '100% 50%', ur: '0 100%', ul: '100% 100%', up: '50% 100%', down: '50% 0' }[c.side];
          const dx = { right: -24, left: 24, ur: -16, ul: 16, up: 0, down: 0 }[c.side] * (1 - s);
          const dy = { right: 0, left: 0, ur: 16, ul: 16, up: 22, down: -22 }[c.side] * (1 - s);
          c.el.style.transformOrigin = ox;
          c.el.style.opacity = String(clamp((tl + 1) / 2) * alpha);
          c.el.style.transform = `translate(${b.x + dx}px,${b.y + dy}px) scale(${lerp(0.55, 1, s)})`;
        }
      }
    }
    return any;
  }

  window.render = (f) => {
    const a = renderCaptions(f);
    const b = renderChip(f);
    const c = renderCallouts(f);
    return a || b || c;
  };
  window.checker = (on) => document.documentElement.classList.toggle('check', on);
  window.report = () => calls.map((c) => ({ id: c.id, live: c.live, side: c.side || c.kind }));
}

// --- drive it ----------------------------------------------------------------
const browser = await puppeteer.launch({ headless: true, args: ['--use-angle=metal', '--font-render-hinting=none'] });
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await page.setContent(HTML, { waitUntil: 'load' });
// Load the faces before anything is measured.
await page.evaluate(() => Promise.all(['700 64px MZ', 'italic 600 64px ENS', 'italic 400 54px ENR'].map((f) => document.fonts.load(f))));
await page.evaluate(`(${pageMain.toString()})(${JSON.stringify(DATA)})`);
const fontState = await page.evaluate(() => [...document.fonts].map((f) => `${f.family}:${f.status}`));
if (fontState.some((s) => !s.endsWith('loaded'))) throw new Error(`fonts not loaded: ${fontState.join(' ')}`);
const sides = await page.evaluate(() => window.report());
console.log(`overlay ${FMT}: callouts ${sides.map((s) => `${s.id}=${s.live ? s.side : 'off'}`).join(' ')}`);

const pad = (n) => String(n).padStart(4, '0');
const t0 = Date.now();
if (TEST) {
  const dir = path.join(STUDIO, 'reviews', 'overlay-test');
  await mkdir(dir, { recursive: true });
  for (const fr of TEST) {
    await page.evaluate((f) => window.render(f), fr);
    await page.evaluate(() => window.checker(false));
    await page.screenshot({ path: path.join(dir, `${FMT}-${pad(fr)}.png`), omitBackground: true });
    await page.evaluate(() => window.checker(true));
    await page.screenshot({ path: path.join(dir, `${FMT}-${pad(fr)}-check.png`) });
    await page.evaluate(() => window.checker(false));
  }
  console.log(`overlay ${FMT}: ${TEST.length} test frames -> ${path.relative(STUDIO, dir)}/ in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
} else {
  const dir = path.join(STUDIO, 'cache', `overlay-${FMT}`);
  await mkdir(dir, { recursive: true });
  const blank = path.join(dir, '_blank.png');
  await page.evaluate(() => window.render(-100));
  await page.screenshot({ path: blank, omitBackground: true });
  let drawn = 0;
  for (let fr = FROM; fr <= TO; fr++) {
    const file = path.join(dir, `${pad(fr)}.png`);
    await rm(file, { force: true });
    const any = await page.evaluate((f) => window.render(f), fr);
    if (!any) { await link(blank, file); continue; }
    await page.screenshot({ path: file, omitBackground: true });
    drawn++;
    if (drawn % 100 === 0) console.log(`  ${fr}/${TO}  ${((Date.now() - t0) / drawn).toFixed(0)} ms/frame`);
  }
  const secs = (Date.now() - t0) / 1000;
  console.log(`overlay ${FMT}: frames ${FROM}-${TO} (${drawn} drawn, ${TO - FROM + 1 - drawn} blank) -> ${path.relative(STUDIO, dir)}/ in ${secs.toFixed(1)} s`
    + ` (${drawn ? ((secs * 1000) / drawn).toFixed(0) : 0} ms per drawn frame)${A.fake ? '  [FAKE ANCHORS]' : ''}`);
}
await browser.close();
