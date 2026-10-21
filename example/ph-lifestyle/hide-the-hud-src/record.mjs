// Records the world footage on the live site (www.phlifestyle.fun) as the
// studio guest. HUD hidden, the free camera flies; one webm per shot plus a
// six-frame strip. Run: node production/motion-studio/src/record.mjs [--only=a,b]
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, rm, writeFile, readFile } from 'node:fs/promises';
import path from 'node:path';
import { openLive, camera, STUDIO, sleep } from './live.mjs';

const run = promisify(execFile);
const FF = 'ffmpeg';
const OUT = path.join(STUDIO, 'assets', 'footage');
const only = (process.argv.find((a) => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
await mkdir(OUT, { recursive: true });

const { browser, page, errors, ev } = await openLive({ hour: 12.5 });
const { fly, hud, setHour, goTo } = camera(page);
const mid = (b) => ({ x: (b.minX + b.maxX) / 2, z: (b.minZ + b.maxZ) / 2 });
let log = [];
try { log = JSON.parse(await readFile(path.join(OUT, 'clips.json'), 'utf8')); } catch {}

async function clip(slug, seconds, what, during) {
  if (only.length && !only.includes(slug)) return;
  const full = path.join(OUT, `${slug}.webm`);
  await rm(full, { force: true });
  const rec = await page.screencast({ path: full, fps: 30, overwrite: true });
  const t0 = Date.now();
  try { await during(); } catch (e) { console.log(`  during ${slug}: ${e.message}`); }
  const left = seconds * 1000 - (Date.now() - t0);
  if (left > 0) await sleep(left);
  await rec.stop();
  await ev(() => { cancelAnimationFrame(window.__fly); window.__phlife.stage.look(null); });
  await run(FF, ['-y', '-v', 'error', '-i', full, '-vf', `fps=6/${seconds},scale=320:-1,tile=6x1`, '-frames:v', '1', '-update', '1', full.replace('.webm', '-strip.png')]);
  const online = await ev(() => document.querySelector('#online-count')?.textContent || null);
  const place = await ev(() => window.__phlife.placeId);
  log = log.filter((c) => c.slug !== slug).concat({ slug, seconds, what, place, online, at: new Date().toISOString() });
  console.log(`clip ${slug} ${seconds}s at ${place}, ${online} online`);
}

async function sweep(slug, place, seconds, what, flight) {
  if (only.length && !only.includes(slug)) return;
  const b = await goTo(place);
  await hud(false);
  await sleep(900);
  const f = typeof flight === 'function' ? flight(b, mid(b)) : flight;
  await clip(slug, seconds, what, () => fly({ secs: seconds, ...f }));
}

try {
  await sweep('market-day', 'market', 6, 'Mile 1 Market by day, high slow drone',
    (b, c) => ({ from: { x: c.x - 4, z: c.z + 1 }, to: { x: c.x + 4, z: c.z - 1 }, yaw: [35, 55], pitch: [46, 38], zoom: [0.8, 0.95] }));
  await sweep('mall', 'phmall', 5, 'Port Harcourt Mall, drone across',
    (b, c) => ({ from: { x: c.x - 5, z: c.z }, to: { x: c.x + 5, z: c.z }, yaw: [30, 55], pitch: [36, 30], zoom: [0.95, 1.1] }));
  await sweep('estate', 'estate', 5, 'Palm Crest Estate houses, drone along',
    (b, c) => ({ from: { x: c.x - 7, z: c.z - 9 }, to: { x: c.x + 2, z: c.z - 9 }, yaw: [24, 36], pitch: [42, 38], zoom: [0.8, 0.9] }));
  if (!only.length || only.includes('ride-drop')) {
    await goTo('market');
    await hud(false);
    await clip('ride-drop', 7, 'A Drop (charter car) on the road out of Mile 1', async () => {
      await ev(() => window.__phlife.ride('estate', 'drop'));
      await page.waitForFunction(() => window.__phlife.rideState, { timeout: 10000 });
    });
    await ev(() => window.__phlife.skipRide());
    await page.waitForFunction(() => window.__phlife.mode === 'place', { timeout: 30000 }).catch(() => {});
  }
  await sweep('jevinik', 'jevinik', 4, 'Jevinik Restaurant, people eating, low push',
    (b, c) => ({ from: { x: c.x - 1, z: c.z + 1 }, to: { x: c.x + 1, z: c.z }, yaw: [150, 190], pitch: [34, 30], zoom: [1.9, 2.2] }));
  await sweep('home', 'home', 4, 'The guest room in the compound, slow push',
    (b, c) => ({ from: c, to: c, yaw: [40, 60], pitch: [48, 42], zoom: [1.0, 1.25] }));
  await sweep('beach', 'beach', 4, 'Tourist Beach, low orbit',
    (b, c) => ({ from: c, to: { x: c.x + 2, z: c.z }, yaw: [20, 80], pitch: [28, 24], zoom: [1.1, 1.3] }));
  if (!only.length || only.some((s) => ['hall-night', 'hall-high', 'club', 'ride-bus', 'market-night'].includes(s))) await setHour(21.3);
  await sweep('club', 'nightclub', 4, 'After Hours PH at night, orbit over the floor',
    (b, c) => ({ from: c, to: c, yaw: [0, 70], pitch: [32, 34], zoom: [1.7, 2.0] }));
  await sweep('hall-night', 'hall', 6, 'Garden City Event Centre at night, low orbit',
    (b, c) => ({ from: c, to: c, yaw: [0, 90], pitch: [30, 26], zoom: [1.05, 1.3] }));
  await sweep('hall-high', 'hall', 7, 'The hall from above, pulling back',
    (b, c) => ({ from: c, to: c, yaw: [160, 200], pitch: [42, 56], zoom: [1.2, 0.75] }));
  if (!only.length || only.includes('ride-bus')) {
    await setHour(18.3);
    await goTo('hall');
    await hud(false);
    await clip('ride-bus', 7, 'The sky-blue bus at night on the road', async () => {
      await ev(() => window.__phlife.ride('market', 'bus'));
      await page.waitForFunction(() => window.__phlife.rideState, { timeout: 10000 });
    });
    await ev(() => window.__phlife.skipRide());
    await page.waitForFunction(() => window.__phlife.mode === 'place', { timeout: 30000 }).catch(() => {});
  }
  await sweep('market-night', 'market', 7, 'Mile 1 under the lamps at night, wide pull back',
    (b, c) => ({ from: c, to: { x: c.x + 2, z: c.z }, yaw: [220, 245], pitch: [34, 44], zoom: [1.1, 0.8] }));
} finally {
  await writeFile(path.join(OUT, 'clips.json'), JSON.stringify(log, null, 2));
  console.log('errors', JSON.stringify(errors.slice(0, 8)));
  await browser.close();
}
