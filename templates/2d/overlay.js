// The overlay over a Blender film: captions, the lesson chip, and callouts
// (label / tip / money) pinned to the projected 3D anchors. The look is all
// STYLE (fonts, colours, treatment, entry / exit, eases), read through
// studio.js; this file owns only behaviour: where things go and when. Every
// frame is laid out from f alone, so frame 150 alone equals frame 150 in a run.
//
//   node src/render2d.mjs src/overlay.html [--format=9x16] [--test=60,95] [--fake] [--style=look.json]
//
// Class names a preset's CSS can target: .ms-chip .ms-slot .ms-num .ms-ttl
// .ms-lab .ms-tip .t .s .ms-dot .ms-ring .ms-leader .ms-money
import { clamp, lerp, tween, esc, applyPose, drawPath } from './motion.js';
import { boot, stack, boxCSS } from './studio.js';
import { captions } from './captions.js';

const S = await boot();
const { T } = S;
const st = S.style;
const cs = st.caption;
const E = st.enter;
const X = st.exit;
const CO = st.callout;
const W = S.w;
const H = S.h;
const N = T.FRAMES;

const $ = (tag, cls, parent, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  parent?.append(n);
  return n;
};
const svg = (tag, attrs, parent) => {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  parent?.append(n);
  return n;
};
const show = (n, on) => { n.style.display = on ? '' : 'none'; };
const pad = Array.isArray(cs.pad) ? cs.pad : [cs.pad, cs.pad * 2];
const PADY = S.u(pad[0]);
const PADX = S.u(pad[1]);
const GAP = Math.max(6, S.u(CO.gap));
const shadow = cs.shadow ? `0 .04em .12em rgba(0,0,0,${0.6 * cs.shadow}),0 0 .6em rgba(0,0,0,${0.45 * cs.shadow})` : 'none';

// --- captions -------------------------------------------------------------------
const drawCaptions = captions(document.getElementById('caps'), S);

// --- lesson chip ------------------------------------------------------------------
// Chapter number in the display face (accent colour) and the title in the body
// face, behind the same treatment as the captions. Chapters back to back share
// one chip; the title swaps with STYLE.exit / STYLE.enter.
const chipWrap = document.getElementById('chipwrap');
const chip = document.getElementById('chip');
chip.className = 'ms-chip';
const CHK = st.chip.style || (cs.style === 'none' ? 'plain' : cs.style);
const CHS = st.chip.size ?? st.type.body.size;
const CHIP = { x: st.chip.x != null ? S.u(st.chip.x) : S.safe.l, y: st.chip.y != null ? S.u(st.chip.y) : S.safe.t, w: 0, h: 0 };
const chapters = (T.CHAPTERS || []).map((c, i) => {
  const slot = $('div', 'ms-slot', chip, `<span class="ms-num">${esc(c.n)}</span><span class="ms-ttl">${esc(c.title)}</span>`);
  Object.assign(slot.style, { position: 'absolute', left: '0', top: '0', display: 'flex', alignItems: 'center', gap: `${(S.u(CHS) * 0.5).toFixed(1)}px`,
    padding: `${PADY}px ${PADX}px`, whiteSpace: 'nowrap', color: st.ink, textShadow: CHK === 'plain' ? shadow : 'none' });
  Object.assign(slot.firstChild.style, S.type('display', { size: CHS * 1.4, line: 1 }), { color: st.accent });
  Object.assign(slot.lastChild.style, S.type('body', { size: CHS, line: 1.1 }));
  return { ...c, i, slot };
});
for (const c of chapters) { c.w = c.slot.offsetWidth; c.h = c.slot.offsetHeight; }
if (chapters.length) {
  CHIP.w = Math.max(...chapters.map((c) => c.w));
  CHIP.h = Math.max(...chapters.map((c) => c.h));
  Object.assign(chip.style, { position: 'absolute', left: `${CHIP.x}px`, top: `${CHIP.y}px`, height: `${CHIP.h}px`, overflow: 'hidden' });
  for (const c of chapters) c.slot.style.height = `${CHIP.h}px`;
  if (CHK === 'underline') chip.style.borderBottom = `${Math.max(1, S.u(cs.rule)).toFixed(1)}px solid ${st.accent}`;
  else Object.assign(chip.style, boxCSS(S, CHK, { h: CHIP.h, radius: cs.radius || null }) || {});
}
const runs = [];
for (const c of chapters) {
  const r = runs[runs.length - 1];
  if (r && c.f_in <= r.f_out) { r.m.push(c); r.f_out = Math.max(r.f_out, c.f_out); } else runs.push({ f_in: c.f_in, f_out: c.f_out, m: [c] });
}

