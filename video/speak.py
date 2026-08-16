"""Turn the narration into audio, one file per line, and measure every one.

Per line rather than per segment, because the picture is cut at line
boundaries. A segment that names four things in sentences of very different
lengths cannot be sliced into four equal pieces, and that is exactly what an
earlier cut did.

    python speak.py                 # only what is missing or changed
    python speak.py --all           # everything, and it costs what it costs

Writes audio/vo/<segment>-<n>.wav and audio/vo/timing.json, where timing.json
carries the measured length of every line and the absolute time each one
starts in the finished film, gaps included. Everything downstream reads that
file and nothing downstream guesses.

## The voice

ElevenLabs, Daniel. The account is a free tier with ten thousand characters on
it and this script is three thousand nine hundred, so a full pass is a
quarter of the budget and a habit of re-running it is not affordable. Hence
the manifest: a line whose text has not changed is not synthesised again.

Settings were picked by measuring rather than by ear, the same way the
previous voice was. On one line:

    stability 0.45, style 0.35            spread 38.3   swing 12.2 dB
    stability 0.30, style 0.55            spread 43.6   swing 14.3 dB
    the same, plus speed 1.12             spread 35.3   swing 10.5 dB

Looser settings read with more range. Speeding the read takes that range
straight back out, which is worth knowing before reaching for it: it is a
running time control and an expression control at the same time, pulling in
opposite directions. The script is about somebody losing money, so the range
wins and the speed is only nudged.

Google Cloud TTS is still here behind PALINODE_TTS=google, because a demo that
cannot be rebuilt without somebody else's API key is a demo with a hostage.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from narration import GAP_LINE, GAP_SEGMENT, SEGMENTS  # noqa: E402

OUT = pathlib.Path(__file__).parent / "audio" / "vo"
MANIFEST = OUT / "manifest.json"

ENGINE = os.getenv("PALINODE_TTS", "elevenlabs").strip().lower()

# ---------------------------------------------------------------- elevenlabs

ELEVEN_VOICE = "onwK4e9ZLuTAKqWW03F9"  # Daniel, steady broadcaster
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_SETTINGS = {
    "stability": 0.30,
    "similarity_boost": 0.75,
    "style": 0.55,
    "use_speaker_boost": True,
    # This is the compromise and it is worth writing down rather than
    # discovering again. At its natural pace Daniel reads this script in five
    # minutes five, against the four the brief asks for. Eight percent came
    # out of the words, which was every sentence that could lose one without
    # losing a fact. The rest has to come from the pace, and pace costs
    # expression: 1.12 measured a 10.5 dB swing where 1.00 measured 14.3.
    #
    # 1.16 lands the film near four minutes ten. It is flatter than the voice
    # can be and still less flat than a script read as a list.
    "speed": 1.16,
}
ELEVEN_URL = (
    f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}"
    "?output_format=mp3_44100_128"
)

# ------------------------------------------------------------------- google

GOOGLE_VOICE = "en-US-Chirp3-HD-Charon"
GOOGLE_RATE = 1.1
GOOGLE_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def shell(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def eleven_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    # Never in the repository. The file is chmod 600 in the user's config.
    path = pathlib.Path.home() / ".config" / "palinode" / "elevenlabs.env"
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(
        "no ELEVENLABS_API_KEY. Put it in ~/.config/palinode/elevenlabs.env "
        "or run with PALINODE_TTS=google."
    )


def say_elevenlabs(text: str, path: pathlib.Path) -> None:
    body = json.dumps({
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": ELEVEN_SETTINGS,
    }).encode()
    request = urllib.request.Request(
        ELEVEN_URL,
        data=body,
        headers={"xi-api-key": eleven_key(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        mp3 = response.read()

    raw = path.with_suffix(".mp3")
    raw.write_bytes(mp3)
    # Everything downstream expects 24k mono wav, which is what the previous
    # engine returned and what mixdown concatenates.
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw),
         "-ar", "24000", "-ac", "1", str(path)],
        check=True,
    )
    raw.unlink()


def say_google(text: str, path: pathlib.Path) -> None:
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": GOOGLE_VOICE},
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": 24000,
            "speakingRate": GOOGLE_RATE,
            "volumeGainDb": 0.0,
        },
    }).encode()
    request = urllib.request.Request(
        GOOGLE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {shell('gcloud', 'auth', 'print-access-token')}",
            "x-goog-user-project": shell("gcloud", "config", "get-value", "project"),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    path.write_bytes(base64.b64decode(payload["audioContent"]))


SAY = {"elevenlabs": say_elevenlabs, "google": say_google}


def duration(path: pathlib.Path) -> float:
    out = shell("ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path))
    return round(float(out), 3)


def fingerprint(text: str) -> str:
    """What was said, and how. Change either and the line is spoken again."""
    settings = ELEVEN_SETTINGS if ENGINE == "elevenlabs" else {"rate": GOOGLE_RATE}
    payload = json.dumps([ENGINE, text, settings], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def main() -> None:
    force = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {} if force else json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    manifest: dict[str, str] = {}

    spoken = chars = 0
    clock = 0.0
    segments = []

    for index, segment in enumerate(SEGMENTS):
        lines = []
        seg_start = clock

        for n, text in enumerate(segment["lines"], start=1):
            name = f"{segment['id']}-{n}.wav"
            path = OUT / name
            mark = fingerprint(text)
            manifest[name] = mark

            if seen.get(name) != mark or not path.is_file():
                SAY[ENGINE](text, path)
                spoken += 1
                chars += len(text)

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

    # Anything left over is a line that was deleted from the script.
    for stale in OUT.glob("*.wav"):
        if stale.name not in manifest:
            stale.unlink()
            print(f"  dropped {stale.name}, no longer in the script")

    MANIFEST.write_text(json.dumps(manifest, indent=2))
    (OUT / "timing.json").write_text(json.dumps({
        "engine": ENGINE,
        "gap_line": GAP_LINE,
        "gap_segment": GAP_SEGMENT,
        "total": round(clock, 3),
        "segments": segments,
    }, indent=2))

    print(f"\n  narration total {clock:.2f}s  ({clock / 60:.2f} minutes)")
    print(f"  spoke {spoken} of {sum(len(s['lines']) for s in SEGMENTS)} lines, "
          f"{chars:,} characters")


if __name__ == "__main__":
    main()
