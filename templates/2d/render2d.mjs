// The 2D driver: loads a composition page, hands it the timeline (and the
// anchors for the format), then for every frame calls
// `await window.renderFrame(frame)` in the page and screenshots the viewport.
//
//   node src/render2d.mjs src/overlay.html [--format=9x16] [--from=N --to=M] [--test=N,N]
//        [--opaque] [--out=dir] [--jobs=K] [--fake] [--style=look.json] [--studio=dir]
//
// Writes <out>/NNNN.png, one per frame, transparent unless --opaque (or the
// page's <meta name="motion-studio" content="opaque">). Default out:
// cache/overlay-<fmt>/, or cache/frames2d-<fmt>/ when opaque. Frames the page
// reports empty (renderFrame returns false) hard-link one blank PNG kept
// beside the folder (cache/<folder>-blank.png), so the folder holds exactly
// FRAMES files named NNNN.png. --test writes only the listed frames to
// reviews/2d-test/ (plus a -check.png over a dark checker when transparent).
// --jobs=K renders K slices of the range in K browsers at once.
//
// Anchors: {screen:{fmt:[x,y]}} are fixed points. Any other anchor comes from
// the Blender exporter's cache/anchors-<fmt>.json; without it the run stops,
// unless --fake (drifting stand-ins, warned about on every run) or the page
// says content="no-anchors".
//
// The page owns the look; this file only feeds it data and takes pictures.
// window.STUDIO = { T (timeline, with STYLE), fmt, w, h, tall, opaque, fake,
// anchors, fonts: {FONTS key -> family | null}, fontsReady, styleOverride }.
import { readFile, writeFile, mkdir, rm, link, access, readdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';

const argv = process.argv.slice(2);
const arg = (k) => argv.find((a) => a.startsWith(`--${k}=`))?.slice(k.length + 3);
const flag = (k) => argv.includes(`--${k}`);
const COMP = argv.find((a) => !a.startsWith('--'));
if (!COMP) {
  console.error('usage: node src/render2d.mjs <composition.html> [--format=9x16] [--from=N --to=M] [--test=N,N] [--opaque] [--out=dir] [--jobs=K] [--fake] [--style=look.json] [--studio=dir]');
  process.exit(2);
}
const exists = (p) => access(p).then(() => true, () => false);
const COMP_PATH = path.resolve(COMP);
if (!(await exists(COMP_PATH))) throw new Error(`no composition at ${COMP_PATH}`);
// The studio is the folder above the one holding the composition (src/).
const STUDIO = path.resolve(arg('studio') || path.dirname(path.dirname(COMP_PATH)));
const rel = (p) => path.relative(STUDIO, p) || '.';
const NAME = path.basename(COMP_PATH, path.extname(COMP_PATH));

const TL = path.join(STUDIO, 'src', 'timeline.json');
if (!(await exists(TL))) throw new Error(`${rel(TL)} missing: run python3 src/timeline.py first`);
const T = JSON.parse(await readFile(TL, 'utf8'));
const FMT = arg('format') || '16x9';
if (!T.FORMATS?.[FMT]) throw new Error(`format ${FMT} not in timeline FORMATS (${Object.keys(T.FORMATS || {}).join(', ')})`);
const [W, H] = T.FORMATS[FMT];
const N = T.FRAMES;

// What the page asks for, from its <meta name="motion-studio" content="...">.
const html = await readFile(COMP_PATH, 'utf8');
const META = new Set((html.match(/<meta\s+name=["']motion-studio["']\s+content=["']([^"']*)["']/i)?.[1] || '').split(/\s+/).filter(Boolean));
const OPAQUE = flag('opaque') || META.has('opaque');
const NO_ANCHORS = META.has('no-anchors');
const TEST = arg('test')?.split(',').map(Number).filter((n) => n >= 1 && n <= N);
const FROM = Math.max(1, Number(arg('from') || 1));
const TO = Math.min(N, Number(arg('to') || N));
const JOBS = Math.max(1, Number(arg('jobs') || 1));
const FULL = !arg('from') && !arg('to') && !TEST;

// --- anchors ------------------------------------------------------------------
const ANCH = T.ANCHORS || {};
const isScreen = (a) => !!a.screen;
const REAL = path.join(STUDIO, 'cache', `anchors-${FMT}.json`);
const FAKE_PATH = path.join(STUDIO, 'cache', `anchors-fake-${FMT}.json`);
const BAR = '!'.repeat(78);

// A fixed screen point for every frame. A point given only for another
// format is scaled across (and said so), so a 2D film can name one.
function screenTrack(id, a) {
  let p = a.screen[FMT];
  if (!p) {
    const [k, q] = Object.entries(a.screen)[0];
    const [w0, h0] = T.FORMATS[k];
    p = [(q[0] * W) / w0, (q[1] * H) / h0];
    console.warn(`render2d: anchor ${id} has no ${FMT} point; scaled from ${k}`);
  }
  const vis = p[0] >= 0 && p[0] <= W && p[1] >= 0 && p[1] <= H ? 1 : 0;
  const row = [p[0], p[1], vis];
  return Array.from({ length: N }, () => row);
}

// Slowly drifting stand-ins for the projected 3D points: a slab anchor sits
// where its UI rect would land in a square-on camera (UI space W x H, cropped
// harder on the tall format so edge points really go off screen), an object
// anchor somewhere central, by its name.
function fakeTracks() {
  const UW = T.W || 1920;
  const UH = T.H || 1080;
  const tall = H > W;
  const s = tall ? (W / UW) * 1.1 : (W / UW) * 0.92;
  const out = {};
  for (const [id, a] of Object.entries(ANCH)) {
    if (isScreen(a)) continue;
    const seed = [...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 100003, 7);
    let p;
    const r = a.slab && T.RECTS?.[a.slab];
    if (a.at) p = a.at;
    else if (r) p = [r.x + r.w / 2, r.y + r.h / 2];
    let bx;
    let by;
    if (p) {
      bx = (p[0] - UW / 2) * s + W / 2;
      // Squashed vertically so UI-space points near the bottom stay clear of
      // the caption band; real anchors come from the camera, not from this.
      by = (p[1] - UH / 2) * s * 0.75 + H * (tall ? 0.44 : 0.45);
    } else {
      bx = W * (0.3 + 0.4 * ((seed % 97) / 97));
      by = H * (0.3 + 0.3 * ((seed % 89) / 89));
    }
    const amp = W / 1920;
    out[id] = Array.from({ length: N }, (_, i) => {
      const t = i / (T.FPS || 30);
      const x = bx + amp * (40 * Math.sin(t * 0.7 + seed) + 18 * Math.sin(t * 1.9 + seed * 2));
      const y = by + amp * (26 * Math.cos(t * 0.6 + seed) + 10 * Math.sin(t * 2.3 + seed));
      const vis = x > 0 && x < W && y > 0 && y < H ? 1 : 0;
      return [Math.round(x * 10) / 10, Math.round(y * 10) / 10, vis];
    });
  }
  return out;
}

const anchors = {};
let fake = false;
for (const [id, a] of Object.entries(ANCH)) if (isScreen(a)) anchors[id] = screenTrack(id, a);
const need3d = !NO_ANCHORS && Object.values(ANCH).some((a) => !isScreen(a));
if (need3d) {
  if (await exists(REAL)) {
    const J = JSON.parse(await readFile(REAL, 'utf8'));
    if (J.w !== W || J.h !== H) throw new Error(`${rel(REAL)} is ${J.w}x${J.h}, expected ${W}x${H}`);
    for (const [id, track] of Object.entries(J.anchors || {})) {
      if (track.length !== N) throw new Error(`${rel(REAL)}: anchor ${id} has ${track.length} frames, timeline has ${N}`);
      if (ANCH[id] && !isScreen(ANCH[id])) anchors[id] = track;
    }
    const miss = Object.entries(ANCH).filter(([id, a]) => !isScreen(a) && !anchors[id]).map(([id]) => id);
    if (miss.length) console.warn(`render2d: ${rel(REAL)} has no track for ${miss.join(', ')}; their callouts never show`);
    console.log(`render2d: anchors from ${rel(REAL)}${flag('fake') ? ' (--fake ignored: the real file exists)' : ''}`);
  } else if (flag('fake')) {
    Object.assign(anchors, fakeTracks());
    fake = true;
    await mkdir(path.dirname(FAKE_PATH), { recursive: true });
    await writeFile(FAKE_PATH, JSON.stringify({ fmt: FMT, w: W, h: H, frames: N, fake: true, anchors }));
    console.warn(`\n${BAR}\n!! render2d: ${rel(REAL)} does not exist.\n!! Using FAKE drifting anchors (written to ${rel(FAKE_PATH)}).\n!! Callout positions in this render are placeholders: re-run once the Blender\n!! exporter has written the real file.\n${BAR}\n`);
  } else {
    console.error(`\n${BAR}\n!! render2d: ${rel(REAL)} does not exist, and the timeline has 3D anchors\n!! (${Object.entries(ANCH).filter(([, a]) => !isScreen(a)).map(([id]) => id).join(', ')}).\n!! Run the Blender anchor export for ${FMT} first, or pass --fake for placeholders.\n${BAR}\n`);
    process.exit(1);
  }
}

// --- style ----------------------------------------------------------------------
// The look is data: timeline STYLE. --style=file.json is a partial STYLE the
// page merges last (studio.js), to try a look without regenerating the timeline.
let styleOverride = null;
if (arg('style')) {
  const sp = path.resolve(arg('style'));
  styleOverride = JSON.parse(await readFile(sp, 'utf8'));
  console.log(`render2d: style from ${rel(sp)} applied over timeline STYLE (and any preset)`);
}

// --- fonts ----------------------------------------------------------------------
// Every FONTS entry that is not None is embedded as a data: URI and registered
// as a family named after its key, so a page never depends on installed or
// file:// fonts. A None entry means the system sans (studio.js falls back).
//   FONTS = { display: '/studio/assets/fonts/Display.otf', body: None }
// A plain path registers for every weight (1-1000), so asking a single-weight
// file for weight 700 uses it as is instead of a synthesised bold. The object
// form { path, weight, style, family } is also accepted (several cuts per family).
const MIME = { '.otf': 'font/otf', '.ttf': 'font/ttf', '.woff': 'font/woff', '.woff2': 'font/woff2' };
const fontFaces = [];
for (const [key, v] of Object.entries(T.FONTS || {})) {
  const d = typeof v === 'string' ? { path: v } : v || {};
  if (!d.path) continue;
  const fp = path.resolve(STUDIO, d.path);
  if (!(await exists(fp))) throw new Error(`FONTS.${key}: font file missing: ${fp}`);
  const ext = path.extname(fp).toLowerCase();
  if (!MIME[ext]) throw new Error(`FONTS.${key}: unsupported font type ${ext}`);
  const b64 = (await readFile(fp)).toString('base64');
  fontFaces.push({ key, family: d.family || key, weight: String(d.weight || '1 1000'), style: d.style || 'normal', src: `data:${MIME[ext]};base64,${b64}` });
}
// key -> family, and key -> null for the None (system sans) entries.
const fonts = Object.fromEntries(Object.keys(T.FONTS || {}).map((k) => [k, fontFaces.find((f) => f.key === k)?.family || null]));

const DATA = { fmt: FMT, w: W, h: H, tall: H > W, opaque: OPAQUE, fake, T, anchors, fonts, styleOverride };
// Runs before the page's own scripts: STUDIO is there, and STUDIO.fontsReady
// resolves once every face is decoded (studio.js boot() awaits it).
const INJECT = `window.STUDIO = ${JSON.stringify(DATA)};
window.STUDIO.fontsReady = Promise.all(${JSON.stringify(fontFaces)}.map(async (d) => {
  const f = new FontFace(d.family, 'url(' + d.src + ')', { weight: d.weight, style: d.style });
  document.fonts.add(f);
  await f.load();
}));`;

// --- workers ----------------------------------------------------------------------
const CHECKER = `html.__check{background:repeating-conic-gradient(#2b2d30 0 25%,#1f2124 0 50%) 0 0/48px 48px !important}
html.__check body{background:radial-gradient(ellipse at 50% 40%,rgba(120,90,60,.25),transparent 70%) !important}`;

async function openWorker(k) {
  const browser = await puppeteer.launch({
    headless: true,
    // --allow-file-access-from-files: file:// pages may import ES modules.
    // --disable-gpu-rasterization: GPU raster keeps per-layer raster scales
    // across frames, so a frame rendered after others differed (by a few
    // levels) from the same frame rendered alone; CPU raster has no history.
    args: ['--allow-file-access-from-files', '--disable-gpu-rasterization', '--font-render-hinting=none',
      '--force-color-profile=srgb', '--hide-scrollbars'],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.evaluateOnNewDocument(INJECT);
  await page.goto(pathToFileURL(COMP_PATH).href, { waitUntil: 'load' });
  try {
    await page.waitForFunction(() => typeof window.renderFrame === 'function', { timeout: 30000, polling: 50 });
  } catch {
    throw new Error(`${NAME}: window.renderFrame never appeared${errors.length ? `:\n  ${errors.join('\n  ')}` : ''}`);
  }
  await page.evaluate(async () => { await window.STUDIO.fontsReady; await document.fonts.ready; });
  const bad = await page.evaluate(() => [...document.fonts].filter((f) => f.status !== 'loaded').map((f) => `${f.family}:${f.status}`));
  if (bad.length) throw new Error(`${NAME}: fonts not loaded: ${bad.join(' ')}`);
  await page.addStyleTag({ content: CHECKER });
  if (k === 0) {
    const report = await page.evaluate(() => (window.renderReport ? window.renderReport() : []));
    for (const line of report) console.log(`${NAME} ${FMT}: ${line}`);
  }
  return { browser, page, errors };
}

const pad = (n) => String(n).padStart(4, '0');
const t0 = Date.now();
const ms = () => Date.now() - t0;

if (TEST) {
  const dir = path.join(STUDIO, 'reviews', '2d-test');
  await mkdir(dir, { recursive: true });
  const prefix = NAME === 'overlay' ? '' : `${NAME}-`;
  const { browser, page, errors } = await openWorker(0);
  const tl = Date.now();
  for (const fr of TEST) {
    await page.evaluate((f) => window.renderFrame(f), fr);
    const base = path.join(dir, `${prefix}${FMT}-${pad(fr)}`);
    await page.screenshot({ path: `${base}.png`, omitBackground: !OPAQUE });
    if (!OPAQUE) {
      await page.evaluate(() => document.documentElement.classList.add('__check'));
      await page.screenshot({ path: `${base}-check.png` });
      await page.evaluate(() => document.documentElement.classList.remove('__check'));
    }
  }
  await browser.close();
  if (errors.length) throw new Error(`${NAME}: page errors:\n  ${errors.join('\n  ')}`);
  console.log(`${NAME} ${FMT}: ${TEST.length} test frames -> ${rel(dir)}/${prefix}${FMT}-NNNN.png in ${(ms() / 1000).toFixed(1)} s`
    + ` (${((Date.now() - tl) / TEST.length).toFixed(0)} ms per frame)${fake ? '  [FAKE ANCHORS]' : ''}`);
} else {
  const dir = path.resolve(STUDIO, arg('out') || path.join('cache', `${OPAQUE ? 'frames2d' : 'overlay'}-${FMT}`));
  await mkdir(dir, { recursive: true });
  // The blank lives beside the folder, so `ls dir | grep -c '^[0-9]*\.png$'` == FRAMES.
  const blank = path.join(path.dirname(dir), `${path.basename(dir)}-blank.png`);
  await rm(blank, { force: true });
  if (FULL) {
    // Frames past the end from an older, longer cut would break the count.
    for (const f of await readdir(dir)) if (/^\d+\.png$/.test(f) && Number(f.slice(0, -4)) > N) await rm(path.join(dir, f));
  }
  let blankReady = null;     // the first empty frame becomes the blank, once
  const total = TO - FROM + 1;
  const every = Math.max(1, Math.round(total / 20));
  let done = 0;
  let drawn = 0;
  const K = Math.min(JOBS, total);
  const slices = Array.from({ length: K }, (_, k) => {
    const a = FROM + Math.floor((total * k) / K);
    const b = FROM + Math.floor((total * (k + 1)) / K) - 1;
    return [a, b];
  });
  const workers = await Promise.all(slices.map((_, k) => openWorker(k)));
  console.log(`${NAME} ${FMT}: frames ${FROM}-${TO} in ${K} job${K > 1 ? 's' : ''}, ${OPAQUE ? 'opaque' : 'transparent'} -> ${rel(dir)}/  (pages ready in ${(ms() / 1000).toFixed(1)} s)`);
  const tr = Date.now();
  await Promise.all(workers.map(async ({ page, errors }, k) => {
    const [a, b] = slices[k];
    for (let fr = a; fr <= b; fr++) {
      const file = path.join(dir, `${pad(fr)}.png`);
      // Unlink first: writing into a hard link would change the shared blank.
      await rm(file, { force: true });
      const any = await page.evaluate((f) => window.renderFrame(f), fr);
      if (errors.length) throw new Error(`${NAME}: page error at frame ${fr}:\n  ${errors.join('\n  ')}`);
      if (any === false) {
        if (!blankReady) blankReady = page.screenshot({ path: blank, omitBackground: !OPAQUE });
        await blankReady;
        await link(blank, file);
      } else {
        await page.screenshot({ path: file, omitBackground: !OPAQUE, optimizeForSpeed: true });
        drawn++;
      }
      done++;
      if (done % every === 0 || done === total) {
        const per = (Date.now() - tr) / done;
        console.log(`  ${String(done).padStart(String(total).length)}/${total}  ${per.toFixed(0)} ms/frame  eta ${((per * (total - done)) / 1000).toFixed(0)} s`);
      }
    }
  }));
  await Promise.all(workers.map((w) => w.browser.close()));
  const secs = ms() / 1000;
  const count = (await readdir(dir)).filter((f) => /^\d+\.png$/.test(f)).length;
  console.log(`${NAME} ${FMT}: ${total} frames (${drawn} drawn, ${total - drawn} blank) in ${secs.toFixed(1)} s,`
    + ` ${((Date.now() - tr) / total).toFixed(0)} ms/frame wall; ${count} of ${N} frames in ${rel(dir)}/${fake ? '  [FAKE ANCHORS]' : ''}`);
  if (fake) console.warn('!! render2d: these frames use FAKE anchors. Re-render once cache/anchors-' + FMT + '.json exists.');
}
