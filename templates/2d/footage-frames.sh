#!/bin/sh
# Footage for 2D compositions: every clip in assets/footage/ (or the ones
# named) as numbered JPGs at the film's FPS, so a composition can draw frame N
# of a clip exactly (footage.js). Seekable: no <video>, no playback clock.
#
#   sh src/footage-frames.sh [clip ...]      # cache/clips/<clip>/NNNN.jpg, count.txt, cache/clips/index.js
#
# Width follows the largest format (1920); FPS from src/timeline.json.
set -eu
cd "$(dirname "$0")/.."
FPS=$(python3 -c "import json;print(json.load(open('src/timeline.json'))['FPS'])")
[ $# -gt 0 ] || set -- $(ls assets/footage | sed -En 's/\.(webm|mp4|mov|mkv)$//p')
for c in "$@"; do
  src=$(ls assets/footage/"$c".* 2>/dev/null | grep -E '\.(webm|mp4|mov|mkv)$' | head -1)
  [ -n "$src" ] || { echo "no clip assets/footage/$c.*" >&2; exit 1; }
  out=cache/clips/$c
  if [ -s "$out/count.txt" ] && [ "$out/count.txt" -nt "$src" ]; then echo "$c: $(cat "$out/count.txt") frames (cached)"; continue; fi
  rm -rf "$out" && mkdir -p "$out"
  ffmpeg -v error -i "$src" -vf "fps=$FPS,scale='min(1920,iw)':-2" -q:v 3 -start_number 0 "$out/%04d.jpg"
  n=$(ls "$out" | grep -c '\.jpg$')
  [ "$n" -gt 0 ] || { echo "$c: no frames decoded" >&2; exit 1; }
  echo "$n" > "$out/count.txt"
  echo "$c: $n frames at $FPS fps -> $out/"
done
# counts for footage.js (a module: file:// pages can import it, not fetch it)
{ printf 'export default {'
  for d in cache/clips/*/; do c=$(basename "$d"); [ -s "$d/count.txt" ] && printf '"%s": %s, ' "$c" "$(cat "$d/count.txt")"; done
  printf '};\n'; } > cache/clips/index.js
