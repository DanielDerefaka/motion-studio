#!/bin/sh
# One picture of the whole film: N evenly spaced frames tiled, each labelled
# by the grid order (read the time as index * duration / N). Look at this, not
# the frames one by one, to find the three worst defects.
#
#   sh src/contact-sheet.sh out/film-16x9.mp4 [reviews/sheet.jpg] [cols] [rows]
#   sh src/contact-sheet.sh out/frames-16x9    [reviews/sheet.jpg] [cols] [rows]
set -e
cd "$(dirname "$0")/.."
SRC=$1
OUT=${2:-reviews/sheet.jpg}
COLS=${3:-6}
ROWS=${4:-4}
FF=$(command -v ffmpeg || echo /opt/homebrew/bin/ffmpeg)
mkdir -p "$(dirname "$OUT")"
K=$((COLS * ROWS))
if [ -d "$SRC" ]; then
  N=$(ls "$SRC" | grep -c '^[0-9]*\.png$')
  STEP=$(( (N + K - 1) / K ))
  "$FF" -y -v error -framerate 30 -i "$SRC/%04d.png" \
    -vf "select='not(mod(n\,$STEP))',scale=480:-1,tile=${COLS}x${ROWS}:padding=6:color=black" -frames:v 1 -q:v 3 "$OUT"
else
  D=$("$(dirname "$FF")/ffprobe" -v error -show_entries format=duration -of csv=p=0 "$SRC")
  "$FF" -y -v error -i "$SRC" \
    -vf "fps=$K/$D,scale=480:-1,tile=${COLS}x${ROWS}:padding=6:color=black" -frames:v 1 -q:v 3 "$OUT"
fi
echo "$OUT ($K frames, ${COLS}x${ROWS})"
