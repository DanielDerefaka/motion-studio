// Cuts the snapshotted UI into slab textures at 3x: each panel alone on a
// transparent page, so in 3D every panel can light up, press and fall on its
// own. A panel's `hide` list leaves its children out (they become their own
// slabs, stood proud of the parent).
// Writes assets/ui/tex/<panel>.png and assets/ui/textures.json:
//   { pad, dpr, <panel>: { file, x, y, w, h, el: {x, y, w, h} } }
// x/y/w/h is the padded crop in UI px, el the element itself.
//
//   node src/slabs.mjs [--config=src/capture.config.json]
//
// A panel whose content changes during the film (a counter, a progress bar)
// is captured once per frame instead: see perFrame() at the bottom.
import { readFile, writeFile, mkdir, link } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';
import { STUDIO, CFG } from './snapshot.mjs';

const UI = path.join(STUDIO, 'assets', 'ui');
const TEX = path.join(UI, 'tex');
const PAD = 24;
const DPR = 3;
const [W, H] = CFG.viewport;
await mkdir(TEX, { recursive: true });

const browser = await puppeteer.launch({ headless: true });
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: DPR });

async function load(name) {
  await page.goto(pathToFileURL(path.join(UI, `${name}.html`)).href, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: 'html,body{background:transparent!important} *{animation:none!important;transition:none!important}' });
}

// Show one element alone. The hide rules are scoped `html body <sel> <child>`
// so they outrank the `<sel> *{visible}` rule; unscoped, they lose and the
// children stay in the parent's texture.
async function isolate(sel, hide = []) {
  await page.evaluate((s, h) => {
    document.querySelector('#iso')?.remove();
    const st = document.createElement('style');
    st.id = 'iso';
    st.textContent = `body *{visibility:hidden!important} ${s}, ${s} *{visibility:visible!important} `
      + h.map((x) => `html body ${s} ${x}, html body ${s} ${x} *{visibility:hidden!important}`).join(' ');
    document.head.append(st);
  }, sel, hide);
}

const rectOf = (sel) => page.$eval(sel, (n) => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });

export async function shoot(name, sel, hide = [], file = path.join(TEX, `${name}.png`), fixed = null) {
  await isolate(sel, hide);
  const r = fixed || await rectOf(sel);
  const clip = { x: Math.max(0, r.x - PAD), y: Math.max(0, r.y - PAD) };
  clip.width = Math.min(W, r.x + r.w + PAD) - clip.x;
  clip.height = Math.min(H, r.y + r.h + PAD) - clip.y;
  await page.screenshot({ path: file, clip, omitBackground: true });
  return { file: path.relative(STUDIO, file), x: clip.x, y: clip.y, w: clip.width, h: clip.height, el: r };
}

const out = {};
for (const [name, pg] of Object.entries(CFG.pages)) {
  await load(name);
  for (const [panel, { sel, hide = [] }] of Object.entries(pg.panels)) out[panel] = await shoot(panel, sel, hide);
}

// Per-frame panel: set the DOM to the film's state at each frame and shoot it
// into assets/ui/<panel>/NNNN.png. Identical states hard-link one file.
// Example: await perFrame('panel-stats', 'home', '#stats', (fr, T) => ({ '#stats b': String(fr * 10) }));
// eslint-disable-next-line no-unused-vars
async function perFrame(panel, pageName, sel, stateAt) {
  const T = JSON.parse(await readFile(path.join(STUDIO, 'src', 'timeline.json'), 'utf8'));
  const dir = path.join(UI, panel);
  await mkdir(dir, { recursive: true });
  await load(pageName);
  const fixed = await rectOf(sel);
  const seen = new Map();
  for (let fr = 1; fr <= T.FRAMES; fr++) {
    const state = stateAt(fr, T);                       // { selector: textContent }
    const key = JSON.stringify(state);
    const file = path.join(dir, `${String(fr).padStart(4, '0')}.png`);
    if (seen.has(key)) { await link(seen.get(key), file).catch(() => {}); continue; }
    await page.evaluate((s) => { for (const [q, v] of Object.entries(s)) document.querySelector(q).textContent = v; }, state);
    const shot = await shoot(panel, sel, [], file, fixed);
    out[panel] ||= { ...shot, file: path.relative(STUDIO, path.join(dir, '0001.png')), seq: path.relative(STUDIO, dir) };
    seen.set(key, file);
  }
  console.log(`${panel}: ${seen.size} distinct states over ${T.FRAMES} frames`);
}

await writeFile(path.join(UI, 'textures.json'), JSON.stringify({ pad: PAD, dpr: DPR, ...out }, null, 1));
console.log(`${Object.keys(out).length} slabs -> assets/ui/textures.json`);
await browser.close();
