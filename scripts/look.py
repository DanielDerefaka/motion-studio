#!/usr/bin/env python3
"""Look closely: frame-step a move, or put the inspo beside our film.

    python3 -I look.py step <video> <t0> <t1> [--every=1] [--cols=6] [--out=x.jpg]
        every native frame from t0 to t1 (seconds) in one labelled sheet:
        read the easing, overshoot, blur, stagger and order of a signature move.

    python3 -I look.py compare <inspo> <ours> [--n=8] [--pairs=0.5:0.4,2.1:1.9] [--out=x.jpg]
        rows of [inspo | ours]: at the same relative times (--n), or at the
        timestamp pairs you give (inspo:ours), e.g. the same beat in both.

Needs ffmpeg and pillow (the studio venv).
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw


def opts(argv):
    pos, kw = [], {}
    for a in argv:
        if a.startswith('--') and '=' in a:
            k, v = a[2:].split('=', 1)
            kw[k] = v
        else:
            pos.append(a)
    return pos, kw


def info(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate:format=duration', '-of', 'json', path],
                         capture_output=True, check=True).stdout
    j = json.loads(out)
    s = j['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return int(s['width']), int(s['height']), float(n) / float(d), float(j['format']['duration'])


def frame(path, t, w):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t):.4f}', '-i', path, '-frames:v', '1',
                          '-vf', f'scale={w}:-2', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                         capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert('RGB')


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 10 + 7 * len(text), 16], fill=(0, 0, 0))
    d.text((5, 2), text, fill=(255, 255, 0))
    return im


def sheet(cells, cols, dst):
    cw, ch = cells[0].size
    rows = (len(cells) + cols - 1) // cols
    out = Image.new('RGB', (cols * cw + (cols + 1) * 4, rows * ch + (rows + 1) * 4), (18, 18, 18))
    for i, c in enumerate(cells):
        out.paste(c.resize((cw, ch)), (4 + (i % cols) * (cw + 4), 4 + (i // cols) * (ch + 4)))
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    out.save(dst, quality=90)
    print(f'{dst} ({len(cells)} cells, {cols} cols)')


def step(video, t0, t1, every=1, cols=6, out=None):
    w, h, fps, dur = info(video)
    t0, t1 = float(t0), min(float(t1), dur)
    n0, n1 = int(round(t0 * fps)), int(round(t1 * fps))
    cells = []
    for n in range(n0, n1 + 1, int(every)):
        cells.append(label(frame(video, n / fps + 0.5 / fps, 360), f'f{n + 1} {n / fps:.2f}s'))
    if len(cells) > 72:
        print(f'warning: {len(cells)} frames; use --every=2 or a shorter range')
    stem = os.path.splitext(os.path.basename(video))[0]
    sheet(cells, int(cols), out or f'reviews/step-{stem}-{t0:.2f}-{t1:.2f}.jpg')


def compare(inspo, ours, n=8, pairs=None, out=None):
    _, _, _, d1 = info(inspo)
    _, _, _, d2 = info(ours)
    if pairs:
        ts = [tuple(float(x) for x in p.split(':')) for p in pairs.split(',')]
    else:
        n = int(n)
        ts = [((i + 0.5) / n * d1, (i + 0.5) / n * d2) for i in range(n)]
    cells = []
    for a, b in ts:
        A, B = frame(inspo, a, 480), frame(ours, b, 480)
        # same cell height: letterbox the narrower one
        H = max(A.height, B.height)
        for im, t, who in ((A, a, 'inspo'), (B, b, 'ours')):
            c = Image.new('RGB', (480, H), (0, 0, 0))
            c.paste(im, (0, (H - im.height) // 2))
            cells.append(label(c, f'{who} {t:.2f}s'))
    sheet(cells, 2, out or 'reviews/compare.jpg')


def main():
    pos, kw = opts(sys.argv[1:])
    if not pos:
        sys.exit(__doc__)
    if pos[0] == 'step' and len(pos) == 4:
        step(*pos[1:], every=kw.get('every', 1), cols=kw.get('cols', 6), out=kw.get('out'))
    elif pos[0] == 'compare' and len(pos) == 3:
        compare(*pos[1:], n=kw.get('n', 8), pairs=kw.get('pairs'), out=kw.get('out'))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
