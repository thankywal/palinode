"""Turn the narration into audio, one file per segment.

Per segment rather than one long file, because the video is cut to the audio
rather than the other way round. Each segment's footage holds for exactly as
long as its line takes, so nothing needs nudging into sync afterwards.

    python speak.py

Writes audio/vo/<id>.wav and audio/vo/timing.json.
"""

from __future__ import annotations

import base64
import json
import pathlib
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from narration import SEGMENTS  # noqa: E402

VOICE = "en-US-Studio-Q"
RATE = 0.95
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
    OUT.mkdir(parents=True, exist_ok=True)
    bearer, proj = token(), project()

    timing = []
    total = 0.0
    for segment in SEGMENTS:
        path = OUT / f"{segment['id']}.wav"
        path.write_bytes(synthesize(segment["text"], bearer, proj))
        seconds = duration(path)
        total += seconds
        timing.append({
            "id": segment["id"],
            "visual": segment["visual"],
            "seconds": seconds,
        })
        print(f"  {segment['id']:<20} {seconds:>6.2f}s   {segment['visual']}")

    (OUT / "timing.json").write_text(json.dumps(timing, indent=2))
    print(f"\n  narration total {total:.1f}s  ({total / 60:.2f} minutes)")


if __name__ == "__main__":
    main()
