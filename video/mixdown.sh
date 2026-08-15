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
#
# The narration arrives as one file per line. The gaps between them are the
# ones timing.json already counted, so the finished audio is exactly as long as
# the plan the picture is cut to.

set -euo pipefail
cd "$(dirname "$0")"

VO=audio/vo
OUT=audio/build
mkdir -p "$OUT"

[ -f "$VO/timing.json" ] || { echo "no timing.json, run speak.py first"; exit 1; }

# ---------------------------------------------------------------- narration

echo "stitching the narration"

# Two lengths of silence. A short breath between the lines of a paragraph, a
# longer one between paragraphs.
LINE_GAP=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['gap_line'])")
SEG_GAP=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['gap_segment'])")

ffmpeg -v error -y -f lavfi -t "$LINE_GAP" -i anullsrc=r=24000:cl=mono "$VO/gap-line.wav"
ffmpeg -v error -y -f lavfi -t "$SEG_GAP"  -i anullsrc=r=24000:cl=mono "$VO/gap-seg.wav"

# The concat demuxer resolves paths relative to the list file, so the list
# lives beside the audio it names rather than in the build directory.
python3 - <<'PY'
import json, pathlib
vo = pathlib.Path("audio/vo")
timing = json.loads((vo / "timing.json").read_text())
segments = timing["segments"]

order = []
for i, segment in enumerate(segments):
    for n, line in enumerate(segment["lines"]):
        order.append(line["file"])
        if n < len(segment["lines"]) - 1:
            order.append("gap-line.wav")
    if i < len(segments) - 1:
        order.append("gap-seg.wav")

(vo / "order.txt").write_text("".join(f"file '{f}'\n" for f in order))
print(f"  {len(order)} pieces")
PY

ffmpeg -v error -y -f concat -safe 0 -i "$VO/order.txt" -ar 48000 -ac 2 "$OUT/vo.wav"
rm -f "$VO/gap-line.wav" "$VO/gap-seg.wav" "$VO/order.txt"

VO_LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/vo.wav")
PLANNED=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['total'])")
echo "  narration ${VO_LEN}s, planned ${PLANNED}s"

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
