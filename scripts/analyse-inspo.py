#!/usr/bin/env python3
"""Measure an inspiration: a video, GIF, image, folder of them, or a link.

    python3 -I analyse-inspo.py <file|folder|url> [out_dir]

Writes, per input, into out_dir (default inspo/analysis/<name>/):
  analysis.md      the numbers in words: format, shots, rhythm, motion, palette, audio
  analysis.json    the same, for timeline.py
  sheet.jpg        uniform contact sheet (6 x rows), timestamps burnt in
  shots.jpg        first / middle / last frame of every shot
  shots/NNN-*.png  those frames at full size, to read type and layout
  palette.png      the palette with shares
  motion.png       motion energy over time, cuts and beats marked
Needs ffmpeg, numpy and pillow (the studio venv has them); yt-dlp for links.

The numbers are evidence for the look recipe, not the recipe: always look at
the sheets and step through the signature moves frame by frame afterwards.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

VIDEO = {'.mp4', '.mov', '.webm', '.mkv', '.m4v', '.gif', '.avi'}
IMAGE = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
AW = 320                      # analysis width (px)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, check=True, **kw)


def probe(path):
    out = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]).stdout
    info = json.loads(out)
    v = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    a = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    num, den = (v.get('avg_frame_rate') or v.get('r_frame_rate') or '30/1').split('/')
    fps = float(num) / float(den) if float(den) else 30.0
    if not 1 <= fps <= 240:
        num, den = v.get('r_frame_rate', '30/1').split('/')
        fps = float(num) / float(den)
    dur = float(info['format'].get('duration') or v.get('duration') or 0)
    return dict(w=int(v['width']), h=int(v['height']), fps=round(fps, 3), duration=round(dur, 3),
                has_audio=a is not None, codec=v.get('codec_name'))


def frames(path, fps, w, h):
    """All frames at `fps`, scaled to AW wide, as uint8 [n, ah, AW, 3]."""
    ah = max(2, int(round(h * AW / w / 2)) * 2)
    raw = run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={AW}:{ah}:flags=area',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, ah, AW, 3)


def cuts_ffmpeg(path, thr=0.3):
    """Hard cuts at native frame rate from ffmpeg's scene score."""
    p = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-vf', f"select='gt(scene,{thr})',showinfo",
                        '-an', '-f', 'null', '-'], capture_output=True, text=True)
    return [round(float(t), 3) for t in re.findall(r'pts_time:([0-9.]+)', p.stderr)]


def cuts_spikes(path, fps):
    """Cuts the scene score misses: one frame that differs far more than its
    neighbours (a subject swapped on the same backdrop, a fast push into a new
    shot). Native frame rate, 64x36 grey; steady camera moves don't spike."""
    raw = run(['ffmpeg', '-v', 'error', '-i', path, '-an', '-vf', 'scale=64:36,format=gray',
               '-f', 'rawvideo', '-']).stdout
    g = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64).astype(np.float32)
    if len(g) < 16:
        return []
    d = np.r_[0, np.abs(np.diff(g, axis=0)).mean((1, 2))]
    out = []
    for i in range(1, len(d)):
        nb = np.r_[d[max(1, i - 7):i], d[i + 1:i + 8]]
        if len(nb) and d[i] > 3 and d[i] > 6 * (np.median(nb) + 0.3):
            out.append(round(i / (fps or 30), 3))
    return out


def merge_cuts(hard, soft, fps):
    """Hard cuts win; a soft cut within 3 frames of another cut is the same one."""
    tol = 3 / (fps or 30)
    allc = sorted([(t, 'hard') for t in hard] + [(t, 'soft') for t in soft])
    out = []
    for t, k in allc:
        if out and t - out[-1][0] <= tol:
            if k == 'hard' and out[-1][1] == 'soft':
                out[-1] = (t, k)
            continue
        out.append((t, k))
    return out


def hexc(c):
    return '#%02x%02x%02x' % tuple(int(x) for x in c)


def palette(px, k=8, iters=12, seed=7):
    """k-means in RGB on sampled pixels -> [(hex, share, rgb)], biggest first."""
    rng = np.random.default_rng(seed)
    px = px.reshape(-1, 3).astype(np.float32)
    if len(px) > 60000:
        px = px[rng.choice(len(px), 60000, replace=False)]
    cen = px[rng.choice(len(px), k, replace=False)]
    for _ in range(iters):
        lab = ((px[:, None, :] - cen[None]) ** 2).sum(-1).argmin(1)
        for i in range(k):
            m = px[lab == i]
            if len(m):
                cen[i] = m.mean(0)
    share = np.bincount(lab, minlength=k) / len(px)
    order = np.argsort(-share)
    return [(hexc(cen[i]), round(float(share[i]), 3), cen[i].tolist()) for i in order if share[i] > 0.004]