function drawChip(f) {
  const run = runs.find((r) => f >= r.f_in && f < r.f_out);
  show(chipWrap, !!run);
  if (!run) return false;
  const k = run.m.findIndex((c) => f >= c.f_in && f < c.f_out);
  const ci = k < 0 ? run.m.length - 1 : k;
  const c = run.m[ci];
  const prev = run.m[ci - 1];
  const box = { w: CHIP.w, h: CHIP.h };
  const xf = X.frames || 0;
  const kx = xf && f >= run.f_out - xf ? tween(f - (run.f_out - xf), { frames: xf, ease: X.ease }) : 0;
  applyPose(chip, stack(S.enter(tween(f - run.f_in, E), box, { by: 'block' }), S.exit(kx, box)));
  // The chip's width moves from one title to the next (STYLE.move).
  const sw = prev ? S.moveEase(clamp((f - c.f_in) / Math.max(1, E.frames))) : 1;
  chip.style.width = `${prev ? lerp(prev.w, c.w, sw) : c.w}px`;
  for (const ch of chapters) {
    if (ch === c) {
      const t = prev ? f - c.f_in - Math.round(xf / 2) : 1e3;
      const p = S.enter(t < 0 ? 0 : tween(t, E), ch);
      if (t < 0) p.hidden = true;
      applyPose(ch.slot, p);
    } else if (ch === prev && f - c.f_in < xf) {
      applyPose(ch.slot, S.exit(tween(f - c.f_in + 1, { frames: xf, ease: X.ease }), ch));
    } else ch.slot.style.visibility = 'hidden';
  }
  return true;
}

// --- callout looks ----------------------------------------------------------------
// Labels: title in the display face at body size, sub in the body face;
// behind them callout.style (default: the caption treatment, or a box when
// captions are plain, so a label stays legible over the footage).
const CK = CO.style || (['plain', 'none'].includes(cs.style) ? 'box' : cs.style);
const TITLE_PX = S.u(st.type.body.size);
const MAXL = CO.max?.[S.fmt] ?? (S.tall ? 2 : 4);
const callsEl = document.getElementById('calls');
const linesEl = document.getElementById('lines');
linesEl.setAttribute('width', W);
linesEl.setAttribute('height', H);
const textT = () => ({ ...S.type('display', { size: st.type.body.size, line: 1.1 }), color: st.ink });
const textS = (m = 0.78) => ({ ...S.type('body', { size: st.type.body.size * m, line: 1.2 }), color: st.ink });
function labelEl(c) {
  const n = $('div', 'ms-lab', callsEl, `<div class="t">${esc(c.title)}</div>${c.sub ? `<div class="s">${esc(c.sub)}</div>` : ''}`);
  n.style.padding = `${PADY}px ${PADX}px`;
  n.style.whiteSpace = 'nowrap';
  Object.assign(n.querySelector('.t').style, textT());
  if (c.sub) Object.assign(n.querySelector('.s').style, textS(), { opacity: '0.72', marginTop: `${(TITLE_PX * 0.18).toFixed(1)}px` });
  return n;
}
function tipEl(c) {
  const n = $('div', 'ms-lab ms-tip', callsEl, `<span class="t">${esc(c.title)}</span>${c.sub ? `<span class="s">${esc(c.sub)}</span>` : ''}`);
  Object.assign(n.style, { padding: `${PADY * 0.8}px ${PADX * 0.8}px`, whiteSpace: 'nowrap', display: 'flex', alignItems: 'baseline', gap: `${(TITLE_PX * 0.4).toFixed(1)}px` });
  Object.assign(n.querySelector('.t').style, textS());
  if (c.sub) Object.assign(n.querySelector('.s').style, textS(0.7), { color: st.accent });
  return n;
}
function moneyEl(c) {
  const n = $('div', `ms-money ${c.tone === 'spend' ? 'spend' : 'earn'}`, callsEl, esc(c.title));
  Object.assign(n.style, S.type('display', { line: 1 }), {
    whiteSpace: 'nowrap', transformOrigin: '50% 100%', textShadow: shadow,
    color: c.tone === 'spend' ? CO.spend || st.palette[0] || st.ink : st.accent,
  });
  return n;
}
function dress(n, h) {
  if (CK === 'underline') n.style.borderBottom = `${Math.max(1, S.u(cs.rule)).toFixed(1)}px solid ${st.accent}`;
  else if (CK === 'plain') n.style.textShadow = shadow;
  else Object.assign(n.style, boxCSS(S, CK, { h, radius: cs.radius || null }) || {});
}
function dotEl() {
  const n = $('div', 'ms-dot', callsEl, '<u class="ms-ring"></u><b></b>');
  const r = Math.max(3, S.u(CO.dot));
  n.style.cssText = 'width:0;height:0';
  n.lastChild.style.cssText = `position:absolute;left:${-r}px;top:${-r}px;width:${2 * r}px;height:${2 * r}px;border-radius:50%;background:${st.accent}`;
  n.firstChild.style.cssText = `position:absolute;left:${-r * 1.8}px;top:${-r * 1.8}px;width:${3.6 * r}px;height:${3.6 * r}px;border-radius:50%;box-sizing:border-box;border:${Math.max(1, r * 0.35).toFixed(1)}px solid ${st.accent};opacity:0`;
  return n;
}
// Callouts keep clear of the safe margins, the chip and the caption band.
const capTop = drawCaptions.cards?.length ? Math.min(...drawCaptions.cards.map((c) => c.box.t)) : S.safe.b;
const SF = { ...S.safe, b: Math.min(S.safe.b, capTop - GAP) };

