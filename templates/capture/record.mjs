// Records real product footage: one webm per clip in capture.config.json,
// with the page driven by simple steps (scroll, hover, click, type, wait),
// plus a six-frame strip per clip for the footage contact sheet.
// Writes assets/footage/<slug>.webm, <slug>-strip.png and clips.json.
//
//   node src/record.mjs [--only=clip-a,clip-b] [--config=src/capture.config.json]
//
// page.screencast needs ffmpeg on PATH. Record as a guest or the studio's own
// test account: never make writes a normal visitor would not make.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, rm, writeFile, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { open, visit, sleep, STUDIO, CFG } from './snapshot.mjs';

const run = promisify(execFile);
const FF = process.env.FFMPEG || 'ffmpeg';
const OUT = path.join(STUDIO, 'assets', 'footage');
const only = (process.argv.find((a) => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
await mkdir(OUT, { recursive: true });
let log = [];
try { log = JSON.parse(await readFile(path.join(OUT, 'clips.json'), 'utf8')); } catch { /* first run */ }

const { browser, page, errors } = await open();

// Smooth scroll over `secs`, eased, driven from the page's own clock.
const scroll = (dy, secs) => page.evaluate((d, s) => new Promise((done) => {
  const y0 = window.scrollY; const t0 = performance.now();
  const ease = (k) => k * k * (3 - 2 * k);
  const step = () => {
    const k = Math.min(1, (performance.now() - t0) / (s * 1000));
    window.scrollTo(0, y0 + d * ease(k));
    if (k < 1) requestAnimationFrame(step); else done();
  };
  step();
}), dy, secs);

// The screencast only gets a frame when the page paints: a still page gives
// an empty webm. A 1px near-invisible pixel that changes every rAF keeps
// frames coming at the full rate without touching what the viewer sees.
const heartbeat = () => page.evaluate(() => {
  if (document.getElementById('__beat')) return;
  const d = document.createElement('div');
  d.id = '__beat';
  d.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;pointer-events:none;z-index:2147483647';
  document.body.append(d);
  const tick = (t) => { d.style.background = `rgba(0,0,0,${0.01 + 0.01 * (Math.floor(t / 16) % 2)})`; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
});

async function play(steps) {
  for (const s of steps) {
    if (s.scroll) await scroll(s.scroll, s.secs || 2);
    if (s.hover) await page.hover(s.hover);
    if (s.click) await page.click(s.click);
    if (s.type) await page.type(s.type.sel, s.type.text, { delay: s.type.delay ?? 60 });
    if (s.wait) await sleep(s.wait);
  }
}

try {
  for (const c of CFG.clips) {
    if (only.length && !only.includes(c.slug)) continue;
    await visit(page, c.path);
    await heartbeat();
    const full = path.join(OUT, `${c.slug}.webm`);
    await rm(full, { force: true });
    const rec = await page.screencast({ path: full, fps: 30 });
    const t0 = Date.now();
    try { await play(c.steps || []); } catch (e) { console.log(`  ${c.slug}: ${e.message}`); }
    const left = c.seconds * 1000 - (Date.now() - t0);
    if (left > 0) await sleep(left);
    await rec.stop();
    if (!(await stat(full)).size) throw new Error(`${c.slug}: the screencast wrote no frames (did the page load? ${c.path})`);
    await run(FF, ['-y', '-v', 'error', '-i', full, '-vf', `fps=6/${c.seconds},scale=320:-1,tile=6x1`, '-frames:v', '1',
      '-update', '1', full.replace('.webm', '-strip.png')]);
    log = log.filter((x) => x.slug !== c.slug).concat({ slug: c.slug, seconds: c.seconds, what: c.what, at: new Date().toISOString() });
    console.log(`clip ${c.slug} ${c.seconds}s`);
  }
} finally {
  await writeFile(path.join(OUT, 'clips.json'), JSON.stringify(log, null, 2));
  if (errors.length) console.log('page errors', errors.slice(0, 8));
  await browser.close();
}
