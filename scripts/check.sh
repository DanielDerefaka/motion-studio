#!/bin/sh
# Reports which tools the studio can use on this machine. Prints one line per
# tool and a branch verdict; exits 0 either way.
#   sh ~/.claude/skills/motion-studio/scripts/check.sh
ok() { printf '  ok   %-10s %s\n' "$1" "$2"; }
no() { printf '  --   %-10s %s\n' "$1" "$2"; }
B=$(command -v blender || ls /Applications/Blender.app/Contents/MacOS/Blender 2>/dev/null)
[ -n "$B" ] && ok blender "$("$B" --version 2>/dev/null | head -1) ($B)" || no blender "missing: 3D branch unavailable (brew install --cask blender)"
command -v node >/dev/null && ok node "$(node -v)" || no node "missing: install Node 20+"
FF=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg 2>/dev/null)
if [ -n "$FF" ]; then
  ok ffmpeg "$("$FF" -version | head -1 | cut -d' ' -f1-3)"
  "$FF" -hide_banner -filters 2>/dev/null | grep -q drawtext && ok drawtext "available" || no drawtext "not built in: draw text in HTML/Blender, never ffmpeg"
else no ffmpeg "missing: brew install ffmpeg"; fi
command -v yt-dlp >/dev/null && ok yt-dlp "inspo links can be downloaded" || no yt-dlp "missing: brew install yt-dlp (or the person sends the file)"
command -v python3 >/dev/null && ok python3 "$(python3 --version 2>&1)" || no python3 missing
if node -e "require.resolve('puppeteer')" 2>/dev/null; then
  node -e "Promise.resolve(require('puppeteer').executablePath()).then((p) => require('fs').accessSync(p)).catch(() => process.exit(1))" 2>/dev/null \
    && ok puppeteer "resolvable, its Chrome installed" || no puppeteer "its Chrome is missing: run npx puppeteer browsers install chrome"
else no puppeteer "run: npm i puppeteer"; fi
[ -x cache/venv/bin/python ] && ok venv "cache/venv" || no venv "run: sh src/setup-venv.sh"
[ -d cache/tts ] && ok kokoro "cache/tts" || no kokoro "run: sh src/setup-tts.sh (voice-over only)"
NF=$(ls assets/fonts 2>/dev/null | grep -ciE '\.(otf|ttf|woff2?)$')
[ "$NF" -gt 0 ] && ok fonts "$NF files" || no fonts "none yet: download the fonts style-guide.md names (craft.md Fonts)"
case "$(uname -m)" in arm64) ok gpu "Apple silicon: Blender METAL";; *) ok gpu "$(uname -m): Blender picks OPTIX/CUDA/HIP or CPU";; esac
