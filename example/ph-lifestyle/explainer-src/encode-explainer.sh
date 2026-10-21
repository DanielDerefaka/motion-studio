#!/bin/sh
# Frames + captions and callouts + voice and music -> the explainer film.
# The picture fades from the fade event (f(48.6), 29.17 s) to black;
# sound.wav already carries its own fade. The first film keeps encode.sh.
# Usage: sh src/encode-explainer.sh 16x9|9x16
set -e
cd "$(dirname "$0")/.."
FMT=${1:-16x9}
FRAMES=out/explainer/frames-$FMT
OVERLAY=cache/overlay-$FMT
N=$(python3 -c "import json; print(json.load(open('src/timeline.json'))['FRAMES'])")
FADE=$(python3 -c "import json; t=json.load(open('src/timeline.json')); f=next(e['f'] for e in t['EVENTS'] if e['kind']=='fade'); print(round((f-1)/30, 3), round((t['FRAMES']-f+1)/30, 3))")
[ "$(ls $FRAMES | wc -l)" -eq "$N" ] || { echo "$FRAMES: not all $N frames"; exit 1; }
[ "$(ls $OVERLAY | grep -c '^[0-9]*\.png$')" -eq "$N" ] || { echo "$OVERLAY: not all $N frames"; exit 1; }
set -- $FADE
ffmpeg -y -v error -framerate 30 -i "$FRAMES/%04d.png" -framerate 30 -i "$OVERLAY/%04d.png" \
  -i out/explainer/sound.wav \
  -filter_complex "[0][1]overlay=0:0:format=auto,fade=t=out:st=$1:d=$2,format=yuv420p[v]" \
  -map "[v]" -map 2:a -c:v libx264 -preset slow -crf 17 -profile:v high -movflags +faststart \
  -c:a aac -b:a 320k -shortest "out/ph-lifestyle-explainer-$FMT.mp4"
# Poster: the end card with Tobi dancing beside it.
ffmpeg -y -v error -i "$FRAMES/0850.png" -i "$OVERLAY/0850.png" \
  -filter_complex "[0][1]overlay=0:0" -q:v 2 "out/explainer/poster-$FMT.jpg"
echo "out/ph-lifestyle-explainer-$FMT.mp4"
