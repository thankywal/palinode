#!/usr/bin/env bash
#
# Builds the soundtrack: narration, a score under it, and effects on top.
#
#   python speak.py && python score.py && ./mixdown.sh
#
# Three layers.
#
# The voice is the point and everything else gets out of its way. It arrives as
# one file per line with the gaps timing.json already counted, so the finished
# audio is exactly as long as the plan the picture is cut to.
#
# The score is Lyria, in two pieces. `drive` runs under the incident: a pulse,
# because an incident has one. `close` takes over for the last segment, where
# somebody is telling you what it cost and a sixteenth note arpeggio would be
# indecent. The crossfade between them is the only moment in this file chosen
# by ear rather than measured, and it is one line so it can be argued with.
#
# The effects come from sound.py, which anchors every cue to a line of
# narration rather than to a clock, so they move when the script does.
#
# Levels are set by loudness rather than by ear, so the result is the same
# every run: the mix lands at -14 LUFS, which is what YouTube normalises to.

set -euo pipefail
cd "$(dirname "$0")"

VO=audio/vo
SCORE=audio/score
OUT=audio/build
mkdir -p "$OUT"

[ -f "$VO/timing.json" ] || { echo "no timing.json, run speak.py first"; exit 1; }
[ -d "$SCORE" ] || { echo "no score, run score.py first"; exit 1; }

# Best of the takes by onset energy: drive-2 carries the most transient
# information per second, which is the measurable part of having a pulse.
DRIVE=$SCORE/drive-2.wav
CLOSE=$SCORE/close-1.wav

# ---------------------------------------------------------------- narration

echo "stitching the narration"

LINE_GAP=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['gap_line'])")
SEG_GAP=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['gap_segment'])")

ffmpeg -nostdin -v error -y -f lavfi -t "$LINE_GAP" -i anullsrc=r=24000:cl=mono "$VO/gap-line.wav"
ffmpeg -nostdin -v error -y -f lavfi -t "$SEG_GAP"  -i anullsrc=r=24000:cl=mono "$VO/gap-seg.wav"

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

ffmpeg -nostdin -v error -y -f concat -safe 0 -i "$VO/order.txt" -ar 48000 -ac 2 "$OUT/vo.wav"
rm -f "$VO/gap-line.wav" "$VO/gap-seg.wav" "$VO/order.txt"

LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/vo.wav")
PLANNED=$(python3 -c "import json;print(json.load(open('$VO/timing.json'))['total'])")
echo "  narration ${LEN}s, planned ${PLANNED}s"

# ------------------------------------------------------------------- score

# Where the score changes temperature: the start of the closing segment.
SWITCH=$(python3 -c "
import json
t = json.load(open('$VO/timing.json'))
print([s for s in t['segments'] if s['id'] == '10-close'][0]['start'])
")
echo "laying the score, handing over at ${SWITCH}s"

# Each piece is about thirty three seconds. Loop it to cover its stretch,
# crossfade the seam so the loop point is not a click, fade the ends.
ffmpeg -nostdin -v error -y -stream_loop -1 -i "$DRIVE" -t "$(echo "$SWITCH + 6" | bc)" \
  -af "afade=t=in:st=0:d=2.5,loudnorm=I=-28:TP=-6:LRA=11" \
  -ar 48000 -ac 2 "$OUT/score-drive.wav"

ffmpeg -nostdin -v error -y -stream_loop -1 -i "$CLOSE" -t "$(echo "$LEN - $SWITCH + 4" | bc)" \
  -af "afade=t=out:st=$(echo "$LEN - $SWITCH - 3" | bc):d=4,loudnorm=I=-28:TP=-6:LRA=11" \
  -ar 48000 -ac 2 "$OUT/score-close.wav"

# Handed over with a four second crossfade centred on the switch, so the pulse
# thins out under the last thing the film says rather than stopping dead.
ffmpeg -nostdin -v error -y -i "$OUT/score-drive.wav" -i "$OUT/score-close.wav" \
  -filter_complex "[0][1]acrossfade=d=4:c1=tri:c2=tri[s]" \
  -map "[s]" -ar 48000 -ac 2 "$OUT/score.wav"

# ----------------------------------------------------------------- effects

echo "placing the effects"
python3 - > "$OUT/sfx.txt" <<'PY'
import json, pathlib, sys
sys.path.insert(0, ".")
from sound import cue_sheet
for cue in cue_sheet():
    print(f"{cue['at']}\t{cue['file']}\t{cue['gain']}")
PY

CUES=$(wc -l < "$OUT/sfx.txt" | tr -d ' ')
echo "  $CUES cues"

# One filter graph: every effect delayed to its moment, gained, and summed.
# amix would divide the level by the number of inputs, which for forty three
# effects means silence, so they are summed and the whole bed is normalised.
python3 - <<'PY' > "$OUT/sfx.cmd"
import pathlib
rows = [l.split("\t") for l in pathlib.Path("audio/build/sfx.txt").read_text().splitlines() if l.strip()]
inputs, chains, labels = [], [], []
for i, (at, path, gain) in enumerate(rows):
    inputs.append(f'-i "{path}"')
    ms = int(float(at) * 1000)
    chains.append(f"[{i}:a]adelay={ms}|{ms},volume={gain}dB,aformat=sample_rates=48000:channel_layouts=stereo[s{i}]")
    labels.append(f"[s{i}]")
graph = ";".join(chains) + ";" + "".join(labels) + f"amix=inputs={len(rows)}:duration=longest:normalize=0[sfx]"
print(" ".join(inputs) + ' -filter_complex "' + graph + '" -map "[sfx]"')
PY

eval ffmpeg -nostdin -v error -y $(cat "$OUT/sfx.cmd") -ar 48000 -ac 2 -t "$LEN" "$OUT/sfx.wav"

# --------------------------------------------------------------- the mix

# sidechaincompress ducks the score whenever the voice is present. Without it
# the bed fights the narration in exactly the frequencies speech lives in. The
# effects are not ducked: they are meant to land on top.
echo "ducking and mixing"
ffmpeg -nostdin -v error -y -i "$OUT/vo.wav" -i "$OUT/score.wav" -i "$OUT/sfx.wav" -filter_complex "
  [0:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[vo][key];
  [1:a][key]sidechaincompress=threshold=0.035:ratio=9:attack=5:release=320[ducked];
  [vo][ducked][2:a]amix=inputs=3:duration=first:normalize=0:weights='1 0.62 0.85'[mix];
  [mix]loudnorm=I=-14:TP=-1.0:LRA=11[out]
" -map "[out]" -ar 48000 -ac 2 -c:a pcm_s16le "$OUT/soundtrack.wav"

ffmpeg -nostdin -v error -y -i "$OUT/soundtrack.wav" -b:a 320k "$OUT/soundtrack.mp3"

echo
echo "  $OUT/soundtrack.wav"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$OUT/soundtrack.wav"
echo "  measured loudness:"
ffmpeg -nostdin -v error -i "$OUT/soundtrack.wav" -af ebur128=peak=true -f null - 2>&1 | tail -8 | sed 's/^/    /'
