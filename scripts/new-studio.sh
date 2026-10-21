#!/bin/sh
# Scaffolds a film studio in ./<name> (or the cwd when it is empty) from the
# skill's templates. Never overwrites an existing file.
#   sh ~/.claude/skills/motion-studio/scripts/new-studio.sh <name> [3d|2d|hybrid]
set -e
SKILL=$(cd "$(dirname "$0")/.." && pwd)
NAME=${1:?film name, kebab-case}
BRANCH=${2:-hybrid}
DIR=$NAME
[ -z "$(ls -A . 2>/dev/null | grep -v '^\.')" ] && DIR=.
mkdir -p "$DIR"/src "$DIR"/assets/fonts "$DIR"/assets/ui "$DIR"/assets/footage "$DIR"/assets/brand \
  "$DIR"/inspo/analysis "$DIR"/reviews "$DIR"/out "$DIR"/cache
put() { [ -e "$DIR/$2" ] || cp -R "$SKILL/$1" "$DIR/$2"; }
put templates/timeline.py src/timeline.py
put templates/encode.sh src/encode.sh
put templates/contact-sheet.sh src/contact-sheet.sh
for f in "$SKILL"/templates/capture/*; do put "templates/capture/$(basename "$f")" "src/$(basename "$f")"; done
for f in "$SKILL"/templates/sound/* "$SKILL"/templates/voice/*; do [ -f "$f" ] && put "${f#$SKILL/}" "src/$(basename "$f")"; done
case $BRANCH in
  3d|hybrid) for f in "$SKILL"/templates/blender/*; do [ -f "$f" ] && put "${f#$SKILL/}" "src/$(basename "$f")"; done ;;
esac
case $BRANCH in
  2d|hybrid) for f in "$SKILL"/templates/2d/*; do [ -e "$f" ] && put "${f#$SKILL/}" "src/$(basename "$f")"; done ;;   # files and presets/
esac
for doc in brief style-guide shotlist; do put "templates/docs/$doc.md" "$doc.md"; done
[ -e "$DIR/.gitignore" ] || printf 'cache/\nnode_modules/\nout/frames-*/\n' > "$DIR/.gitignore"
sed -i '' "s/^NAME = .*/NAME = '$NAME'/" "$DIR/src/timeline.py" 2>/dev/null || sed -i "s/^NAME = .*/NAME = '$NAME'/" "$DIR/src/timeline.py"
echo "studio: $(cd "$DIR" && pwd) ($BRANCH)"
