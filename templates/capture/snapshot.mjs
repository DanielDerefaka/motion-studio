// Snapshots the real product UI as static HTML: its own markup with scripts
// stripped and a <base> pointing at the live site, so its CSS, fonts and
// icons load as they are. Also records every panel's rect in UI pixels.
// Writes assets/ui/<page>.html, assets/ui/live-<page>.png, assets/ui/rects.json.
//
//   node src/snapshot.mjs [--config=src/capture.config.json] [--headed]
//
// --headed opens a visible browser on the persistent profile and waits for
// Enter, so a person can log in once; later runs reuse the session. The agent
// never types credentials.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

export const STUDIO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const arg = (k) => process.argv.find((a) => a.startsWith(`--${k}=`))?.split('=')[1];
export const CFG = JSON.parse(await readFile(path.resolve(STUDIO, arg('config') || 'src/capture.config.json'), 'utf8'));

export async function open({ headed = false } = {}) {
  const [width, height] = CFG.viewport;
  const browser = await puppeteer.launch({
    headless: !headed,
    userDataDir: path.join(STUDIO, CFG.profile || 'cache/live-profile'),
    defaultViewport: headed ? null : { width, height, deviceScaleFactor: 1 },
    args: ['--enable-webgl', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required', `--window-size=${width},${height}`],
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  return { browser, page, errors };
}

export async function visit(page, p) {
  await page.goto(new URL(p, CFG.url).href, { waitUntil: 'networkidle2', timeout: 60000 });
  if (CFG.waitFor) await page.waitForSelector(CFG.waitFor, { timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await sleep(CFG.settleMs ?? 2000);
  if (CFG.hideDuringCapture?.length) {
    await page.addStyleTag({ content: `${CFG.hideDuringCapture.join(',')}{display:none!important}` });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const OUT = path.join(STUDIO, 'assets', 'ui');
  await mkdir(OUT, { recursive: true });
  const headed = process.argv.includes('--headed');
  const { browser, page, errors } = await open({ headed });
  try {
    if (headed) {
      await page.goto(CFG.url);
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      await rl.question('Log in or set the product up in the window, then press Enter here. ');
      rl.close();
    }
    const rects = {};
    for (const [name, pg] of Object.entries(CFG.pages)) {
      await visit(page, pg.path);
      for (const [panel, { sel }] of Object.entries(pg.panels)) {
        const r = await page.$eval(sel, (n) => { const b = n.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; })
          .catch(() => null);
        if (!r || !r.w) throw new Error(`${name}: panel ${panel} (${sel}) is missing or hidden on the live page`);
        rects[panel] = { ...Object.fromEntries(Object.entries(r).map(([k, v]) => [k, Math.round(v)])), page: name,
          text: await page.$eval(sel, (n) => n.innerText.replace(/\s+/g, ' ').trim().slice(0, 120)) };
      }
      await page.screenshot({ path: path.join(OUT, `live-${name}.png`) });
      const html = await page.evaluate((site) => {
        const doc = document.documentElement.cloneNode(true);
        doc.querySelectorAll('script, noscript, iframe').forEach((n) => n.remove());
        // Canvases do not survive cloning; keep their last picture as an image.
        const live = [...document.querySelectorAll('canvas')];
        doc.querySelectorAll('canvas').forEach((n, i) => {
          const img = document.createElement('img');
          try { img.src = live[i].toDataURL(); } catch { /* tainted: leave blank */ }
          img.style.cssText = n.style.cssText; img.className = n.className;
          img.width = live[i].width; img.height = live[i].height;
          n.replaceWith(img);
        });
        const base = document.createElement('base');
        base.href = site;
        doc.querySelector('head').prepend(base);
        return `<!doctype html>\n${doc.outerHTML}`;
      }, new URL('/', CFG.url).href);
      await writeFile(path.join(OUT, `${name}.html`), html);
      console.log(`${name}: ${Object.keys(pg.panels).length} panels`);
    }
    await writeFile(path.join(OUT, 'rects.json'), JSON.stringify(rects, null, 1));
    console.log(`rects -> assets/ui/rects.json${errors.length ? `\npage errors: ${errors.slice(0, 5).join(' | ')}` : ''}`);
  } finally {
    await browser.close();
  }
}
