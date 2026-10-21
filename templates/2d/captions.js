// Captions drawn entirely from STYLE: the type role, the treatment behind the
// words (STYLE.caption.style: plain | pill | box | underline | none), and the
// entry / exit (STYLE.enter, STYLE.exit). Each CAPTIONS card holds fragments
// that arrive when they are said; *stars* mark accent words. Shared by
// overlay.html and any 2D film.
//
//   import { captions } from './captions.js';
//   const drawCaptions = captions(document.getElementById('caps'), S);
//   drawCaptions(f)        // -> true when a card is on screen
//   drawCaptions.boxes(f)  // settled screen boxes of the cards on f (overlap checks)
//   drawCaptions.report()  // lines for renderReport (holds shorter than STYLE.hold_min_s)
//
// Class names a preset's CSS can target: .ms-card .ms-unit .w .w.acc .c .ms-bg
import { clamp, lerp, tween, accents, applyPose } from './motion.js';
import { stack, boxCSS } from './studio.js';

const el = (tag, cls, parent) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  parent?.append(n);
  return n;
};

export function captions(root, S, list = S.T.CAPTIONS || []) {
  const st = S.style;
  const cs = st.caption;
  const E = st.enter;
  const X = st.exit;
  const draw = (f) => drawAll(f);
  if (cs.style === 'none' || !list.length) {
    draw.boxes = () => [];
    draw.report = () => [];
    return Object.assign(() => false, { boxes: draw.boxes, report: draw.report });
  }
  root.style.cssText = 'position:absolute;left:0;top:0;width:0;height:0';
  const by = E.kind === 'type' ? 'char' : E.by || 'line';
  const role = { ...(st.type[cs.type] || st.type.body) };
  if (cs.size) role.size = cs.size;
  const textCSS = S.type(cs.type, role);
  const maxW = Math.min(S.u(cs.max_w), S.w - 2 * S.u(st.safe));
  const pad = Array.isArray(cs.pad) ? cs.pad : [cs.pad, cs.pad * 2];  // [y, x]
  const padY = S.u(pad[0]);
  const padX = S.u(pad[1]);
  const acc = st.type.accent || {};
  const accCSS = {
    color: acc.color || st.accent,
    ...(acc.font ? { fontFamily: S.family(acc.font) } : {}),
    ...(acc.weight ? { fontWeight: String(acc.weight) } : {}),
    ...(acc.style ? { fontStyle: acc.style } : {}),
    ...(acc.scale ? { fontSize: `${acc.scale}em` } : {}),
  };
  const shadow = cs.shadow ? `0 .04em .12em rgba(0,0,0,${0.6 * cs.shadow}),0 0 .6em rgba(0,0,0,${0.45 * cs.shadow})` : 'none';
  const hook = S.hooks.caption || {};

  const cards = list.map((c, ci) => {
    const node = el('div', 'ms-card', root);
    Object.assign(node.style, textCSS, {
      position: 'absolute', left: '0', top: '0', width: `${maxW}px`, textAlign: cs.align,
      color: cs.color || st.ink, textShadow: shadow, textWrap: 'balance',
    });
    const words = [];
    c.parts.forEach((p, pi) => {
      for (const s of accents(p.text)) {
        for (const tok of s.text.split(/(\s+)/)) {
          if (!tok) continue;
          if (/^\s+$/.test(tok)) { node.append(document.createTextNode(' ')); continue; }
          const w = el('span', s.accent ? 'w acc' : 'w', node);
          w.style.display = 'inline-block';
          if (s.accent) Object.assign(w.style, accCSS);
          if (by === 'char') for (const ch of tok) { const cc = el('span', 'c', w); cc.style.display = 'inline-block'; cc.textContent = ch; } else w.textContent = tok;
          words.push({ el: w, pi, accent: s.accent });
        }
      }
      if (pi < c.parts.length - 1 && !/\s$/.test(p.text)) node.append(document.createTextNode(' '));
    });
    return { ...c, ci, el: node, words };
  });

  // Measure once (fonts are loaded): lines, then the units that move.
  for (const c of cards) {
    const lines = [];
    // Same line = vertical centres within half a line: an accent word in a
    // bigger face sits higher than its neighbours but on the same line.
    const half = (parseFloat(textCSS.fontSize) * (role.line || 1.2)) / 2;
    for (const w of c.words) {
      w.y = w.el.offsetTop + w.el.offsetHeight / 2;
      let ln = lines.find((l) => Math.abs(l.y - w.y) < half);
      if (!ln) lines.push((ln = { y: w.y, words: [] }));
      ln.words.push(w);
    }
    // A segment is a run of one fragment's words on one line: the unit for
    // by 'line' and 'block'. Wrapped in one inline-block so it moves whole.
    if (by === 'line' || by === 'block') {
      for (const ln of lines) {
        let seg = null;
        for (const w of ln.words) {
          if (!seg || seg.pi !== w.pi) {
            seg = { pi: w.pi, words: [w], el: el('span', 'ms-unit') };
            seg.el.style.cssText = 'display:inline-block;white-space:pre';
            w.el.before(seg.el);
            (ln.segs ||= []).push(seg);
          } else seg.words.push(w);
          // move the word and the space before it into the segment
          if (seg.words.length > 1) { const sp = w.el.previousSibling; if (sp?.nodeType === 3) seg.el.append(sp); }
          seg.el.append(w.el);
        }
      }
    }
    const units = [];
    const count = {};
    const add = (u, pi, line) => {
      const n = (count[pi] = (count[pi] ?? -1) + 1);
      const p = c.parts[pi];
      u.t0 = p.f + (by === 'block' ? 0 : n * (E.stagger || 0));
      u.line = line;
      units.push(u);
    };
    lines.forEach((ln, li) => {
      if (by === 'line' || by === 'block') for (const s of ln.segs) add({ el: s.el }, s.pi, li);
      else if (by === 'char') for (const w of ln.words) for (const ch of w.el.children) add({ el: ch, word: w }, w.pi, li);
      else for (const w of ln.words) add({ el: w.el, word: w }, w.pi, li);
    });
    for (const u of units) {
      u.x = u.el.offsetLeft + (u.el.offsetParent === c.el ? 0 : u.el.offsetParent.offsetLeft);
      u.y = u.el.offsetTop + (u.el.offsetParent === c.el ? 0 : u.el.offsetParent.offsetTop);
      u.w = u.el.offsetWidth;
      u.h = u.el.offsetHeight;
    }
    c.units = units;
    c.lines = lines.map((ln, li) => {
      const us = units.filter((u) => u.line === li);
      return { us, top: Math.min(...us.map((u) => u.y)), bot: Math.max(...us.map((u) => u.y + u.h)) };
    });
    const h = c.el.offsetHeight;
    // Anchored by its bottom edge at caption.y: a second line grows upwards.
    c.top = S.u(cs.y) - h;
    c.left = cs.align === 'left' ? S.safe.l : cs.align === 'right' ? S.safe.r - maxW : (S.w - maxW) / 2;
    const xs = units.map((u) => u.x);
    const xe = units.map((u) => u.x + u.w);
    c.box = { l: c.left + Math.min(...xs) - padX, r: c.left + Math.max(...xe) + padX, t: c.top + c.lines[0].top - padY, b: c.top + c.lines[c.lines.length - 1].bot + padY };
    // The treatment behind the words: one per line (pill, underline) or one
    // for the card (box).
    const kind = cs.style;
    const perLine = kind === 'pill' || kind === 'underline';
    c.bgs = (kind === 'box' ? [null] : perLine ? c.lines : []).map(() => {
      const b = el('div', `ms-bg ms-${kind}`);
      b.style.cssText = 'position:absolute;left:0;top:0;z-index:0';
      c.el.prepend(b);
      return b;
    });
    for (const u of units) { u.el.style.position = 'relative'; u.el.style.zIndex = '1'; }
    // A preset may decorate accent words (hooks.caption.accent returns an
    // updater called each frame with the frames since that word arrived).
    c.accentHooks = hook.accent ? c.words.filter((w) => w.accent).map((w) => ({
      t0: units.find((u) => u.el === w.el || u.el.contains(w.el) || w.el.contains(u.el)).t0,
      upd: hook.accent(w.el, { S, card: c.ci, seed: c.ci * 1.7 + w.pi }),
    })) : [];
    c.hold = (c.f_out - c.parts[c.parts.length - 1].f) / S.time.FPS;
    c.el.style.display = 'none';
  }

  // Revealed extent of a line on frame f: from its first unit to the right
  // edge of the newest one, eased along with that unit's entry.
  function extent(units, f) {
    const shown = units.filter((u) => f >= u.t0);
    if (!shown.length) return null;
    const last = shown[shown.length - 1];
    const k = clamp(tween(f - last.t0, E));
    const l = Math.min(...shown.map((u) => u.x));
    const prevR = shown.length > 1 ? Math.max(...shown.slice(0, -1).map((u) => u.x + u.w)) : last.x + last.w * 0.15;
    return { l, r: lerp(prevR, last.x + last.w, k), a: clamp(tween(f - shown[0].t0, E)) };
  }

  function drawAll(f) {
    let any = false;
    for (const c of cards) {
      const on = f >= c.f_in && f < c.f_out;
      c.el.style.display = on ? '' : 'none';
      if (!on) continue;
      any = true;
      // The card leaves as one block over the last exit.frames frames.
      const xf = Math.max(0, Math.min(X.frames || 0, c.f_out - c.parts[c.parts.length - 1].f - 2));
      const kx = xf ? tween(f - (c.f_out - xf), { frames: xf, ease: X.ease }) : 0;
      const box = { w: c.box.r - c.box.l, h: c.box.b - c.box.t };
      const px = S.exit(f >= c.f_out - xf ? kx : 0, box);
      c.el.style.transformOrigin = `${c.box.l - c.left + box.w / 2}px ${c.box.t - c.top + box.h / 2}px`;
      applyPose(c.el, px, `translate(${c.left}px,${c.top}px)`);
      for (const u of c.units) {
        const t = f - u.t0;
        const k = t < 0 ? 0 : tween(t, E);
        const p = S.enter(k, u, {});
        if (t < 0) p.hidden = true;
        applyPose(u.el, p);
      }
      for (const a of c.accentHooks) a.upd(f - a.t0);
      // Treatment behind the words.
      const kind = cs.style;
      if (kind === 'box') {
        const ex = c.lines.map((ln) => extent(ln.us, f)).filter(Boolean);
        const b = c.bgs[0];
        if (!ex.length) { b.style.opacity = '0'; continue; }
        const shownLines = c.lines.filter((ln, i) => extent(ln.us, f));
        const l = Math.min(...ex.map((e) => e.l)) - padX;
        const r = Math.max(...ex.map((e) => e.r)) + padX;
        const t0 = shownLines[0].top - padY;
        const b0 = shownLines[shownLines.length - 1].bot + padY;
        Object.assign(b.style, boxCSS(S, 'box', { h: b0 - t0 }), {
          opacity: String(ex[0].a), width: `${r - l}px`, height: `${b0 - t0}px`, transform: `translate(${l}px,${t0}px)`,
        });
      } else if (c.bgs.length) {
        c.lines.forEach((ln, i) => {
          const b = c.bgs[i];
          const e = extent(ln.us, f);
          if (!e) { b.style.opacity = '0'; return; }
          const l = e.l - padX;
          const r = e.r + padX;
          if (kind === 'pill') {
            const hh = ln.bot - ln.top + padY * 2;
            Object.assign(b.style, boxCSS(S, 'pill', { h: hh, radius: cs.radius || null }), {
              opacity: String(e.a), width: `${r - l}px`, height: `${hh}px`, transform: `translate(${l}px,${ln.top - padY}px)`,
            });
          } else {
            const th = Math.max(1, S.u(cs.rule));
            Object.assign(b.style, boxCSS(S, 'underline'), {
              opacity: String(e.a), width: `${e.r - e.l}px`, height: `${th}px`, transform: `translate(${e.l}px,${ln.bot - th + padY * 0.5}px)`,
            });
          }
        });
      }
    }
    return any;
  }

  draw.boxes = (f) => cards.filter((c) => f >= c.f_in && f < c.f_out).map((c) => c.box);
  draw.report = () => cards.filter((c) => c.hold < st.hold_min_s)
    .map((c) => `WARNING caption ${c.ci + 1} holds ${c.hold.toFixed(2)} s after its last words (STYLE.hold_min_s ${st.hold_min_s})`);
  draw.cards = cards;
  return draw;
}