// --- callout placement ------------------------------------------------------------
const A = S.anchors;
const anchorAt = (id, f) => A[id][clamp(f, 1, N) - 1];
// Where the point is on frame f: its own place when seen, else the nearest
// frame it was seen (back first), so a fading callout holds still.
const posAt = (id, f) => {
  const a = A[id];
  for (let d = 0; d < N; d++) {
    const b = a[clamp(f - d, 1, N) - 1];
    if (b[2]) return [b[0], b[1]];
    const n = a[clamp(f + d, 1, N) - 1];
    if (n[2]) return [n[0], n[1]];
  }
  const z = a[clamp(f, 1, N) - 1];
  return [z[0], z[1]];
};
// Seen-ness over the last 3 frames: a 3-frame fade when the point leaves the
// shot, instead of a label pointing at nothing.
const visAt = (id, f) => {
  let v = 0;
  for (let d = 0; d < 3; d++) v += anchorAt(id, f - d)[2] ? 1 : 0;
  return v / 3;
};

const missing = new Set();
const calls = (T.CALLOUTS || []).map((c, i) => {
  const o = { ...c, i, kind: c.kind || 'label' };
  if (!A[c.anchor]) missing.add(c.anchor);
  o.first = null;
  if (A[c.anchor]) for (let f = c.f_in; f < c.f_out; f++) if (anchorAt(c.anchor, f)[2]) { o.first = f; break; }
  o.live = o.first != null;
  o.el = (o.kind === 'money' ? moneyEl : o.kind === 'tip' ? tipEl : labelEl)(c);
  o.w = o.el.offsetWidth;
  o.h = o.el.offsetHeight;
  if (o.kind !== 'money') dress(o.el, o.h);
  return o;
});
// A tip rides under the label of the same anchor; a tip with no label of its
// own is pinned like a label (dot + leader) and placed the same way.
for (const c of calls) {
  if (c.kind !== 'tip') continue;
  c.parent = calls.find((x) => x.kind === 'label' && x.anchor === c.anchor && x.f_in < c.f_out && c.f_in < x.f_out) || null;
  c.pinned = !c.parent;
}
for (const c of calls) {
  if (c.kind === 'label') c.pinned = true;
  if (!c.pinned) continue;
  c.dot = dotEl();
  c.line = svg('path', { class: 'ms-leader', fill: 'none', stroke: st.ink, 'stroke-width': Math.max(1, S.u(CO.line)).toFixed(2), 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, linesEl);
}
// 9:16 holds fewer labels at once: when one more arrives than the format
// allows, the oldest leaves as it arrives (its tips go with it).
const OUT = Math.max(1, X.frames || 4);
{
  const pins = calls.filter((c) => c.pinned && c.live).sort((a, b) => a.f_in - b.f_in || a.i - b.i);
  for (const c of pins) {
    const before = pins.filter((o) => o !== c && o.f_in <= c.f_in && o.f_out > c.f_in && (o.f_in < c.f_in || o.i < c.i));
    if (before.length >= MAXL) {
      for (const o of before.slice(0, before.length - MAXL + 1)) o.f_out = Math.min(o.f_out, c.f_in + OUT);
    }
  }
  for (const c of calls) if (c.parent) c.f_out = Math.min(c.f_out, c.parent.f_out);
}
// Groups: callouts whose lives overlap (transitively) are laid out together.
const groups = [];
for (const c of [...calls].sort((a, b) => a.f_in - b.f_in)) {
  const g = groups.find((x) => c.f_in < x.f_out && c.f_out > x.f_in);
  if (g) { g.m.push(c); g.f_out = Math.max(g.f_out, c.f_out); } else groups.push({ f_in: c.f_in, f_out: c.f_out, m: [c] });
}
for (const g of groups) for (const c of g.m) c.g = g;

const chipBox = { l: CHIP.x, t: CHIP.y, r: CHIP.x + CHIP.w + 24, b: CHIP.y + CHIP.h + 18 };
const topFor = (l, r) => (chapters.length && l < chipBox.r && r > chipBox.l ? Math.max(SF.t, chipBox.b) : SF.t);
// Placement. A label and its tips move as one block; tips sit under the
// label (over it when the block is above its point).
const OFF = S.u(CO.off);
const RISE = Math.round(TITLE_PX * 1.33);
const DOT = Math.max(12, Math.round(TITLE_PX * 0.73));
const lifeMeet = (a, b) => a.f_in < b.f_out && b.f_in < a.f_out;
const inter = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x))
  * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
