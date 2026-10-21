// Snapshots the live HUD at the owambe hall (night) and the phone home
// screen as static HTML: the game's own markup, scripts stripped, a <base>
// pointing at the live site so its CSS, fonts and icons load as they are.
// Writes assets/ui/hud.html, assets/ui/phone.html and rects.json.
import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { openLive, camera, STUDIO, SITE, sleep } from './live.mjs';

const OUT = path.join(STUDIO, 'assets', 'ui');
await mkdir(OUT, { recursive: true });
const { browser, page, ev } = await openLive({ hour: 21.3 });
const { goTo, hud } = camera(page);
const snap = () => ev((site) => {
  const doc = document.documentElement.cloneNode(true);
  doc.querySelectorAll('script, noscript, iframe').forEach((n) => n.remove());
  doc.querySelectorAll('canvas').forEach((n) => n.remove());
  const head = doc.querySelector('head');
  const base = document.createElement('base');
  base.href = `${site}/`;
  head.prepend(base);
  return `<!doctype html>\n${doc.outerHTML}`;
}, SITE);
const rects = (sels) => ev((list) => Object.fromEntries(list.map((s) => {
  const n = document.querySelector(s);
  if (!n || n.offsetParent === null && getComputedStyle(n).position !== 'fixed') return [s, null];
  const r = n.getBoundingClientRect();
  return [s, { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }];
})), sels);
try {
  await goTo('hall');
  await hud(true);
  await page.mouse.click(960, 540).catch(() => {});
  await sleep(1500);
  // Dismiss banners and gist cards so the snapshot is the plain HUD.
  await ev(() => document.querySelectorAll('.toast .close, .banner .close, [data-dismiss], .gist-card .x').forEach((b) => b.click()));
  await sleep(600);
  const HUD = ['#hud-me', '#hud-place', '#hud-goal', '#online-pill', '#audience-stats', '#board-mini', '#hud-nav', '#dock', '#chat', '#btn-hide', '#btn-phone', '#btn-map'];
  const r1 = await rects(HUD);
  const dock = await ev(() => [...document.querySelectorAll('#dock .act')].map((n) => {
    const r = n.getBoundingClientRect();
    return { action: n.dataset.action, text: n.innerText.replace(/\s+/g, ' ').trim(), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  }));
  await page.screenshot({ path: path.join(OUT, 'live-hud.png') });
  await writeFile(path.join(OUT, 'hud.html'), await snap());
  await page.click('#btn-phone');
  await sleep(1800);
  const phone = await ev(() => {
    const host = document.querySelector('#phone, .phone, #phone-shell');
    const r = host?.getBoundingClientRect();
    const apps = [...document.querySelectorAll('[data-app]')].filter((n) => n.offsetParent !== null).map((n) => {
      const b = n.getBoundingClientRect();
      return { app: n.dataset.app, text: n.innerText.replace(/\s+/g, ' ').trim(), x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
    });
    return { host: host ? { id: host.id, cls: host.className, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null, apps };
  });
  await page.screenshot({ path: path.join(OUT, 'live-phone.png') });
  await writeFile(path.join(OUT, 'phone.html'), await snap());
  const online = await ev(() => document.querySelector('#online-count')?.textContent);
  await writeFile(path.join(OUT, 'rects.json'), JSON.stringify({ viewport: [1920, 1080], hud: r1, dock, phone, online, at: new Date().toISOString() }, null, 1));
  console.log(JSON.stringify({ r1, dock, phone, online }, null, 1));
} finally {
  await browser.close();
}
