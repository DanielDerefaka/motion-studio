#!/bin/sh
# The local voice: <studio>/cache/tts-venv with kokoro-onnx + soundfile, and the
# two Kokoro v1.0 model files in <studio>/cache/tts/. Idempotent: what is
# already there (and the right size) is kept.
#
#   sh templates/voice/setup-tts.sh <studio>       # default: the current directory
#   <studio>/cache/tts-venv/bin/python -I src/voice.py --samples "A line."
#
# Models: copied from $LOCAL_TTS (a folder you already have them in) when set, else
# downloaded from the kokoro-onnx GitHub release "model-files-v1.0".
set -eu
STUDIO=$(cd "${1:-.}" && pwd)
VENV="$STUDIO/cache/tts-venv"
TTS="$STUDIO/cache/tts"
PY=${PYTHON:-python3}
LOCAL_TTS=${LOCAL_TTS:-}
RELEASE=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0

mkdir -p "$TTS"
if [ ! -x "$VENV/bin/python" ]; then
  echo "making $VENV ($($PY --version))"
  "$PY" -m venv "$VENV"
fi
if "$VENV/bin/python" -I -c 'import kokoro_onnx, soundfile' 2>/dev/null; then
  echo "tts venv ready: $VENV"
else
  "$VENV/bin/python" -I -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -I -m pip install --quiet kokoro-onnx soundfile
  "$VENV/bin/python" -I -c 'import kokoro_onnx, soundfile; print("tts venv ready")'
fi

# name and exact size (bytes) of each release file
for spec in kokoro-v1.0.onnx:325532387 voices-v1.0.bin:28214398; do
  name=${spec%%:*}
  size=${spec##*:}
  dest="$TTS/$name"
  have=$( [ -f "$dest" ] && wc -c < "$dest" | tr -d ' ' || echo 0 )
  if [ "$have" = "$size" ]; then
    echo "have $name"
    continue
  fi
  if [ -n "$LOCAL_TTS" ] && [ -f "$LOCAL_TTS/$name" ] && [ "$(wc -c < "$LOCAL_TTS/$name" | tr -d ' ')" = "$size" ] \
     && [ "$(cd "$LOCAL_TTS" && pwd -P)" != "$(cd "$TTS" && pwd -P)" ]; then
    echo "copying $name from $LOCAL_TTS"
    cp "$LOCAL_TTS/$name" "$dest.part"
  else
    echo "downloading $name ($size bytes) from $RELEASE"
    curl -fL --retry 3 -o "$dest.part" "$RELEASE/$name"
  fi
  got=$(wc -c < "$dest.part" | tr -d ' ')
  if [ "$got" != "$size" ]; then
    echo "error: $name is $got bytes, expected $size; left at $dest.part" >&2
    exit 1
  fi
  mv "$dest.part" "$dest"
done
echo "models ready: $TTS"
