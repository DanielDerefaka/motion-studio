// Renders the UI slab textures at 3x from the live DOM snapshots
// (assets/ui/hud.html, phone.html): each panel alone on a transparent page,
// plus the cash-and-needs panel once per frame, driven by timeline.json.
// Writes assets/ui/tex/*.png, assets/ui/me/NNNN.png and textures.json.
import { readFile, writeFile, mkdir, rm, link } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';
import { STUDIO } from './live.mjs';
import { glyph } from '../../../game/src/life/glyphs.js';

const T = JSON.parse(await readFile(path.join(STUDIO, 'src', 'timeline.json'), 'utf8'));
const UI = path.join(STUDIO, 'assets', 'ui');
const TEX = path.join(UI, 'tex');
const ME = path.join(UI, 'me');
await rm(ME, { recursive: true, force: true });
await mkdir(TEX, { recursive: true });
await mkdir(ME, { recursive: true });
const PAD = 24;
const DPR = 3;
const out = {};

const browser = await puppeteer.launch({ headless: true, args: ['--use-angle=metal'] });
const page = await browser.newPage();
await page.setViewport({ width: T.W, height: T.H, deviceScaleFactor: DPR });

async function load(file) {
  await page.goto(pathToFileURL(path.join(UI, file)).href, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: 'html,body{background:transparent!important} *{animation:none!important;transition:none!important}' });
}

// Show one element alone; `hide` lists selectors inside it to leave out.
async function isolate(sel, hide = []) {
  await page.evaluate((s, h) => {
    document.querySelector('#iso')?.remove();
    const st = document.createElement('style');
    st.id = 'iso';
    st.textContent = `body *{visibility:hidden!important} ${s}, ${s} *{visibility:visible!important} `
      + h.map((x) => `html body ${x}, html body ${x} *{visibility:hidden!important}`).join(' ');
    document.head.append(st);
  }, sel, hide);
}

