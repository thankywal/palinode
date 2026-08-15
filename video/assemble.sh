#!/usr/bin/env bash
#
# Builds the full cut: picture cut to the narration, then the soundtrack laid
# over it.
#
#   python speak.py && ./mixdown.sh && python plan.py && ./assemble.sh
#
# There are no timings in this file. Every shot and every length comes from
# out/shots.tsv, which plan.py derives from the measured length of each
# synthesised line. That is the whole design: the audio is recorded, then
# measured, and the picture is cut to the measurement.
#
# It was not always so. The first cut sliced each narration segment into equal
# pieces, and segment eight names four Google Cloud services in sentences that
# run from three seconds to eleven, so the voice arrived at Cloud Trace while
# the picture was still on the logs.
#
# Everything is normalised to 1920x1080 h264 at 30fps before the concat,
# because Playwright hands back variable frame rate webm and the concat
# demuxer will happily produce something unplayable if you skip that.

set -euo pipefail
cd "$(dirname "$0")"

OUT=out
WORK=$OUT/work
SHOTS=$OUT/shots.tsv
SOUND=audio/build/soundtrack.wav
TAKE=$OUT/capture/seg-dashboard.webm

[ -f "$SOUND" ] || { echo "no soundtrack, run ./mixdown.sh first"; exit 1; }
[ -f "$SHOTS" ] || { echo "no shot list, run python plan.py first"; exit 1; }

# Wiped every run. The concat step globs this directory, so a clip left behind
# from a previous cut with different shot names silently ends up in the film,
# which is a confusing thing to debug from the runtime alone.
rm -rf "$WORK"
mkdir -p "$WORK"

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

# ------------------------------------------------------------------- shots

# -nostdin on every one of these. ffmpeg reads standard input by default, and
# inside the while loop below that is the shot list, so it quietly ate the next
# few lines and the film came out with the names half chewed.
norm() {
  ffmpeg -nostdin -v error -y -i "$1" -t "$2" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 19 -an "$3"
}

echo "cutting"
while IFS=$'\t' read -r name kind spec offset seconds; do
  [ -n "$name" ] || continue
  case "$kind" in
    remotion)
      # Rendered to the plan's length already. Trimmed anyway so a rounding
      # difference between Remotion and ffmpeg cannot walk the film out of sync.
      lower=$(echo "$spec" | tr 'A-Z' 'a-z')
      norm "$OUT/$lower.mp4" "$seconds" "$WORK/$name.mp4"
      ;;
    take)
      # One continuous recording. Time never jumps inside it. What changes is
      # the framing, which follows whichever panel the voice is on, and the
      # crops are delivered at their own size because the take is 4K.
      ffmpeg -nostdin -v error -y -ss "$offset" -i "$TAKE" -t "$seconds" \
        -vf "$spec,fps=30,format=yuv420p" \
        -c:v libx264 -preset medium -crf 19 -an "$WORK/$name.mp4"
      ;;
    still)
      # Held stills, no push in. A zoom looked better for about a second and
      # then cost 190MB per clip and six minutes of encoding, because
      # resampling sharp console text every frame is the worst case for h264.
      # These are evidence, not motion graphics, and they are more legible
      # standing still anyway.
      ffmpeg -nostdin -v error -y -loop 1 -t "$seconds" -i "console/png/$spec.png" \
        -vf "fps=30,format=yuv420p" -tune stillimage \
        -c:v libx264 -preset veryfast -crf 20 "$WORK/$name.mp4"
      ;;
    *)
      echo "  unknown shot kind: $kind"; exit 1 ;;
  esac
  printf "  %-20s %6.2fs\n" "$name" "$seconds"
done < "$SHOTS"

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