def tone(px):
    f = px.reshape(-1, 3).astype(np.float32) / 255
    lum = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = f.max(1), f.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return dict(luma_mean=round(float(lum.mean()), 3), luma_p5=round(float(np.percentile(lum, 5)), 3),
                luma_p95=round(float(np.percentile(lum, 95)), 3), sat_mean=round(float(sat.mean()), 3),
                key='dark' if lum.mean() < 0.35 else 'light' if lum.mean() > 0.65 else 'mid')


def shift(a, b):
    """Global translation a -> b by phase correlation (analysis px)."""
    fa, fb = np.fft.fft2(a), np.fft.fft2(b)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    c = np.abs(np.fft.ifft2(r))
    y, x = np.unravel_index(c.argmax(), c.shape)
    h, w = a.shape
    return (x - w if x > w // 2 else x), (y - h if y > h // 2 else y), float(c.max())


def motion(fr, afps, cuts):
    """Per-frame motion energy, the moves between holds and their ease shape."""
    g = fr.astype(np.float32).mean(-1)
    e = np.r_[0, np.abs(np.diff(g, axis=0)).mean((1, 2))]
    cut_i = {int(round(t * afps)) for t in cuts}
    for i in cut_i:                                 # a cut is not motion
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(e):
                e[j] = np.nan
    ok = e[~np.isnan(e)]
    if not len(ok):
        return dict(energy=[], moves=[], hold_share=1.0)
    hold = max(0.6, float(np.percentile(ok, 30)) * 1.6)
    moving = np.nan_to_num(e, nan=0) > hold
    moves, i = [], 0
    while i < len(e):
        if moving[i]:
            j = i
            while j + 1 < len(e) and moving[j + 1]:
                j += 1
            seg = np.nan_to_num(e[i:j + 1])
            if j - i + 1 >= 2:
                peak = float(np.argmax(seg)) / max(1, len(seg) - 1)
                shape = ('ease-out (fast start, long settle)' if peak < 0.34 else
                         'ease-in (slow start, fast end)' if peak > 0.66 else 'ease-in-out')
                dx = dy = 0.0
                for k in range(i, j):
                    sx, sy, _ = shift(g[k], g[k + 1])
                    dx += sx
                    dy += sy
                moves.append(dict(t0=round(i / afps, 2), t1=round((j + 1) / afps, 2),
                                  secs=round((j - i + 1) / afps, 2), peak_at=round(peak, 2), shape=shape,
                                  energy=round(float(seg.max()), 2),
                                  pan_px=[round(dx * 1920 / AW), round(dy * 1920 / AW)]))
            i = j + 1
        else:
            i += 1
    return dict(energy=[None if np.isnan(x) else round(float(x), 2) for x in e],
                hold_threshold=round(hold, 2), hold_share=round(float(1 - moving.mean()), 3), moves=moves)


def audio(path, dur):
    sr = 22050
    raw = run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']).stdout
    x = np.frombuffer(raw, np.float32)
    if not len(x) or np.abs(x).max() < 1e-4:
        return dict(silent=True)
    hop, win = 512, 2048
    n = 1 + (len(x) - win) // hop
    if n < 8:
        return dict(silent=True)
    idx = np.arange(win)[None] + hop * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * np.hanning(win), axis=1))
    flux = np.r_[0, np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(1)]
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    fr = sr / hop
    # tempo: autocorrelation of the onset curve, 60-180 BPM, prefer 90-150
    ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
    lags = np.arange(len(ac))
    bpms = 60 * fr / np.maximum(lags, 1)
    band = (bpms >= 60) & (bpms <= 180)
    wgt = np.exp(-0.5 * ((np.log2(np.maximum(bpms, 1)) - np.log2(118)) / 0.6) ** 2)
    lag = int(lags[band][np.argmax((ac * wgt)[band])]) if band.any() else 0
    # refine to a fractional lag: the 1st-8th multiples of the period together
    # pin it far finer than one hop (128 vs 129.2 BPM)
    def comb(L, k=8):
        m = np.arange(1, k + 1) * L
        m = m[m < len(ac) - 1]
        return float(np.interp(m, lags, ac).sum()) if len(m) else 0.0
    if lag:
        cand = np.arange(lag - 1, lag + 1.001, 0.01)
        lag = float(cand[np.argmax([comb(L) for L in cand])])
    bpm = round(60 * fr / lag, 1) if lag else None
    # the other octave, when the onsets support it nearly as well
    alt = None
    if lag:
        for L in (lag / 2, lag * 2):
            b = 60 * fr / L
            if L > lag and bpm < 150:      # half time always fits a steady beat; offer it only for fast ones
                continue
            if 50 <= b <= 200 and L * 4 < len(ac) and comb(L, 4) >= 0.6 * comb(lag, 4):
                alt = round(b, 1)
                break
    # beat phase: the offset that collects the most onset strength
    beats = []
    if lag:
        nb = int((len(flux) - 1) / lag)
        def at(ph):
            i = np.round(ph + lag * np.arange(nb + 1)).astype(int)
            return i[i < len(flux)]
        ph = max(np.arange(0, lag, 0.25), key=lambda p: flux[at(p)].sum())
        beats = [round(i / fr, 3) for i in at(ph)]
    peaks = [i for i in range(1, len(flux) - 1)
             if flux[i] > 1.5 and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    onsets = [round(i / fr, 3) for i in peaks]
    half = int(sr * 0.5)
    loud = [round(max(-90.0, float(20 * np.log10(np.sqrt((x[i:i + half] ** 2).mean()) + 1e-9))), 1)
            for i in range(0, len(x) - half // 2, half)]
    return dict(silent=False, bpm=bpm, bpm_other_octave=alt, beat_secs=round(60 / bpm, 3) if bpm else None, beats=beats,
                onsets=onsets, rms_dbfs_per_half_second=loud,
                peak_dbfs=round(float(20 * np.log10(np.abs(x).max() + 1e-9)), 1))


def on_grid(times, grid, tol=0.07):
    if not times or not grid:
        return None
    g = np.array(grid)
    return round(float(np.mean([np.abs(g - t).min() <= tol for t in times])), 2)


def grab(path, t, dst):
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t):.3f}', '-i', path, '-frames:v', '1', dst])


def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 8 + 7 * len(text), 16], fill=(0, 0, 0))
    d.text((4, 2), text, fill=(255, 255, 0))
    return img


