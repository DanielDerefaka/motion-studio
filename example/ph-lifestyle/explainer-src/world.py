"""The world comp: one 1920x1080 frame per film frame, from the live footage,
cut on the timeline's beats. This is the texture of the world slab.

Run with the studio venv: cache/venv/bin/python src/world.py
Writes cache/world/NNNN.jpg (the end card is laid on later by endcard.mjs).
"""
import os
import subprocess
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(__file__))
import timeline as T  # noqa: E402

FF = 'ffmpeg'
FOOT = os.path.join(T.STUDIO, 'assets', 'footage')
RAW = os.path.join(T.STUDIO, 'cache', 'frames')
OUT = os.path.join(T.STUDIO, 'cache', 'world')
FLASH = 2   # frames of exposure lift on every cut


def frames_of(slug):
    d = os.path.join(RAW, slug)
    if not os.path.isdir(d):
        os.makedirs(d)
        subprocess.run([FF, '-v', 'error', '-i', os.path.join(FOOT, f'{slug}.webm'), '-vf', f'fps={T.FPS}',
                        '-q:v', '2', os.path.join(d, '%04d.jpg')], check=True)
    return sorted(os.listdir(d))


def main():
    os.makedirs(OUT, exist_ok=True)
    cuts = T.CUTS + [(T.FRAMES + 1, None, 0, 1.0)]
    for (start, slug, offset, speed), (end, *_) in zip(cuts, cuts[1:]):
        have = frames_of(slug)
        first = int(round(offset * T.FPS))
        for fr in range(start, end):
            src = first + int((fr - start) * speed)     # speed < 1 holds frames: slow motion
            i = min(src, len(have) - 1)
            if src >= len(have):
                print(f'  {slug}: ran out at film frame {fr}, holding the last frame')
            im = Image.open(os.path.join(RAW, slug, have[i])).convert('RGB')
            if fr - start < FLASH and start > 1:
                im = ImageEnhance.Brightness(im).enhance(1.35 - 0.15 * (fr - start))
            im.save(os.path.join(OUT, f'{fr:04d}.jpg'), quality=94)
        print(f'{slug:12s} frames {start}-{end - 1} from {offset:.1f}s at {speed}x')


if __name__ == '__main__':
    main()
