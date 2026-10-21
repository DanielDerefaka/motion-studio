#!/bin/sh
# Frames (+ optional transparent overlay) + sound -> the delivered film.
# Reads FRAMES, FPS, NAME and the fade event from src/timeline.json, refuses
# to encode a half-rendered folder, and pulls a poster frame.
#
#   sh src/encode.sh 16x9 [poster_frame]
#
# Inputs:  out/frames-<fmt>/NNNN.png   (Blender or the 2D renderer)
#          cache/overlay-<fmt>/NNNN.png (optional: captions/callouts over 3D)
#          out/sound.wav                (optional: sound.py)
# Output:  out/<NAME>-<fmt>.mp4, out/poster-<fmt>.jpg
set -e
cd "$(dirname "$0")/.."
FMT=${1:-16x9}
FF=$(command -v ffmpeg || echo /opt/homebrew/bin/ffmpeg)
FRAMES=out/frames-$FMT
OVERLAY=cache/overlay-$FMT
SOUND=out/sound.wav
read N FPS NAME FADE_ST FADE_D <<EOT
$(python3 -I -c "
import json; t = json.load(open('src/timeline.json'))
fps = t['FPS']; n = t['FRAMES']
f = next((e['f'] for e in t.get('EVENTS', []) if e['kind'] == 'fade'), None)
st, d = (round((f - 1) / fps, 3), round((n - f + 1) / fps, 3)) if f else (0, 0)
print(n, fps, t['NAME'], st, d)")
EOT
POSTER=${2:-$(( N * 9 / 10 ))}
POSTER=$(printf %04d "$POSTER")

count() { ls "$1" 2>/dev/null | grep -c '^[0-9]*\.png$' || true; }
[ "$(count "$FRAMES")" -eq "$N" ] || { echo "$FRAMES: $(count "$FRAMES") of $N frames"; exit 1; }

INPUTS="-framerate $FPS -i $FRAMES/%04d.png"
CHAIN="[0]"
if [ -d "$OVERLAY" ]; then
  [ "$(count "$OVERLAY")" -eq "$N" ] || { echo "$OVERLAY: $(count "$OVERLAY") of $N frames"; exit 1; }
  INPUTS="$INPUTS -framerate $FPS -i $OVERLAY/%04d.png"
  CHAIN="[0][1]overlay=0:0:format=auto,"
else
  CHAIN="[0]"
fi
FADE=""
[ "$FADE_D" != "0" ] && FADE="fade=t=out:st=$FADE_ST:d=$FADE_D,"
AUDIO=""
if [ -f "$SOUND" ]; then
  A=$([ -d "$OVERLAY" ] && echo 2 || echo 1)
  INPUTS="$INPUTS -i $SOUND"
  AUDIO="-map $A:a -c:a aac -b:a 320k -shortest"
fi
OUT="out/$NAME-$FMT.mp4"
# shellcheck disable=SC2086
"$FF" -y -v error $INPUTS -filter_complex "${CHAIN}${FADE}format=yuv420p[v]" -map "[v]" $AUDIO \
  -c:v libx264 -preset slow -crf 17 -profile:v high -pix_fmt yuv420p -movflags +faststart "$OUT"
if [ -d "$OVERLAY" ]; then
  "$FF" -y -v error -i "$FRAMES/$POSTER.png" -i "$OVERLAY/$POSTER.png" -filter_complex "[0][1]overlay=0:0" -q:v 2 "out/poster-$FMT.jpg"
else
  "$FF" -y -v error -i "$FRAMES/$POSTER.png" -q:v 2 "out/poster-$FMT.jpg"
fi
"$(dirname "$FF")/ffprobe" -v error -show_entries format=duration:stream=codec_name,width,height -of compact "$OUT" 2>/dev/null || true
echo "$OUT"
