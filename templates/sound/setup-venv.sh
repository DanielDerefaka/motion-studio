#!/bin/sh
# The studio's Python for the sound: <studio>/cache/venv with numpy, scipy,
# soundfile and pillow (pillow only draws reviews/sound.png). Idempotent: an
# existing venv that already imports all four is left alone.
#
#   sh templates/sound/setup-venv.sh <studio>      # default: the current directory
#   <studio>/cache/venv/bin/python src/sound.py
set -eu
STUDIO=$(cd "${1:-.}" && pwd)
VENV="$STUDIO/cache/venv"
PY=${PYTHON:-python3}

mkdir -p "$STUDIO/cache"
if [ ! -x "$VENV/bin/python" ]; then
  echo "making $VENV ($($PY --version))"
  "$PY" -m venv "$VENV"
fi
# -I: a stray numpy.py or bisect.py in the cwd must not shadow the real ones.
if "$VENV/bin/python" -I -c 'import numpy, scipy, soundfile, PIL' 2>/dev/null; then
  echo "venv ready: $VENV"
else
  "$VENV/bin/python" -I -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -I -m pip install --quiet numpy scipy soundfile pillow
  "$VENV/bin/python" -I -c 'import numpy, scipy, soundfile, PIL; print("venv ready:", numpy.__version__, scipy.__version__, soundfile.__version__, PIL.__version__)'
fi
