"""Turn the narration into audio, one file per line, and measure every one.

Per line rather than per segment, because the picture is cut at line
boundaries. A segment that names four things in sentences of very different
lengths cannot be sliced into four equal pieces, and that is exactly what an
earlier cut did.

    python speak.py

Writes audio/vo/<segment>-<n>.wav and audio/vo/timing.json, where timing.json
carries the measured length of every line and the absolute time each one
starts in the finished film, gaps included. Everything downstream reads that
file and nothing downstream guesses.
"""

from __future__ import annotations

import base64
import json
import pathlib
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from narration import GAP_LINE, GAP_SEGMENT, SEGMENTS  # noqa: E402

# Chirp3 rather than Studio. Auditioned five voices on one line and measured
# how far each read moves: Charon swings 14.4 dB in loudness against Studio-Q's
# 11.3, sits lower at 121 Hz, and has a comparable pitch spread. The Studio
# voices are built to be neutral, which is the right choice for a script that
# is a list and the wrong one for a script about somebody losing money.
VOICE = "en-US-Chirp3-HD-Charon"

# Charon reads slower than Studio-Q did, and at its natural pace this script
# runs to four minutes twenty. The brief asks for about four. Ten percent
# faster brings it to three fifty five and costs nothing anyone can hear.
RATE = 1.1
OUT = pathlib.Path(__file__).parent / "audio" / "vo"
ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"


def token() -> str:
    return subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def project() -> str:
    return subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def synthesize(text: str, bearer: str, proj: str) -> bytes:
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": VOICE},
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": 24000,
            "speakingRate": RATE,
            # A touch of headroom. The music sits under this and a voice
            # recorded hot leaves nowhere to put it.
            "volumeGainDb": 0.0,
        },
    }).encode()

    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {bearer}",
            "x-goog-user-project": proj,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return base64.b64decode(payload["audioContent"])


def duration(path: pathlib.Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return round(float(out), 3)


def main() -> None:
    for stale in OUT.glob("*.wav"):
        stale.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    bearer, proj = token(), project()

    # Absolute time in the finished film. Advanced by each line and by each
    # gap, so a line's start is where the picture for it has to change.
    clock = 0.0
    segments = []

    for index, segment in enumerate(SEGMENTS):
        lines = []
        seg_start = clock

        for n, text in enumerate(segment["lines"], start=1):
            name = f"{segment['id']}-{n}.wav"
            path = OUT / name
            path.write_bytes(synthesize(text, bearer, proj))
            seconds = duration(path)

            lines.append({
                "file": name,
                "text": text,
                "start": round(clock, 3),
                "seconds": seconds,
            })
            clock += seconds
            if n < len(segment["lines"]):
                clock += GAP_LINE

        segments.append({
            "id": segment["id"],
            "visual": segment["visual"],
            "start": round(seg_start, 3),
            "seconds": round(clock - seg_start, 3),
            "lines": lines,
        })
        print(f"  {segment['id']:<20} {clock - seg_start:>6.2f}s  "
              f"{len(lines)} lines   {segment['visual']}")

        if index < len(SEGMENTS) - 1:
            clock += GAP_SEGMENT

    timing = {
        "gap_line": GAP_LINE,
        "gap_segment": GAP_SEGMENT,
        "total": round(clock, 3),
        "segments": segments,
    }
    (OUT / "timing.json").write_text(json.dumps(timing, indent=2))
    print(f"\n  narration total {clock:.2f}s  ({clock / 60:.2f} minutes)")


if __name__ == "__main__":
    main()