def tile(images, cols, cell_w, dst):
    if not images:
        return
    cell_h = int(images[0].height * cell_w / images[0].width)
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell_w + (cols + 1) * 4, rows * cell_h + (rows + 1) * 4), (20, 20, 20))
    for i, im in enumerate(images):
        im = im.convert('RGB').resize((cell_w, cell_h), Image.LANCZOS)
        sheet.paste(im, (4 + (i % cols) * (cell_w + 4), 4 + (i // cols) * (cell_h + 4)))
    sheet.save(dst, quality=88)


def palette_png(pal, dst):
    W, H = 900, 120
    im = Image.new('RGB', (W, H + 22), (255, 255, 255))
    d = ImageDraw.Draw(im)
    x = 0
    for hx, share, rgb in pal:
        w = max(40, int(W * share))
        d.rectangle([x, 0, x + w, H], fill=tuple(int(c) for c in rgb))
        d.text((x + 3, H + 4), f'{hx} {share:.0%}', fill=(0, 0, 0))
        x += w
    im.crop((0, 0, max(x, 1), H + 22)).save(dst)


def motion_png(m, afps, cuts, beats, dur, dst):
    e = [0 if v is None else v for v in m['energy']]
    W, H = 1200, 260
    im = Image.new('RGB', (W, H), (16, 16, 18))
    d = ImageDraw.Draw(im)
    top = max(e + [1])
    X = lambda t: int(t / max(dur, 1e-6) * (W - 1))
    for b in beats:
        d.line([X(b), H - 14, X(b), H], fill=(90, 90, 110))
    for mv in m['moves']:
        d.rectangle([X(mv['t0']), 0, X(mv['t1']), H - 16], fill=(28, 40, 34))
    pts = [(X(i / afps), H - 16 - int(v / top * (H - 30))) for i, v in enumerate(e)]
    if len(pts) > 1:
        d.line(pts, fill=(120, 230, 160), width=2)
    for c in cuts:
        d.line([X(c), 0, X(c), H - 16], fill=(255, 90, 90), width=2)
    d.text((6, 4), 'motion energy (green), moves (shaded), cuts (red), beats (ticks)', fill=(200, 200, 200))
    im.save(dst)


def analyse_video(path, out):
    info = probe(path)
    dur = info['duration'] or 1
    afps = 10 if dur <= 90 else max(2, int(900 / dur))
    fr = frames(path, afps, info['w'], info['h'])
    kinds = [(t, k) for t, k in merge_cuts(cuts_ffmpeg(path), cuts_spikes(path, info['fps']), info['fps'])
             if 0.05 < t < dur - 0.05]
    cuts = [t for t, _ in kinds]
    kind_at = dict(kinds)
    bounds = [0.0] + cuts + [dur]
    spans = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 0.04]
    shots = [dict(n=i + 1, t0=round(a, 2), t1=round(b, 2), secs=round(b - a, 2),
                  cut_in=kind_at.get(a, 'start'))
             for i, (a, b) in enumerate(spans)]
    m = motion(fr, afps, cuts)
    au = audio(path, dur) if info['has_audio'] else dict(silent=True)
    pal = palette(fr[::max(1, len(fr) // 60)])
    border = np.concatenate([fr[:, :3].reshape(-1, 3), fr[:, -3:].reshape(-1, 3),
                             fr[:, :, :3].reshape(-1, 3), fr[:, :, -3:].reshape(-1, 3)])
    lens = [s['secs'] for s in shots]
    res = dict(source=os.path.abspath(path), **info,
               aspect=f"{info['w']}:{info['h']}" if info['w'] and info['h'] else None,
               shots=shots, cuts=cuts, soft_cuts=[t for t, k in kinds if k == 'soft'], cuts_per_second=round(len(cuts) / dur, 2),
               shot_secs=dict(mean=round(float(np.mean(lens)), 2), median=round(float(np.median(lens)), 2),
                              min=round(min(lens), 2), max=round(max(lens), 2)),
               palette=[dict(hex=h, share=s) for h, s, _ in pal], background=hexc(np.median(border, 0)),
               tone=tone(fr[::max(1, len(fr) // 60)]),
               motion={k: v for k, v in m.items() if k != 'energy'}, audio=au)
    if not au.get('silent'):
        res['cuts_on_beat'] = on_grid(cuts, au['beats'])
        res['move_starts_on_beat'] = on_grid([mv['t0'] for mv in m['moves']], au['beats'], 0.1)
    # pictures
    os.makedirs(os.path.join(out, 'shots'), exist_ok=True)
    shot_imgs = []
    for s in shots:
        for tag, t in (('a', s['t0'] + 0.04), ('m', (s['t0'] + s['t1']) / 2), ('z', s['t1'] - 0.06)):
            dst = os.path.join(out, 'shots', f"{s['n']:03d}-{tag}-{t:06.2f}s.png")
            grab(path, t, dst)
            if os.path.exists(dst):
                shot_imgs.append(label(Image.open(dst).convert('RGB').resize((480, int(480 * info['h'] / info['w']))),
                                       f"shot {s['n']} {tag} {t:.2f}s"))
    tile(shot_imgs, 3, 480, os.path.join(out, 'shots.jpg'))
    n = min(36, max(12, int(dur * 2)))
    uni = []
    for i in range(n):
        k = min(len(fr) - 1, int(i * len(fr) / n))
        uni.append(label(Image.fromarray(fr[k]), f'{k / afps:.2f}s'))
    tile(uni, 6, 320, os.path.join(out, 'sheet.jpg'))
    palette_png(pal, os.path.join(out, 'palette.png'))
    motion_png(m, afps, cuts, au.get('beats', []), dur, os.path.join(out, 'motion.png'))
    return res


def analyse_image(path, out):
    im = Image.open(path).convert('RGB')
    a = np.asarray(im.resize((AW, max(2, int(im.height * AW / im.width)))))
    pal = palette(a)
    os.makedirs(out, exist_ok=True)
    palette_png(pal, os.path.join(out, 'palette.png'))
    shutil.copy(path, os.path.join(out, 'still' + os.path.splitext(path)[1].lower()))
    return dict(source=os.path.abspath(path), still=True, w=im.width, h=im.height,
                palette=[dict(hex=h, share=s) for h, s, _ in pal], tone=tone(a))


def write_md(r, dst):
    L = [f"# Inspo analysis: {os.path.basename(r['source'])}", '']
    if r.get('still'):
        L += [f"Still, {r['w']}x{r['h']}. Tone: {r['tone']}.", '', 'Palette: ' +
              ', '.join(f"{p['hex']} {p['share']:.0%}" for p in r['palette'])]
        open(dst, 'w').write('\n'.join(L) + '\n')
        return
    m, au = r['motion'], r['audio']
    L += [f"- **Format:** {r['w']}x{r['h']} ({r['aspect']}), {r['fps']} fps, {r['duration']} s, {r['codec']}",
          f"- **Shots:** {len(r['shots'])}; {r['cuts_per_second']} cuts/s; shot length mean {r['shot_secs']['mean']} s, "
          f"median {r['shot_secs']['median']} s, range {r['shot_secs']['min']}-{r['shot_secs']['max']} s; "
          f"{len(r.get('soft_cuts', []))} soft cuts (same backdrop, subject swapped, or a fast push: step through them)",
          f"- **Motion:** holds {m['hold_share']:.0%} of the time; {len(m['moves'])} moves",
          f"- **Tone:** {r['tone']['key']} key, luma mean {r['tone']['luma_mean']}, "
          f"p5-p95 {r['tone']['luma_p5']}-{r['tone']['luma_p95']}, saturation {r['tone']['sat_mean']}",
          f"- **Background (frame edges):** {r['background']}",
          '- **Palette:** ' + ', '.join(f"{p['hex']} {p['share']:.0%}" for p in r['palette'])]
    if au.get('silent'):
        L.append('- **Audio:** none or silent')
    else:
        L.append(f"- **Audio:** ~{au['bpm']} BPM (beat {au['beat_secs']} s"
                 + (f"; or ~{au['bpm_other_octave']} BPM, listen to decide" if au.get('bpm_other_octave') else '') + "), "
                 f"{len(au['onsets'])} strong onsets, "
                 f"peak {au['peak_dbfs']} dBFS; cuts on the beat {r.get('cuts_on_beat')}, "
                 f"move starts on the beat {r.get('move_starts_on_beat')}")
        lo = au['rms_dbfs_per_half_second']
        if len(lo) > 80:     # long films: per 2 s, the half-second list stays in analysis.json
            lo = [round(float(np.mean(lo[i:i + 4])), 1) for i in range(0, len(lo), 4)]
            L.append(f"- **Loudness per 2 s (RMS dBFS):** {lo}")
        else:
            L.append(f"- **Loudness per half second (RMS dBFS):** {lo}")
    L += ['', '## Shots', '', '| # | start | end | secs | cut in |', '|---|---|---|---|---|']
    L += [f"| {s['n']} | {s['t0']} | {s['t1']} | {s['secs']} | {s.get('cut_in', '')} |" for s in r['shots']]
    L += ['', '## Moves (between holds)', '', '| start | end | secs | ease shape | pan px (1920 scale) |',
          '|---|---|---|---|---|']
    L += [f"| {v['t0']} | {v['t1']} | {v['secs']} | {v['shape']} | {v['pan_px']} |" for v in m['moves'][:60]]
    L += ['', 'Ease shape comes from where the motion energy peaks inside each move; pan is the',
          'global shift (camera/whole-frame move), ~0 for moves inside a still frame.',
          'Next: look at sheet.jpg, shots.jpg and motion.png, then step through 2-3 signature',
          'moves at native fps (reference/inspo.md, "Frame-step the signature moves").']
    open(dst, 'w').write('\n'.join(L) + '\n')


def fetch(url, out):
    if not shutil.which('yt-dlp'):
        sys.exit('yt-dlp is not installed: download the video by hand into inspo/ and pass the file')
    os.makedirs(out, exist_ok=True)
    run(['yt-dlp', '-q', '--no-playlist', '-f', 'bv*[height<=1080]+ba/b[height<=1080]/b',
         '--merge-output-format', 'mp4', '-o', os.path.join(out, 'source.%(ext)s'), url])
    got = [f for f in os.listdir(out) if f.startswith('source.')]
    if not got:
        sys.exit(f'yt-dlp found no video at {url}')
    return os.path.join(out, got[0])


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else os.path.join('inspo', 'analysis')
    if re.match(r'https?://', src):
        name = re.sub(r'[^a-zA-Z0-9]+', '-', src.split('//', 1)[1])[:60].strip('-')
        src = fetch(src, os.path.join('inspo', 'downloads', name))
    items = ([os.path.join(src, f) for f in sorted(os.listdir(src))
              if os.path.splitext(f)[1].lower() in VIDEO | IMAGE] if os.path.isdir(src) else [src])
    for p in items:
        name = re.sub(r'[^a-zA-Z0-9]+', '-', os.path.splitext(os.path.basename(p))[0]).strip('-') or 'inspo'
        out = os.path.join(base, name) if len(sys.argv) <= 2 or len(items) > 1 else base
        os.makedirs(out, exist_ok=True)
        ext = os.path.splitext(p)[1].lower()
        r = analyse_image(p, out) if ext in IMAGE else analyse_video(p, out)
        json.dump(r, open(os.path.join(out, 'analysis.json'), 'w'), indent=1)
        write_md(r, os.path.join(out, 'analysis.md'))
        print(f'{p} -> {out}/analysis.md')


if __name__ == '__main__':
    main()
