"""The world comp: one frame per film frame from the recorded footage, cut on
the timeline's beats (T.CUTS). This is the texture of the base slab (or the
background of a 2D film).

    cache/venv/bin/python src/world.py
Writes cache/world/NNNN.jpg at the UI size (T.W x T.H).
"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402

FF = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
FOOT = os.path.join(T.STUDIO, 'assets', 'footage')
RAW = os.path.join(T.STUDIO, 'cache', 'frames')
OUT = os.path.join(T.STUDIO, 'cache', 'world')
FLASH = 2   # frames of exposure lift on every cut


def frames_of(slug):
    d = os.path.join(RAW, slug)
    if not os.path.isdir(d):
        os.makedirs(d)
        subprocess.run([FF, '-v', 'error', '-i', os.path.join(FOOT, f'{slug}.webm'),
                        '-vf', f'fps={T.FPS},scale={T.W}:{T.H}', '-q:v', '2', os.path.join(d, '%04d.jpg')], check=True)
    return sorted(os.listdir(d))


def main():
    os.makedirs(OUT, exist_ok=True)
    cuts = T.CUTS + [(T.FRAMES + 1, None, 0, 1.0)]
    short = []
    for (start, slug, offset, speed), (end, *_) in zip(cuts, cuts[1:]):
        have = frames_of(slug)
        first = int(round(offset * T.FPS))
        for fr in range(start, end):
            src = first + int((fr - start) * speed)     # speed < 1 holds frames: slow motion
            if src >= len(have):
                short.append((slug, fr))
            im = Image.open(os.path.join(RAW, slug, have[min(src, len(have) - 1)])).convert('RGB')
            if fr - start < FLASH and start > 1:
                im = ImageEnhance.Brightness(im).enhance(1.35 - 0.15 * (fr - start))
            im.save(os.path.join(OUT, f'{fr:04d}.jpg'), quality=94)
        print(f'{slug:14s} frames {start}-{end - 1} from {offset:.1f}s at {speed}x')
    # A clip that runs out holds its last frame: visible as a freeze. Fix the
    # offset or the speed in T.CUTS rather than accept it.
    for slug in dict.fromkeys(s for s, _ in short):
        frs = [fr for s, fr in short if s == slug]
        print(f'  {slug}: RAN OUT at film frames {frs[0]}-{frs[-1]} ({len(frs)} frozen frames): '
              f'record it longer or lower its offset/speed in T.CUTS')


if __name__ == '__main__':
    main()
