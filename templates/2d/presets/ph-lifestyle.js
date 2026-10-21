// One example look, not a default: the PH Lifestyle explainer (smoked glass
// caption pills, a green brush swash under accent words, a slanted serif
// accent, white-dot pins, outlined money). Loaded only when STYLE.preset is
// 'ph-lifestyle' (in timeline.py, or --style=file.json holding {"preset":
// "ph-lifestyle"}). Its fonts are the studio's FONTS, e.g.
//   FONTS = dict(display=".../example/ph-lifestyle/fonts/Editor'sNote-Semibold.otf",
//                body=".../example/ph-lifestyle/fonts/mazzard-soft-h-bold.otf")
// It shows the two ways a look goes past plain STYLE data: CSS for the
// classes the templates expose, and hooks (a new entry kind, an accent
// decoration). Copy it to start another look that needs code.
import { clamp, lerp, ease } from '../motion.js';

// The house spring: lands by `frames`, a small overshoot (1 - e^-6u cos 9u).
const settle = (k) => (k <= 0 ? 0 : k >= 1 ? 1 : 1 - Math.exp(-6 * k) * Math.cos(9 * k));

export const style = {
  bg: '#121214', ink: '#ffffff', accent: '#008751', palette: ['#e5484d', '#f2b134'],
  type: {
    display: { font: 'display', weight: 600, size: 0.06, tracking: -0.02, line: 1, case: 'none', style: 'italic' },
    body: { font: 'body', weight: 700, size: 0.0278, tracking: -0.01, line: 1.14, case: 'none' },
    accent: { font: 'display', weight: 600, style: 'italic', scale: 1.16, color: '#ffffff' },
  },
  caption: { style: 'pill', y: 0.905, max_w: 1.39, align: 'center', bg: 'rgba(18,18,20,0.42)', radius: 0.02, pad: [0.0054, 0.024], type: 'body', size: 0.0593, shadow: 0.9 },
  enter: { kind: 'pop', by: 'block', frames: 8, stagger: 0, ease: settle, dist: 0.028 },
  exit: { kind: 'rise', frames: 4, ease: [0.55, 0, 1, 0.45] },
  move: { ease: [0.22, 1, 0.36, 1], overshoot: 0.08 },
  chip: { size: 0.0278 },
  callout: { style: 'box', line: 0.0021, dot: 0.0065, off: 0.085, pulse: 30 },
  formats: {
    // 9:16: the bottom ~20 % is the phone UI's own buttons, so captions sit higher.
    '9x16': { caption: { y: 0.795, size: 0.0385, max_w: 0.49 }, type: { body: { size: 0.0175 } }, chip: { size: 0.017 }, callout: { off: 0.044 } },
  },
};

const SVGNS = 'http://www.w3.org/2000/svg';
// A hand-drawn brush swash: a tapered stroke along a gentle wave. The seed
// only bends it, so the same card always gets the same swash.
function swashPath(seed) {
  const n = 28;
  const top = [];
  const bot = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    const y = 50 + 16 * Math.sin(u * Math.PI * 1.15 + seed) - 18 * u + 9;
    const w = 6 + 40 * Math.sin(Math.PI * clamp(u * 0.92 + 0.04)) ** 0.6;
    top.push([u * 100, y - w / 2]);
    bot.push([u * 100 + 1.2, y + w / 2]);
  }
  return `M${[...top, ...bot.reverse()].map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('L')}Z`;
}
let uid = 0;

export const hooks = {
  // A new entry kind: each fragment pops up on the spring, a touch tilted.
  kinds: {
    pop: (k, unit, d) => ({
      transform: `translateY(${((1 - k) * d).toFixed(2)}px) scale(${lerp(0.5, 1, k).toFixed(4)}) rotate(${((1 - k) * -4).toFixed(3)}deg)`,
      opacity: clamp(k * 2.5),
    }),
  },
  caption: {
    // The swash under each accent word wipes on just after the word lands.
    accent(el, { S, seed }) {
      el.style.position = 'relative';
      const sv = document.createElementNS(SVGNS, 'svg');
      sv.setAttribute('viewBox', '0 0 100 100');
      sv.setAttribute('preserveAspectRatio', 'none');
      sv.style.cssText = 'position:absolute;left:-5%;width:110%;bottom:-.1em;height:.44em;overflow:visible;z-index:-1';
      const id = `ph_swash_${uid++}`;
      sv.innerHTML = `<defs><clipPath id="${id}"><rect x="-2" y="-50" width="0" height="200"/></clipPath></defs>`
        + `<path d="${swashPath(seed)}" fill="${S.style.accent}" clip-path="url(#${id})"/>`;
      el.append(sv);
      const rect = sv.querySelector('rect');
      return (t) => rect.setAttribute('width', String(104 * ease.outCubic((t - 2) / 7)));
    },
  },
  // Glass, borders and shadows on the classes the templates expose.
  css: () => `
.ms-card .w.acc{padding:0 .04em 0 .08em;line-height:1}
.ms-lab .t{font-family:"body",system-ui,sans-serif!important;font-style:normal!important;font-weight:700!important}
.ms-bg.ms-pill{box-shadow:0 10px 40px rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.06)}
.ms-chip,.ms-lab{background:rgba(18,18,20,.62)!important;border:1px solid rgba(255,255,255,.14);
  box-shadow:0 12px 36px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.06)}
.ms-chip{border-radius:999px!important}
.ms-lab{border-radius:.53em!important}
.ms-lab.ms-tip{border-radius:999px!important}
.ms-lab .s{opacity:.7!important}
#lines{filter:drop-shadow(0 1px 3px rgba(0,0,0,.5))}
.ms-dot b{background:#fff!important;box-shadow:0 0 0 3px var(--accent),0 2px 8px rgba(0,0,0,.6)}
.ms-money{font-family:"body",system-ui,sans-serif!important;font-style:normal!important;font-weight:700!important;letter-spacing:-.02em!important;
  -webkit-text-stroke:.16em #fff;paint-order:stroke fill;filter:drop-shadow(0 6px 14px rgba(0,0,0,.45));text-shadow:none!important}
.ms-money.spend{color:var(--p0)!important}
`,
};
