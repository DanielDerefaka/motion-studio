// Shared live-site session for the motion studio: one guest on
// https://www.phlifestyle.fun in a persistent browser profile, so every run
// reuses the same guest instead of making a new player on the live world.
// No bots, no writes beyond what a guest playing normally would do.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';
import { muteAnalytics } from '../../../tests/browser-analytics.mjs';

export const STUDIO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const SITE = 'https://www.phlifestyle.fun';
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function openLive({ hour = 12.5, width = 1920, height = 1080, dpr = 1, name = 'Tobi Dx' } = {}) {
  const browser = await puppeteer.launch({
    headless: true,
    userDataDir: path.join(STUDIO, 'cache', 'live-profile'),
    args: ['--use-angle=metal', '--enable-webgl', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  await page.setViewport({ width, height, deviceScaleFactor: dpr });
  await muteAnalytics(page);
  await page.goto(`${SITE}/?hour=${hour}`, { waitUntil: 'load', timeout: 60000 });
  await page.waitForFunction(() => window.__phlife, { timeout: 60000 });
  await page.evaluate(() => window.__phlife.ready);
  // Wait until the title has made up its mind: Continue (our saved guest)
  // or the Sign up / Log in / guest card.
  const which = await page.waitForFunction(() => {
    const seen = (sel) => { const n = document.querySelector(sel); return !!n && n.offsetParent !== null; };
    if (seen('#continue-btn:not([disabled])')) return 'continue';
    if (seen('#guest-btn')) return 'guest';
    return false;
  }, { timeout: 45000, polling: 250 }).then((h) => h.jsonValue());
  await sleep(800);
  if (which === 'continue') {
    await page.click('#continue-btn');
  } else {
    // Never make a second guest by accident: the saved one should Continue.
    if (!process.env.NEW_GUEST) throw new Error('title offers a new guest, not Continue: set NEW_GUEST=1 to make one');
    await page.click('#guest-btn');
    await page.click('#name-input');
    await page.keyboard.type(name);
    const card = (await page.$$('#look-picker .look-card'))[0];
    const body = await card.evaluate((n) => n.dataset.look.split('-')[0]);
    await page.click(`#look-picker .body-btn[data-body="${body}"]`);
    await card.click();
    await page.click('#enter-btn');
  }
  await page.waitForFunction(() => window.__phlife.mode === 'place', { timeout: 60000 });
  await sleep(2500);
  // The first-day class reveal, if it shows.
  const reveal = await page.$('#class-reveal .big');
  if (reveal && await reveal.evaluate((n) => n.offsetParent !== null)) { await reveal.click(); await sleep(600); }
  const ev = (fn, ...a) => page.evaluate(fn, ...a);
  return { browser, page, errors, ev };
}

export function camera(page) {
  const ev = (fn, ...a) => page.evaluate(fn, ...a);
  // The free camera from the trailer recorder: ease aim, yaw, pitch and zoom.
  const fly = (spec) => ev((s) => {
    cancelAnimationFrame(window.__fly);
    const st = window.__phlife.stage;
    const rad = (d) => (d * Math.PI) / 180;
    const yaw0 = rad(s.yaw[0]), yaw1 = rad(s.yaw[1]);
    const pitch0 = rad(s.pitch[0]), pitch1 = rad(s.pitch[1]);
    st.resetCamera();
    let yaw = Math.PI / 4, pitch = rad(50);
    const ease = (t) => t * t * (3 - 2 * t);
    const t0 = performance.now();
    const step = () => {
      const raw = Math.min(1, (performance.now() - t0) / (s.secs * 1000));
      const k = s.linear ? raw : ease(raw);
      const wy = yaw0 + (yaw1 - yaw0) * k, wp = pitch0 + (pitch1 - pitch0) * k;
      st.orbit(wy - yaw, wp - pitch); yaw = wy; pitch = wp;
      st.setZoom(s.zoom[0] + (s.zoom[1] - s.zoom[0]) * k);
      st.look({ x: s.from.x + (s.to.x - s.from.x) * k, z: s.from.z + (s.to.z - s.from.z) * k });
      if (raw < 1) window.__fly = requestAnimationFrame(step);
    };
    step();
  }, spec);
  const hud = async (on) => {
    const hidden = await ev(() => document.documentElement.classList.contains('ui-off'));
    if (hidden === !on) return;
    await page.keyboard.press('h');
    await sleep(400);
  };
  const setHour = (h) => ev(async (hour) => {
    const m = await import('/src/life/daylight.js');
    m.setHour(hour);
    window.__phlife.stage.relight();
  }, h);
  const goTo = async (place, mode = 'trek') => {
    const here = await ev(() => window.__phlife.placeId);
    if (here !== place) {
      await ev((to, m) => window.__phlife.ride(to, m), place, mode);
      await page.waitForFunction(() => window.__phlife.rideState, { timeout: 15000 }).catch(() => {});
      await ev(() => window.__phlife.skipRide());
      await page.waitForFunction((want) => window.__phlife.mode === 'place' && window.__phlife.placeId === want, { timeout: 30000 }, place);
    }
    await sleep(3500);
    await ev(() => window.__phlife.stage.resetCamera());
    return ev(() => ({ ...(window.__phlife.state.place?.bounds || { minX: -9, maxX: 9, minZ: -5, maxZ: 5 }) }));
  };
  return { fly, hud, setHour, goTo };
}
