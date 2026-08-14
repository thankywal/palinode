#!/usr/bin/env bash
#
# Builds the full cut from the rendered title cards and the captured segments.
#
#   ./assemble.sh
#
# Everything is normalised to 1920x1080 h264 at 30fps first, because the
# capture comes out of Playwright as variable frame rate webm and the concat
# demuxer will happily produce something unplayable if you skip that.

set -euo pipefail
cd "$(dirname "$0")"

OUT=out
WORK=$OUT/work

# Wiped every run. The concat step globs this directory, so a clip left behind
# from a previous cut with different segment names silently ends up in the
# film, which is a confusing thing to debug from the runtime alone.
rm -rf "$WORK"
mkdir -p "$WORK"

echo "rendering title cards"
npx remotion render Intro "$OUT/intro.mp4" --log=error
npx remotion render Outro "$OUT/outro.mp4" --log=error

chapter() {
  npx remotion render Chapter "$OUT/ch$1.mp4" --log=error \
    --props="{\"index\":\"$1\",\"title\":\"$2\",\"subtitle\":\"$3\",\"accent\":\"$4\"}"
}

chapter "01" "Model Armor catches one of these" \
  "Both invoices send the money to the same attacker. Only one is a prompt injection." "#38BDF8"
chapter "02" "Nobody is watching" \
  "The fleet acts on the invoice that passed. Sentinel reverses it without being asked." "#C084FC"
chapter "03" "What could not be undone" \
  "A settled wire does not come back. Palinode says so instead of pretending." "#FBBF24"
chapter "04" "None of that was local" \
  "Cloud Run, Firestore, Model Armor and Cloud Trace, on the service the demo just used." "#4ADE80"

echo "building the console slides"
node console/build.mjs
mkdir -p console/png
for f in console/slides/*.html; do
  n=$(basename "$f" .html)
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
    --screenshot="console/png/$n.png" --window-size=1920,1080 --hide-scrollbars \
    --allow-file-access-from-files "$f" >/dev/null 2>&1
done

# Each console capture gets four and a half seconds and a very slow push in, so
# it reads as a held shot rather than a slide that stopped.
i=0
for png in console/png/*.png; do
  i=$((i+1))
  ffmpeg -v error -y -loop 1 -t 4.5 -i "$png" \
    -vf "scale=2400:-1,zoompan=z='min(zoom+0.00035,1.06)':d=135:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 19 "$WORK/console-$i.mp4"
done

echo "normalising"
norm() {
  ffmpeg -v error -y -i "$1" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 19 -an "$WORK/$2.mp4"
  printf "  %-16s %ss\n" "$2" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/$2.mp4")"
}

norm "$OUT/intro.mp4"                  "00-intro"
norm "$OUT/ch01.mp4"                   "01-ch"
norm "$OUT/capture/seg-01-armor.webm"  "02-armor"
norm "$OUT/ch02.mp4"                   "03-ch"
norm "$OUT/capture/seg-02-sentinel.webm" "04-sentinel"
norm "$OUT/ch03.mp4"                   "05-ch"
norm "$OUT/capture/seg-03-disclosure.webm" "06-disclosure"
norm "$OUT/ch04.mp4"                   "07-ch"
for c in "$WORK"/console-*.mp4; do
  n=$(basename "$c" .mp4 | sed 's/console-//')
  mv "$c" "$WORK/08-console-$n.mp4"
done
norm "$OUT/outro.mp4"                  "09-outro"

echo "stitching"
: > "$WORK/list.txt"
for f in "$WORK"/[0-9][0-9]-*.mp4; do
  echo "file '$(basename "$f")'" >> "$WORK/list.txt"
done

ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$OUT/palinode-demo.mp4"

echo
echo "  $OUT/palinode-demo.mp4"
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "$OUT/palinode-demo.mp4"
