#!/usr/bin/env bash
#
# Builds the full cut: picture cut to the narration, then the soundtrack laid
# over it. Delivered at 4K.
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
# On resolution and bitrate. The first 1080p master came out at 521 kbps,
# which is where the softness everybody could see was coming from: not the
# sources, all of which are sharp, but an encoder given nothing to work with.
# Delivery is now 3840x2160 through VideoToolbox at a bitrate chosen to be
# wasteful, because this is a master that YouTube will re-encode anyway and the
# only thing that costs is disk.
#
#   the dashboard take   3840x2160 native, recorded that way
#   the cards            Remotion at scale 2, genuinely rendered at 4K
#   the console slides   laid out at 4K around one clean 2x upscale
#
# The console captures are the only source that is not natively 4K, because a
# browser extension screenshot is however many pixels the window had. They are
# upscaled once, with a good filter, rather than twice by accident.

set -euo pipefail
cd "$(dirname "$0")"

OUT=out
WORK=$OUT/work
SHOTS=$OUT/shots.tsv
SOUND=audio/build/soundtrack.wav
TAKE=$OUT/capture/seg-dashboard.webm

W=3840
H=2160
# VideoToolbox takes a bitrate rather than a quality target. This is far more
# than 4K needs and that is the point.
VENC=(-c:v h264_videotoolbox -b:v 80M -maxrate 95M -bufsize 160M -profile:v high -allow_sw 1)

[ -f "$SOUND" ] || { echo "no soundtrack, run ./mixdown.sh first"; exit 1; }
[ -f "$SHOTS" ] || { echo "no shot list, run python plan.py first"; exit 1; }

# Wiped every run. The concat step globs this directory, so a clip left behind
# from a previous cut with different shot names silently ends up in the film,
# which is a confusing thing to debug from the runtime alone.
rm -rf "$WORK"
mkdir -p "$WORK"

# --------------------------------------------------------------- title cards

# scale 2 renders the 1920x1080 compositions at 4K for real. Every glyph and
# every border is drawn at the delivery size rather than blown up afterwards.
if [ "${SKIP_CARDS:-0}" = "1" ]; then
  echo "reusing the rendered cards"
else
echo "rendering the cards at 4K"
npx remotion render Intro    "$OUT/intro.mp4"    --scale=2 --log=error
npx remotion render Invoices "$OUT/invoices.mp4" --scale=2 --log=error
npx remotion render Sweeper  "$OUT/sweeper.mp4"  --scale=2 --log=error
npx remotion render Outro    "$OUT/outro.mp4"    --scale=2 --log=error
fi

# ------------------------------------------------------------------- shots

# A slow drift, over the length of whatever it is applied to. Held stills used
# to be held absolutely still, which was the right call when a move cost six
# minutes of encoding on the CPU. On the GPU it costs nothing, and evidence
# that drifts very slightly reads as a camera rather than as a slide.
#
# A pan rather than a zoom, deliberately. zoompan rounds its offsets to whole
# pixels, and a four percent zoom across five seconds at 4K moves the frame by
# less than a pixel per frame, so the rounding shows up as a stutter. A linear
# translation of about a pixel a frame does not.
drift() {
  local seconds=$1
  local up=$(python3 -c "print(int($W*1.05//2*2))")
  local upy=$(python3 -c "print(int($H*1.05//2*2))")
  echo "scale=$up:$upy:flags=lanczos,crop=$W:$H:'($up-$W)*t/$seconds':'($upy-$H)*t/$seconds'"
}

echo "cutting"
while IFS=$'\t' read -r name kind spec offset seconds; do
  [ -n "$name" ] || continue
  frames=$(python3 -c "print(max(1,int(round($seconds*30))))")

  case "$kind" in
    remotion)
      # Already 4K and already animated. Trimmed so a rounding difference
      # between Remotion and ffmpeg cannot walk the film out of sync.
      lower=$(echo "$spec" | tr 'A-Z' 'a-z')
      ffmpeg -nostdin -v error -y -i "$OUT/$lower.mp4" -t "$seconds" \
        -vf "scale=$W:$H:flags=lanczos,fps=30,format=yuv420p" \
        "${VENC[@]}" -an "$WORK/$name.mp4"
      ;;
    take)
      # One continuous recording at 4K. Time never jumps inside it. What
      # changes is the framing, which follows whichever panel the voice is on,
      # and it drifts while it holds.
      ffmpeg -nostdin -v error -y -ss "$offset" -i "$TAKE" -t "$seconds" \
        -vf "$spec,fps=30,format=yuv420p" \
        "${VENC[@]}" -an "$WORK/$name.mp4"
      ;;
    console)
      # A capture with a camera over it, rendered by Remotion at scale 2 so
      # the magnification rasterises at delivery size rather than being
      # upscaled after the fact. Vendored from video-shotcraft, Apache 2.0.
      # Rendering eight of these at 4K is most of the wall clock in this
      # script and they do not change when only the cut does. Delete the file
      # to force one.
      if [ ! -f "$OUT/shot-$spec.mp4" ]; then
        npx remotion render "shot-$spec" "$OUT/shot-$spec.mp4" --scale=2 --log=error
      fi
      ffmpeg -nostdin -v error -y -i "$OUT/shot-$spec.mp4" -t "$seconds" \
        -vf "scale=$W:$H:flags=lanczos,fps=30,format=yuv420p" \
        "${VENC[@]}" -an "$WORK/$name.mp4"
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
ffmpeg -nostdin -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$WORK/picture.mp4"

echo "laying the sound"
# -shortest so a frame of drift at the end cannot leave the film running on
# black after the last word.
ffmpeg -nostdin -v error -y -i "$WORK/picture.mp4" -i "$SOUND" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -shortest \
  -movflags +faststart "$OUT/palinode-demo.mp4"

echo
echo "  $OUT/palinode-demo.mp4"
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "$OUT/palinode-demo.mp4"
