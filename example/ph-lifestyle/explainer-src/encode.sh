#!/bin/sh
# Frames + sound -> the film. The picture fades from the fade event (f(26.5),
# 15.0 s) to black; sound.wav already carries its own fade.
# Usage: sh src/encode.sh 16x9|9x16
set -e
cd "$(dirname "$0")/.."
FMT=${1:-16x9}
FRAMES=out/frames
[ "$FMT" = 9x16 ] && FRAMES=out/frames-9x16
[ "$(ls $FRAMES | wc -l)" -eq 504 ] || { echo "$FRAMES: not all 504 frames"; exit 1; }
ffmpeg -y -v error -framerate 30 -i "$FRAMES/%04d.png" -i out/sound.wav \
  -vf "fade=t=out:st=15.0:d=1.8,format=yuv420p" \
  -c:v libx264 -preset slow -crf 17 -profile:v high -movflags +faststart \
  -c:a aac -b:a 320k -shortest "out/ph-lifestyle-$FMT.mp4"
# Poster: the end card with Tobi dancing beside it.
ffmpeg -y -v error -i "$FRAMES/0450.png" -q:v 2 "out/poster-$FMT.jpg"
echo "out/ph-lifestyle-$FMT.mp4"
