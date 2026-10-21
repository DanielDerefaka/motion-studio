// Scout the live city: join, screenshot, list places and who is about.
import path from 'node:path';
import { openLive, STUDIO, sleep } from './live.mjs';

const out = path.join(STUDIO, 'reviews', 'scout');
const { browser, page, errors, ev } = await openLive();
try {
  await import('node:fs/promises').then((fs) => fs.mkdir(out, { recursive: true }));
  const info = await ev(() => ({
    me: { id: window.__phlife.me?.id, name: window.__phlife.me?.name, cash: window.__phlife.me?.cash, home: window.__phlife.me?.property?.home },
    place: window.__phlife.placeId,
    players: window.__phlife.players.length,
    online: document.querySelector('#online-count, .online b, #hud-online')?.textContent,
    places: Object.keys(window.__phlife.state.places || window.__phlife.ctx?.places || {}).slice(0, 80),
    hud: [...document.querySelectorAll('#hud [id]')].map((n) => n.id).slice(0, 80),
  }));
  console.log(JSON.stringify(info, null, 1));
  await page.screenshot({ path: path.join(out, 'arrive.png') });
  await page.click('#btn-phone');
  await sleep(1500);
  await page.screenshot({ path: path.join(out, 'phone.png') });
  console.log('errors', errors.slice(0, 5));
} finally {
  await browser.close();
}