async function rectOf(sel) {
  return page.$eval(sel, (n) => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
}

async function shoot(name, sel, hide = [], file = path.join(TEX, `${name}.png`), fixed = null) {
  await isolate(sel, hide);
  const r = fixed || await rectOf(sel);
  const clip = { x: Math.max(0, r.x - PAD), y: Math.max(0, r.y - PAD), width: 0, height: 0 };
  clip.width = Math.min(T.W, r.x + r.w + PAD) - clip.x;
  clip.height = Math.min(T.H, r.y + r.h + PAD) - clip.y;
  await page.screenshot({ path: file, clip, omitBackground: true });
  return { file: path.relative(STUDIO, file), x: clip.x, y: clip.y, w: clip.width, h: clip.height, el: r };
}

// --- HUD panels -------------------------------------------------------------
await load('hud.html');
await page.addStyleTag({ content: '#moodlets{display:none!important}' });
for (const [name, sel] of [['place', '#hud-place'], ['stats', '#audience-stats'], ['board', '#board-mini'], ['goal', '#hud-goal'], ['chat', '#chat']]) {
  out[name] = await shoot(name, sel);
}
out.dock = await shoot('dock', '#dock', ['.act[data-action="spray"]']);
out['dock-spray'] = await shoot('dock-spray', '#dock .act[data-action="spray"]');
out.nav = await shoot('nav', '#hud-nav', ['.nav-btn']);
for (const id of ['home', 'map', 'people', 'phone', 'eyes', 'hide']) out[`btn-${id}`] = await shoot(`btn-${id}`, `#btn-${id}`);

// --- The cash and needs panel, per frame ------------------------------------
const MOODS = [[75, 'happy', 'Very happy'], [58, 'smile', 'Happy'], [40, 'meh', 'Okay'], [20, 'sad', 'Not happy'], [-1, 'miserable', 'Miserable']];
const MOOD_KEYS = ['hunger', 'energy', 'vibe', 'thirst'];
const easeOut = (k) => 1 - (1 - k) ** 3;
const fills = T.EVENTS.filter((e) => e.kind === 'need-fill');
const kick = T.EVENTS.find((e) => e.kind === 'kick-spray');
function stateAt(fr) {
  const needs = { ...T.NEEDS0 };
  for (const e of fills) {
    const k = Math.min(1, Math.max(0, (fr - e.f) / 9));
    needs[e.need] = T.NEEDS0[e.need] + (100 - T.NEEDS0[e.need]) * easeOut(k);
  }
  // One ₦200 note leaves every 2 frames after the kick, as the game sprays.
  const gone = fr < kick.f ? 0 : Math.min(kick.notes, Math.floor((fr - kick.f) / 2) + 1);
  return { needs, cash: T.CASH0 - gone * kick.each };
}
const meRect = await rectOf('#hud-me');
const seen = new Map();
for (let fr = 1; fr <= T.FRAMES; fr++) {
  const s = stateAt(fr);
  const key = JSON.stringify([s.cash, Object.values(s.needs).map((v) => v.toFixed(1))]);
  const file = path.join(ME, `${String(fr).padStart(4, '0')}.png`);
  if (seen.has(key)) { await link(seen.get(key), file); continue; }
  const values = MOOD_KEYS.map((k) => s.needs[k]);
  const score = Math.min(values.reduce((a, b) => a + b, 0) / values.length, Math.min(...values) + 40);
  const [, face, word] = MOODS.find(([at]) => score >= at);
  await page.evaluate((st, faceSvg, w, sc) => {
    document.querySelector('#cash-value').textContent = st.cash.toLocaleString('en-NG');
    for (const [k, v] of Object.entries(st.needs)) {
      const row = document.querySelector(`.need[data-need="${k}"]`);
      if (!row) continue;
      row.querySelector('.bar i').style.width = `${v.toFixed(1)}%`;
      row.classList.toggle('low', v < 20);
      row.classList.toggle('mid', v >= 20 && v < 45);
    }
    document.querySelector('#mood-face').innerHTML = faceSvg;
    document.querySelector('#mood-word').textContent = w;
    const m = document.querySelector('#mood');
    m.classList.toggle('good', sc >= 58);
    m.classList.toggle('bad', sc < 40);
  }, s, glyph(face), word, score);
  const shot = await shoot('me', '#hud-me', [], file, meRect);
  out.me ||= { ...shot, file: path.relative(STUDIO, path.join(ME, '0001.png')), seq: path.relative(STUDIO, ME) };
  seen.set(key, file);
}
console.log(`me: ${seen.size} distinct states over ${T.FRAMES} frames`);
// Rows of the needs panel in UI px, for the hops.
out.needRows = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.need')].map((n) => {
  const r = n.querySelector('.bar').getBoundingClientRect();
  return [n.dataset.need, { x: r.x, y: r.y, w: r.width, h: r.height }];
})));

// --- The phone --------------------------------------------------------------
await load('phone.html');
const TILES = ['cars', 'events', 'property', 'boutique'];
out.phone = await shoot('phone', '#sheet-phone', TILES.map((a) => `[data-app="${a}"]`));
for (const a of TILES) out[`app-${a}`] = await shoot(`app-${a}`, `#sheet-phone [data-app="${a}"]`);

// --- The ₦200 note (the game's own canvas drawing, notes.js) and the logo ---
await page.goto('about:blank');
const note = await page.evaluate(async () => {
  await document.fonts.ready;
  const c = document.createElement('canvas');
  c.width = 384; c.height = 192;
  const g = c.getContext('2d');
  g.scale(3, 3);
  g.fillStyle = '#c9a25a'; g.fillRect(0, 0, 128, 64);
  g.fillStyle = '#8a5a2b'; g.fillRect(0, 0, 128, 8); g.fillRect(0, 56, 128, 8);
  g.fillStyle = '#5c8a52'; g.fillRect(82, 12, 38, 40);
  g.fillStyle = '#4a2f17'; g.font = 'bold 26px system-ui, sans-serif'; g.textBaseline = 'middle'; g.fillText('₦200', 8, 33);
  g.strokeStyle = '#4a2f17'; g.lineWidth = 2; g.strokeRect(2, 2, 124, 60);
  return c.toDataURL('image/png').split(',')[1];
});
await writeFile(path.join(TEX, 'note.png'), Buffer.from(note, 'base64'));
out.note = { file: path.relative(STUDIO, path.join(TEX, 'note.png')) };

await writeFile(path.join(UI, 'textures.json'), JSON.stringify({ pad: PAD, dpr: DPR, ...out }, null, 1));
console.log(Object.keys(out).join(' '));
await browser.close();
