#!/usr/bin/env bash
#
# Builds the full cut: picture timed to the narration, then the soundtrack laid
# over it.
#
#   ./mixdown.sh && ./assemble.sh
#
# The audio is the master. Every boundary below is the moment a narration
# segment starts, taken from audio/vo/timing.json plus the 0.55 second breath
# between segments that mixdown.sh inserts. The picture is cut to those
# numbers rather than the other way round, so nothing has to be nudged into
# sync at the end.
#
#   0.00   intro card              01-hook
#  10.40   the two invoices        02-two-invoices
#  40.90   the dashboard, one take 03 to 06
# 114.98   Stripe, GitHub, Slack   07-it-was-real
# 130.21   Cloud Run and friends   08-google-cloud
# 151.01   outro                   09-close
# 165.24   end
#
# Everything is normalised to 1920x1080 h264 at 30fps before the concat,
# because Playwright hands back variable frame rate webm and the concat
# demuxer will happily produce something unplayable if you skip that.

set -euo pipefail
cd "$(dirname "$0")"

OUT=out
WORK=$OUT/work
SOUND=audio/build/soundtrack.wav

[ -f "$SOUND" ] || { echo "no soundtrack, run ./mixdown.sh first"; exit 1; }

# Wiped every run. The concat step globs this directory, so a clip left behind
# from a previous cut with different segment names silently ends up in the
# film, which is a confusing thing to debug from the runtime alone.
rm -rf "$WORK"
mkdir -p "$WORK"

PROOF=5.0767        # three shots across 114.98 to 130.21
CLOUD=5.2000        # four shots across 130.21 to 151.01

# The dashboard is one unbroken take, recorded at 4K. Time never jumps in it.
# What changes is the framing, which follows whichever panel the narration is
# on, because the board goes still once the reversal has landed and the voice
# has another thirty seconds to run. Framing in on a 1080p capture is what
# blurred an earlier cut. Here a half frame crop is delivered at its own size.
#
#   40.90  wide, the fleet acting and Sentinel deciding      s03 and s04
#   82.71  in on the ledger rows, what came back             s05
#  102.28  in on the disclosure, what did not                s06
#  114.98  out
DASH_WIDE=41.81
DASH_ROWS=19.57
DASH_DISC=12.70

# --------------------------------------------------------------- title cards

echo "rendering the cards"
npx remotion render Intro    "$OUT/intro.mp4"    --log=error
npx remotion render Invoices "$OUT/invoices.mp4" --log=error
npx remotion render Outro    "$OUT/outro.mp4"    --log=error

# ------------------------------------------------------------ console slides

echo "building the console slides"
node console/build.mjs
rm -rf console/png
mkdir -p console/png
for f in console/slides/*.html; do
  n=$(basename "$f" .html)
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
    --screenshot="console/png/$n.png" --window-size=1920,1080 --hide-scrollbars \
    --allow-file-access-from-files "$f" >/dev/null 2>&1
done

# Held stills, no push in. A zoom looked better for about a second and then
# cost 190MB per clip and six minutes of encoding, because resampling sharp
# console text every frame is the worst case for h264. These are evidence, not
# motion graphics, and they are more legible standing still anyway.
still() {
  ffmpeg -v error -y -loop 1 -t "$2" -i "$1" \
    -vf "fps=30,format=yuv420p" -tune stillimage \
    -c:v libx264 -preset veryfast -crf 20 "$3"
}

still console/png/s01.png "$PROOF" "$WORK/03-stripe.mp4"
still console/png/s02.png "$PROOF" "$WORK/04-github.mp4"
still console/png/s03.png "$PROOF" "$WORK/05-slack.mp4"
still console/png/s04.png "$CLOUD" "$WORK/06-cloudrun.mp4"
still console/png/s05.png "$CLOUD" "$WORK/07-logs.mp4"
still console/png/s06.png "$CLOUD" "$WORK/08-trace.mp4"
still console/png/s07.png "$CLOUD" "$WORK/09-firestore.mp4"

# ------------------------------------------------------------------ the rest

echo "normalising"
norm() {
  # set -u trips over an empty array on bash 3, which is what ships on macOS,
  # so the flag is carried as two plain words instead.
  local trim=""
  [ "${3:-}" ] && trim="-t $3"
  # shellcheck disable=SC2086
  ffmpeg -v error -y -i "$1" $trim \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 19 -an "$WORK/$2.mp4"
}

norm "$OUT/intro.mp4"                  "00-intro"
norm "$OUT/invoices.mp4"               "01-invoices"

# Frames of the take, in order, with no gap between them. Wide is the whole 4K
# frame brought down to delivery size. The other two are cut out of it at their
# own resolution and never resampled.
TAKE=$OUT/capture/seg-dashboard.webm
shot() {
  ffmpeg -v error -y -ss "$1" -i "$TAKE" -t "$2" \
    -vf "$3,fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 19 -an "$WORK/$4.mp4"
}

# The recorder is running before the page is. The first half second of the
# take is the white of about:blank, which lands as a white flash at the cut,
# so the shot starts after the first paint. The tail has the slack for it.
shot 0.70  "$DASH_WIDE" "scale=1920:1080"          "02a-dash-wide"
shot 42.51 "$DASH_ROWS" "crop=1920:1080:940:170"   "02b-dash-rows"
shot 62.08 "$DASH_DISC" "crop=1920:1080:1920:1080" "02c-dash-disclosure"

norm "$OUT/outro.mp4"                  "10-outro"

for f in "$WORK"/[0-9][0-9]*-*.mp4; do
  printf "  %-16s %ss\n" "$(basename "$f" .mp4)" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"
done

# --------------------------------------------------------------- the film

echo "stitching"
: > "$WORK/list.txt"
for f in "$WORK"/[0-9][0-9]*-*.mp4; do
  echo "file '$(basename "$f")'" >> "$WORK/list.txt"
done
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$WORK/picture.mp4"

echo "laying the sound"
# -shortest so a frame of drift at the end cannot leave the film running on
# black after the last word.
ffmpeg -v error -y -i "$WORK/picture.mp4" -i "$SOUND" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest \
  -movflags +faststart "$OUT/palinode-demo.mp4"

echo
echo "  $OUT/palinode-demo.mp4"
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name \
  -of default=noprint_wrappers=1 "$OUT/palinode-demo.mp4"
