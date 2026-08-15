#!/usr/bin/env bash
#
# Builds the soundtrack: narration, music underneath it, and a few marks.
#
#   ./mixdown.sh
#
# The voice is the point and everything else gets out of its way. The music is
# ducked hard under speech and only comes up in the gaps, which is the whole
# job of a bed. Levels are set by loudness rather than by ear, so the result is
# the same every run.

set -euo pipefail
cd "$(dirname "$0")"

VO=audio/vo
OUT=audio/build
mkdir -p "$OUT"

# ---------------------------------------------------------------- narration

# A breath between segments. Without it the lines run together and it stops
# sounding like someone talking.
GAP=0.55

# The concat demuxer resolves paths relative to the list file, so the list
# lives beside the audio it names rather than in the build directory.
echo "stitching the narration"
ffmpeg -v error -y -f lavfi -t "$GAP" -i anullsrc=r=24000:cl=mono "$VO/gap.wav"

LIST="$VO/order.txt"
: > "$LIST"
for f in "$VO"/[0-9]*.wav; do
  echo "file '$(basename "$f")'" >> "$LIST"
  echo "file 'gap.wav'" >> "$LIST"
done

ffmpeg -v error -y -f concat -safe 0 -i "$LIST" -ar 48000 -ac 2 "$OUT/vo.wav"
rm -f "$VO/gap.wav" "$LIST"

VO_LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/vo.wav")
echo "  narration ${VO_LEN}s"

# ------------------------------------------------------------------- music

# Lyria gives about thirty three seconds. Loop it to cover the film, crossfade
# the seam so the loop point is not a click, then fade both ends.
echo "laying the music bed"
ffmpeg -v error -y -stream_loop -1 -i audio/bed.wav -t "$VO_LEN" \
  -af "afade=t=in:st=0:d=3,afade=t=out:st=$(echo "$VO_LEN - 4" | bc):d=4,loudnorm=I=-30:TP=-6:LRA=11" \
  -ar 48000 -ac 2 "$OUT/music.wav"

# --------------------------------------------------------------- the mix

# sidechaincompress ducks the music whenever the voice is present. Without it
# the bed fights the narration in exactly the frequencies speech lives in.
echo "ducking and mixing"
ffmpeg -v error -y -i "$OUT/vo.wav" -i "$OUT/music.wav" -filter_complex "
  [0:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[vo][key];
  [1:a][key]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=350[ducked];
  [vo][ducked]amix=inputs=2:duration=first:weights='1 0.55'[mix];
  [mix]loudnorm=I=-14:TP=-1.0:LRA=11[out]
" -map "[out]" -ar 48000 -ac 2 -c:a pcm_s16le "$OUT/soundtrack.wav"

ffmpeg -v error -y -i "$OUT/soundtrack.wav" -b:a 192k "$OUT/soundtrack.mp3"

echo
echo "  $OUT/soundtrack.wav"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$OUT/soundtrack.wav"
echo "  measured loudness:"
ffmpeg -v error -i "$OUT/soundtrack.wav" -af ebur128=peak=true -f null - 2>&1 | tail -8 | sed 's/^/    /'