const dotBox = ([x, y]) => ({ x: x - DOT, y: y - DOT, w: DOT * 2, h: DOT * 2 });
const pinsOf = (g) => g.m.filter((c) => c.live && c.pinned);
for (const c of calls) {
  if (!c.pinned) continue;
  c.tips = calls.filter((t) => t.parent === c && t.live);
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
  const x = clamp(b.x, SF.l, SF.r - b.w);
  const y = clamp(b.y, topFor(x, x + b.w), SF.b - b.h);
  return { ...b, x, y };
}
// Split a block into the label's box and its tips' boxes.
function split(c, b, box) {
  const up = VSIDE[c.side];
  const lx = (w) => (c.side === 'left' || c.side === 'ul' ? b.x + b.w - w : b.x);
  const y = up ? b.y + b.h - c.h : b.y;
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

// Choose each label's side once, from the data alone.
for (const g of groups) {
  const labs = pinsOf(g);
  if (!labs.length) continue;
  // Column mode: three or more points stacked up get one aligned column of
  // labels beside them.
  const ref = Math.max(...labs.map((c) => c.first));
  const ps = labs.map((c) => posAt(c.anchor, ref));
  const xs = ps.map((p) => p[0]);
  const ys = ps.map((p) => p[1]);
  g.column = labs.length >= 3 && Math.max(...xs) - Math.min(...xs) < 0.7 * (Math.max(...ys) - Math.min(...ys));
  if (g.column) {
    const maxW = Math.max(...labs.map((c) => c.bw));
    const side = Math.max(...xs) + OFF + maxW <= SF.r && (Math.min(...xs) - OFF - maxW < SF.l || Math.max(...xs) < W * 0.6) ? 'right' : 'left';
    for (const c of labs) c.side = side;
    continue;
  }
  // Scatter mode: each label (in order of arrival) takes the side, chosen
  // where its point first shows, that keeps it in the frame, off the other
  // points and labels, its leader clear, and pointing outward.
  const chosen = [];
  const DIR = { right: [1, -0.3], left: [-1, -0.3], ur: [0.7, -0.7], ul: [-0.7, -0.7], up: [0, -1], down: [0, 1] };
  const BASE = { right: 0, left: 0, ur: 40, ul: 40, up: 70, down: 160 };
  for (const c of [...labs].sort((a, b) => a.f_in - b.f_in || a.i - b.i)) {
    const fr = c.first;
    const a = posAt(c.anchor, fr);
    const dots = labs.filter((o) => o !== c && lifeMeet(o, c)).map((o) => posAt(o.anchor, fr));
    const all = [a, ...dots];
    const cx = all.reduce((s, p) => s + p[0], 0) / all.length;
    const cy = all.reduce((s, p) => s + p[1], 0) / all.length;
    let ox = a[0] - cx;
    let oy = a[1] - cy;
    const on = Math.hypot(ox, oy);
    if (on > 1) { ox /= on; oy /= on; } else { ox = a[0] < W * 0.56 ? 1 : -1; oy = 0; }
    const placed = chosen.filter((o) => lifeMeet(o, c)).map((o) => clampBox(sideBox(o.side, posAt(o.anchor, fr), o)));
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
for (const c of calls) if (c.parent) c.side = c.parent.side;

// Lay out one group on frame f. Every live member is placed whether or not it
// is showing yet, so nothing jumps when the next one arrives.
function layout(g, f) {
  const box = new Map();
  const P = new Map();
  for (const c of g.m) if (c.live) P.set(c, posAt(c.anchor, f));
  const labs = pinsOf(g).sort((a, b) => a.f_in - b.f_in || a.i - b.i);
  const blocks = new Map();
  if (g.column) {
    // One aligned column, in the order of the points, centred on them.
    const side = labs[0].side;
    const col = [...labs].sort((a, b) => posAt(a.anchor, a.first)[1] - posAt(b.anchor, b.first)[1] || a.f_in - b.f_in);
    const pts = col.map((c) => P.get(c));
    const maxW = Math.max(...col.map((c) => c.bw));
    let lx = side === 'right' ? Math.max(...pts.map((p) => p[0])) + OFF : Math.min(...pts.map((p) => p[0])) - OFF - maxW;
    lx = clamp(lx, SF.l, SF.r - maxW);
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
    if (bot0 + shift > SF.b) shift = SF.b - bot0;
    if (top0 + shift < top) shift = top - top0;
    col.forEach((c, j) => {
      const b = { x: side === 'right' ? lx : lx + maxW - c.bw, y: yc[j] + shift, w: c.bw, h: c.bh };
      blocks.set(c, b);
      split(c, b, box);
    });
  } else {
    for (const c of labs) {
      let b = clampBox(sideBox(c.side, P.get(c), c));
      // A label clamped against the safe edge can slide over its own point as
      // the point drifts. Ease it above (or below) the point instead, by how
      // far the point has gone in, so it never jumps.
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
      // Clear the other points and labels with the smallest move: the spot
      // itself, then just above, below, left or right of each thing in the
      // way (and of pairs of them), keeping the cleanest, nearest one.
      const hit = (q) => obst.reduce((s2, r) => s2 + inter(q, r), 0);
      if (hit(b) > 0) {
        const b0 = b;
        const cands = [];
        const around = (q) => {
          const out = [];
          for (const r of obst) out.push({ ...q, y: r.y - GAP - q.h }, { ...q, y: r.y + r.h + GAP }, { ...q, x: r.x - GAP - q.w }, { ...q, x: r.x + r.w + GAP });
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
  // Money pops off its point on the side away from that point's label, clear
  // of the labels around it.
  for (const c of g.m) {
    if (!c.live || c.kind !== 'money') continue;
    const [px, py] = P.get(c);
    const peer = labs.find((x) => x.anchor === c.anchor && lifeMeet(x, c));
    const toRight = peer ? !['right', 'ur'].includes(peer.side) : px < W / 2;
    let b = clampBox({ x: toRight ? px - 10 : px - c.w + 10, y: py - 40 - c.h, w: c.w, h: c.h });
    for (let it = 0; it < 6; it++) {
      const o = labs.filter((x) => lifeMeet(x, c) && blocks.has(x)).map((x) => blocks.get(x))
        .find((r) => inter(b, { x: r.x - GAP, y: r.y - GAP, w: r.w + 2 * GAP, h: r.h + 2 * GAP }) > 0);
      if (!o) break;
      b = clampBox({ ...b, y: o.y - GAP - b.h });
    }
    box.set(c, b);
  }
  return { box, P };
}

function drawCallouts(f) {
  let any = false;
  for (const c of calls) {
    show(c.el, false);
    if (c.dot) show(c.dot, false);
    if (c.line) c.line.style.display = 'none';
  }
  const LF = Math.max(3, E.frames || 6);     // leader draw-on, frames
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
      const ex = f >= c.f_out - OUT ? tween(f - (c.f_out - OUT) + 1, { frames: OUT, ease: X.ease }) : 0;
      if (ex >= 1) continue;
      any = true;
      const out = S.exit(ex, c);
      if (c.kind === 'money') {
        // Arrives with STYLE.enter, rises off its point (STYLE.move) and fades
        // over the second half of its life.
        const k = t / Math.max(1, life - 1);
        const rise = c.h * 0.9 * S.moveEase(k);
        const fade = 1 - S.ease(X.ease)(clamp((k - 0.5) / 0.5));
        const p = stack(S.enter(tween(t, E), c, { by: 'block' }), out);
        show(c.el, true);
        applyPose(c.el, { ...p, opacity: p.opacity * fade * v }, `translate(${b.x}px,${b.y - rise}px)`);
        continue;
      }
      if (!c.pinned) {
        const p = stack(S.enter(tween(t, E), c), out);
        show(c.el, true);
        applyPose(c.el, { ...p, opacity: p.opacity * v }, `translate(${b.x}px,${b.y}px)`);
        continue;
      }
      const a = P.get(c);
      const alpha = v * (1 - ex);
      // The point lands (STYLE.move, with its overshoot), then the leader
      // draws out from it, then the label arrives at the end of the leader.
      const sd = S.moveEase(clamp(t / Math.max(2, LF * 0.6)));
      show(c.dot, true);
      c.dot.style.opacity = String(alpha);
      c.dot.style.transform = `translate(${a[0]}px,${a[1]}px) scale(${sd.toFixed(4)})`;
      if (CO.pulse) {
        const ph = ((f - c.f_in) % CO.pulse) / CO.pulse;
        c.dot.firstChild.style.transform = `scale(${(0.6 + ph).toFixed(3)})`;
        c.dot.firstChild.style.opacity = String((1 - ph) * 0.9);
      }
      const { d } = leaderGeom(c.side, a, b);
      c.line.style.display = '';
      c.line.setAttribute('d', d);
      drawPath(c.line, S.moveEase(clamp((t - 1) / LF)));
      c.line.style.opacity = String(alpha);
      const tl = t - Math.round(LF * 0.6);
      if (tl >= 0) {
        const p = stack(S.enter(tween(tl, E), c), out);
        show(c.el, true);
        applyPose(c.el, { ...p, opacity: p.opacity * v }, `translate(${b.x}px,${b.y}px)`);
      }
    }
  }
  return any;
}

// --- the contract ---------------------------------------------------------------------
window.renderFrame = (f) => {
  const a = drawCaptions(f);
  const b = drawChip(f);
  const c = drawCallouts(f);
  return a || b || c;
};
// Frame ranges where a pinned callout's point sits under a caption: the
// point is hidden by the words, so move the callout or the caption.
function underCaptions() {
  const out = [];
  for (const c of calls) {
    if (!c.pinned || !c.live || !A[c.anchor]) continue;
    let run = null;
    for (let f = c.f_in; f <= c.f_out; f++) {
      const p = f < c.f_out ? anchorAt(c.anchor, f) : null;
      const hit = p && p[2] && drawCaptions.boxes(f).some((q) => p[0] > q.l && p[0] < q.r && p[1] > q.t && p[1] < q.b);
      if (hit && !run) run = [f, f];
      else if (hit) run[1] = f;
      else if (run) { out.push(`${c.id} f${run[0]}-${run[1]}`); run = null; }
    }
  }
  return out;
}
// Lines for the driver's log: the look in use and where each callout went.
window.renderReport = () => [
  `look: captions ${cs.style}, enter ${E.kind} by ${E.by}, exit ${X.kind}${st.preset ? `, preset ${st.preset}` : ''}`,
  `callouts ${calls.map((c) => `${c.id}=${c.live ? c.side || c.kind : 'off'}`).join(' ') || 'none'}`,
  ...(missing.size ? [`no anchor data for: ${[...missing].join(', ')} (their callouts never show)`] : []),
  ...((u) => (u.length ? [`WARNING callout point under a caption: ${u.join(', ')}`] : []))(underCaptions()),
  ...drawCaptions.report(),
];
