// The end card, laid onto the world comp from the endcard event on: the one
// HUD panel that comes back after Hide. Its glass is the live place card's
// own computed style (read from assets/ui/hud.html), the icon is
// game/brand/icon.svg, the line is the game's own description.
// Writes cache/screen/NNNN.jpg: the world slab's texture, every frame.
// --format=9x16 writes cache/screen-9x16/ with the card stacked and centred
// at END_CARD_9X16, inside the tall camera's view.
import { readFile, mkdir, rm, link } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';
import { STUDIO } from './live.mjs';

const T = JSON.parse(await readFile(path.join(STUDIO, 'src', 'timeline.json'), 'utf8'));
const WORLD = path.join(STUDIO, 'cache', 'world');
const TALL = process.argv.includes('--format=9x16');
const SCREEN = path.join(STUDIO, 'cache', TALL ? 'screen-9x16' : 'screen');
const ICON = path.resolve(STUDIO, '../../game/brand/icon.svg');
const at = T.EVENTS.find((e) => e.kind === 'endcard').f;
const only = process.argv.find((a) => a.startsWith('--frames='))?.slice(9).split(',').map(Number);

await mkdir(SCREEN, { recursive: true });
const num = (fr) => `${String(fr).padStart(4, '0')}.jpg`;
for (let fr = 1; fr < at; fr++) {
  await rm(path.join(SCREEN, num(fr)), { force: true });
  await link(path.join(WORLD, num(fr)), path.join(SCREEN, num(fr)));
}

const browser = await puppeteer.launch({ headless: true, args: ['--use-angle=metal'] });
const page = await browser.newPage();
await page.setViewport({ width: T.W, height: T.H, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(STUDIO, 'assets', 'ui', 'hud.html')).href, { waitUntil: 'networkidle0' });
const glass = await page.$eval('#hud-place', (n) => {
  const s = getComputedStyle(n);
  return ['background-color', 'background-image', 'border', 'border-radius', 'box-shadow', 'backdrop-filter', '-webkit-backdrop-filter', 'color']
    .map((k) => `${k}:${s.getPropertyValue(k)}`).join(';');
});
const icon = await readFile(ICON, 'utf8');

// Springs: overshoot then settle, in frames; nothing fades in.
const spring = (t, dur = 12) => {
  if (t <= 0) return 0;
  if (t >= dur) return 1;
  const k = t / dur;
  return 1 - Math.exp(-6 * k) * Math.cos(9 * k);
};
await page.setContent(`<!doctype html><html><head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap">
<style>
html,body{margin:0;width:${T.W}px;height:${T.H}px;overflow:hidden;font-family:Poppins,system-ui,sans-serif}
#bg{position:absolute;inset:0;width:100%;height:100%}
#card{position:absolute;left:340px;bottom:150px;display:flex;align-items:center;gap:28px;padding:26px 40px 26px 26px;${glass};border-radius:28px;transform-origin:0 100%}
${TALL ? `#card{left:${T.END_CARD_9X16.cx}px;bottom:${T.END_CARD_9X16.bottom}px;flex-direction:column;text-align:center;gap:16px;padding:30px 40px;transform-origin:50% 100%;margin-left:-340px;width:600px} .line{transform-origin:50% 50%!important}` : ''}
#icon{width:132px;height:132px;flex:none;transform-origin:50% 100%}
#icon svg{width:100%;height:100%;display:block}
h1{margin:0;font-size:62px;font-weight:700;line-height:1.05;letter-spacing:-0.01em;color:#fff}
p{margin:8px 0 14px;font-size:25px;font-weight:500;color:rgba(255,255,255,.86)}
#url{display:inline-block;padding:7px 18px;border-radius:99px;background:#008751;color:#fff;font-size:24px;font-weight:600}
.line{display:block;transform-origin:0 50%}
</style></head><body><img id="bg"><div id="card"><div id="icon">${icon}</div>
<div><h1 class="line" id="t1">PH Lifestyle</h1><p class="line" id="t2">${T.END_LINE}</p><span class="line" id="url">${T.END_URL}</span></div></div></body></html>`, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);

for (let fr = at; fr <= T.FRAMES; fr++) {
  if (only && !only.includes(fr)) continue;
  const t = fr - at;
  const s = {
    card: spring(t, 9), icon: spring(t - 3, 12),
    t1: spring(t - T.BEAT / 2, 10), t2: spring(t - T.BEAT, 10), url: spring(t - T.BEAT * 1.5, 10),
    tall: TALL,
  };
  await page.evaluate((src, st) => {
    document.querySelector('#bg').src = src;
    const set = (sel, css) => { document.querySelector(sel).style.transform = css; };
    // The card rises out of the floor of the world and settles (panel rule).
    set('#card', `translateY(${(1 - st.card) * 260}px) scale(${0.9 + 0.1 * st.card})`);
    set('#icon', `scale(${st.icon}, ${Math.max(0, 2 * st.icon - st.icon ** 2)})`);
    for (const k of ['t1', 't2', 'url']) set(`#${k}`, `translateX(${st.tall ? 0 : (1 - st[k]) * -40}px) scaleX(${Math.max(0.001, st[k])})`);
    return new Promise((r) => (document.querySelector('#bg').complete ? r() : document.querySelector('#bg').addEventListener('load', r, { once: true })));
  }, pathToFileURL(path.join(WORLD, num(fr))).href, s);
  const file = path.join(SCREEN, num(fr));
  await page.screenshot({ path: file, type: 'jpeg', quality: 94 });
}
console.log(`end card on frames ${at}-${T.FRAMES}`);
await browser.close();
