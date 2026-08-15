"""Generate the music bed with Lyria on Vertex AI.

    python score.py

The bed used to be one calm ambient loop under the whole film, which suited a
narration that read like a list and suits nothing about the one that replaced
it. This asks Lyria for something with a pulse.

Two pieces rather than one, because the film has two temperatures. The body of
it is an incident happening at speed. The close is somebody telling you what it
cost. Cutting between them at the last segment is the only edit in the whole
soundtrack that is a taste decision rather than a measurement, and it is here
in one place where it can be argued with.

Lyria returns about thirty seconds per call, so each piece is generated a few
times and mixdown.sh loops whichever it needs. Writes audio/score/*.wav.
"""

from __future__ import annotations

import base64
import json
import pathlib
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "audio" / "score"
MODEL = "lyria-002"

PIECES = {
    "drive": {
        "takes": 4,
        "prompt": (
            "Driving cinematic electronic underscore for a technology film. "
            "Insistent sixteenth note synth arpeggio, tight punchy kick on "
            "every beat, crisp hi hats, deep sub bass. Tense and forward "
            "moving, building pressure, modern and clean. No vocals. "
            "Around 120 beats per minute in D minor."
        ),
        "negative": "orchestral, acoustic guitar, vocals, lo-fi, ambient pads only, slow",
    },
    "close": {
        "takes": 2,
        "prompt": (
            "Cinematic electronic outro. The same pulse settling: a slower "
            "warm synth chord progression over a soft heartbeat kick, one "
            "sustained bass note, quiet and resolved but not sad. Modern, "
            "spacious, hopeful. No vocals. Around 90 beats per minute in D "
            "minor."
        ),
        "negative": "busy percussion, arpeggios, vocals, orchestral strings",
    },
}


def endpoint(project: str) -> str:
    # Lyria is served from a region, unlike the Gemini models which this
    # project reaches at the global endpoint. Getting that backwards cost an
    # afternoon once already.
    return (
        "https://us-central1-aiplatform.googleapis.com/v1/projects/"
        f"{project}/locations/us-central1/publishers/google/models/{MODEL}:predict"
    )


def shell(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def generate(name: str, spec: dict, take: int, bearer: str, project: str) -> pathlib.Path:
    body = json.dumps({
        "instances": [{
            "prompt": spec["prompt"],
            "negative_prompt": spec["negative"],
            # Fixed, so a rerun of this script produces the same score rather
            # than a different film.
            "seed": 1400 + take,
        }],
        "parameters": {"sample_count": 1},
    }).encode()

    request = urllib.request.Request(
        endpoint(project),
        data=body,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.load(response)

    audio = payload["predictions"][0]["bytesBase64Encoded"]
    path = OUT / f"{name}-{take}.wav"
    path.write_bytes(base64.b64decode(audio))
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bearer = shell("gcloud", "auth", "print-access-token")
    project = shell("gcloud", "config", "get-value", "project")

    for name, spec in PIECES.items():
        for take in range(spec["takes"]):
            try:
                path = generate(name, spec, take, bearer, project)
            except Exception as exc:  # noqa: BLE001
                print(f"  {name}-{take} failed: {str(exc)[:120]}", file=sys.stderr)
                continue
            seconds = shell(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path),
            )
            print(f"  {path.name:<14} {float(seconds):.1f}s")


if __name__ == "__main__":
    main()
