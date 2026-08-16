"""Turn the narration into audio, one performance per segment, and measure it.

    python speak.py                 # only segments whose text or settings changed
    python speak.py --all           # everything, and it costs what it costs

Writes audio/vo/<segment>.wav, cuts it into audio/vo/<segment>-<n>.wav at the
pauses, and writes audio/vo/timing.json carrying the measured length of every
line and the absolute time each one starts in the finished film. Everything
downstream reads that file and nothing downstream guesses.

## One request per segment, not one per line

The picture is cut at line boundaries, so an earlier version of this file asked
for each line separately: thirty four requests, one per cut. It sounded wrong
and the reason is worth writing down.

A text to speech request carries no memory of the one before it. Ask for
thirty four lines separately and you get thirty four independent performances
of the same voice, each rolling its own pitch, energy and pace. Measured across
that cut, the mean pitch was 147.6 Hz and the lines ranged from 135 to 162.
Twenty seven hertz is about three semitones. It reads as the speaker changing
between sentences, which is exactly what a listener said they heard.

So a segment is now one request and one performance. The pauses between its
lines are asked for in the text, with a break tag, and the voice takes the
breath itself. Then the file is cut at those pauses to get the per line
boundaries the picture needs. The cut lands in the middle of silence, so
concatenating the pieces back gives the segment unchanged, sample for sample:
the pauses are part of the take rather than something spliced in around it.

Across segment joins there is nothing to be done about it except tell the model
what came before and what comes next, which is what previous_text and next_text
are for, and let it pitch the entry accordingly.

## The settings

Picked by measuring rather than by ear. On one line:

    stability 0.45, style 0.35            spread 38.3   swing 12.2 dB
    stability 0.30, style 0.55            spread 43.6   swing 14.3 dB
    the same, plus speed 1.12             spread 35.3   swing 10.5 dB

Looser settings read with more range, and speeding the read takes that range
straight back out. Pace and expression are one dial pulled in two directions.

Both moved for this pass. Stability up, because low stability is precisely the
setting that lets one request wander away from the next, and within a single
performance the model keeps its own range without being told to. Speed down
from 1.16 to 1.08, because 1.16 was heard as rushed and it was: the running
time it was buying should have been bought out of the script, and this time it
was.

Google Cloud TTS is still here behind PALINODE_TTS=google, because a demo that
cannot be rebuilt without somebody else's API key is a demo with a hostage.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from narration import BREAK_LINE, GAP_LINE, GAP_SEGMENT, SEGMENTS  # noqa: E402

OUT = pathlib.Path(__file__).parent / "audio" / "vo"
MANIFEST = OUT / "manifest.json"

ENGINE = os.getenv("PALINODE_TTS", "elevenlabs").strip().lower()

# ---------------------------------------------------------------- elevenlabs

ELEVEN_VOICE = "onwK4e9ZLuTAKqWW03F9"  # Daniel, steady broadcaster
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_SETTINGS = {
    # High enough that the voice holds its character across a long paragraph,
    # low enough that it still has somewhere to go. The 0.30 that measured
    # best on a single line was measuring the freedom to differ from the takes
    # around it, which is the thing being removed here.
    "stability": 0.50,
    "similarity_boost": 0.80,
    "style": 0.40,
    "use_speaker_boost": True,
    # 1.16 was rushed. The nine percent it was buying came out of the words
    # instead, so the read can sit where a person would sit.
    "speed": 1.08,
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


def ffmpeg(*args: str) -> str:
    done = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "info", "-y", *args],
        capture_output=True, text=True,
    )
    if done.returncode:
        raise SystemExit(done.stderr[-2000:])
    return done.stderr


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


def spoken(lines: list[str]) -> str:
    """The segment as one utterance, with the breaths asked for out loud."""
    return f' <break time="{BREAK_LINE}s" /> '.join(lines)


def say_elevenlabs(
    lines: list[str], path: pathlib.Path, before: str, after: str
) -> None:
    body = json.dumps({
        "text": spoken(lines),
        "model_id": ELEVEN_MODEL,
        "voice_settings": ELEVEN_SETTINGS,
        # Not spoken. They tell the model where this paragraph sits, so it does
        # not open every segment as if it were the first thing said.
        "previous_text": before,
        "next_text": after,
    }).encode()
    request = urllib.request.Request(
        ELEVEN_URL,
        data=body,
        headers={"xi-api-key": eleven_key(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        mp3 = response.read()

    raw = path.with_suffix(".mp3")
    raw.write_bytes(mp3)
    # Everything downstream expects 24k mono wav.
    ffmpeg("-i", str(raw), "-ar", "24000", "-ac", "1", str(path))
    raw.unlink()


def say_google(
    lines: list[str], path: pathlib.Path, before: str, after: str
) -> None:
    ssml = "<speak>" + f'<break time="{BREAK_LINE}s"/>'.join(lines) + "</speak>"
    body = json.dumps({
        "input": {"ssml": ssml},
        "voice": {"languageCode": "en-US", "name": GOOGLE_VOICE},
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": 24000,
            "speakingRate": GOOGLE_RATE,
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
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    path.write_bytes(base64.b64decode(payload["audioContent"]))


SAY = {"elevenlabs": say_elevenlabs, "google": say_google}


def duration(path: pathlib.Path) -> float:
    out = shell("ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path))
    return round(float(out), 3)


def pauses(path: pathlib.Path, floor: float = 0.30) -> list[tuple[float, float]]:
    """Every stretch of quiet in the take, longest first."""
    log = ffmpeg("-i", str(path), "-af", f"silencedetect=noise=-42dB:d={floor}",
                 "-f", "null", "-")
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    total = duration(path)
    if len(ends) < len(starts):
        ends.append(total)
    found = [(s, e) for s, e in zip(starts, ends) if s > 0.15 and e < total - 0.15]
    return sorted(found, key=lambda p: p[0] - p[1])


def boundaries(lines: list[str], total: float, quiet: list[tuple[float, float]]
               ) -> list[float]:
    """Work out which of the pauses in a take are the ones we asked for.

    The obvious rule is that the breaths are the longest pauses, and for most
    segments it is right. It is not right for segment two, which argues in
    short sentences: the fifth breath came back 0.91s and a full stop inside a
    line came back 0.83s. Nothing about length separates those, and guessing
    wrong does not shift one cut, it shifts every cut after it.

    So length is only half the evidence. The other half is that we know how
    long each line is in characters, which says roughly where its boundary
    ought to fall, and a full stop in the middle of a line is nowhere near
    there. Scoring both together and taking the best run of pauses in order
    gets it right where either signal alone does not.
    """
    want = len(lines) - 1
    widths = [len(line) for line in lines]
    breath = sorted((e - s for s, e in quiet), reverse=True)[:want]
    breath = sum(breath) / len(breath)

    # Where each boundary would land if the voice spent time on a line in
    # proportion to its length, which is close enough to find the right pause.
    speech = max(total - want * breath, total * 0.5)
    expect, run = [], 0
    for n in range(want):
        run += widths[n]
        expect.append(run / sum(widths) * speech + n * breath + breath / 2)

    mids = [(s + e) / 2 for s, e in quiet]
    lengths = [e - s for s, e in quiet]
    order = sorted(range(len(quiet)), key=lambda i: mids[i])

    # A pause 0.1s longer is worth 0.2s of being in the wrong place.
    def cost(boundary: int, cand: int) -> float:
        return abs(mids[cand] - expect[boundary]) - 2.0 * lengths[cand]

    best: dict[tuple[int, int], tuple[float, list[int]]] = {}

    def solve(boundary: int, first: int) -> tuple[float, list[int]]:
        if boundary == want:
            return 0.0, []
        if (boundary, first) in best:
            return best[(boundary, first)]
        answer = (float("inf"), [])
        for slot in range(first, len(order) - (want - boundary) + 1):
            rest, tail = solve(boundary + 1, slot + 1)
            here = cost(boundary, order[slot]) + rest
            if here < answer[0]:
                answer = (here, [order[slot], *tail])
        best[(boundary, first)] = answer
        return answer

    _, chosen = solve(0, 0)
    return [mids[i] for i in chosen]


def carve(path: pathlib.Path, lines: list[str], stem: str) -> list[pathlib.Path]:
    """Cut one performance into its lines, in the middle of the breaths."""
    want = len(lines) - 1
    if want == 0:
        piece = path.with_name(f"{stem}-1.wav")
        ffmpeg("-i", str(path), "-c", "copy", str(piece))
        return [piece]

    quiet = pauses(path)
    if len(quiet) < want:
        raise SystemExit(
            f"{stem}: asked for {want} breaks, found {len(quiet)} pauses. "
            f"The take cannot be cut to the script."
        )
    cuts = boundaries(lines, duration(path), quiet)

    edges = [0.0, *cuts, duration(path)]
    pieces = []
    for n in range(len(lines)):
        piece = path.with_name(f"{stem}-{n + 1}.wav")
        # Sample accurate, and nothing is dropped: piece n ends exactly where
        # piece n+1 begins, so the concatenation is the take again.
        ffmpeg("-i", str(path), "-ss", f"{edges[n]:.4f}", "-to", f"{edges[n+1]:.4f}",
               "-c", "copy", str(piece))
        pieces.append(piece)
    return pieces


def fingerprint(lines: list[str]) -> str:
    """What was said, and how. Change either and the segment is spoken again."""
    settings = ELEVEN_SETTINGS if ENGINE == "elevenlabs" else {"rate": GOOGLE_RATE}
    payload = json.dumps([ENGINE, lines, settings, BREAK_LINE], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def main() -> None:
    force = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {} if force else json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    manifest: dict[str, str] = {}

    spoke = chars = 0
    clock = 0.0
    segments = []
    keep: set[str] = set()

    for index, segment in enumerate(SEGMENTS):
        lines = segment["lines"]
        stem = segment["id"]
        take = OUT / f"{stem}.wav"
        mark = fingerprint(lines)
        manifest[f"{stem}.wav"] = mark
        keep.add(take.name)
        keep.update(f"{stem}-{n + 1}.wav" for n in range(len(lines)))

        pieces = [OUT / f"{stem}-{n + 1}.wav" for n in range(len(lines))]
        if seen.get(f"{stem}.wav") != mark or not all(p.is_file() for p in pieces):
            before = " ".join(SEGMENTS[index - 1]["lines"]) if index else ""
            after = SEGMENTS[index + 1]["lines"][0] if index + 1 < len(SEGMENTS) else ""
            SAY[ENGINE](lines, take, before, after)
            carve(take, lines, stem)
            spoke += 1
            chars += len(spoken(lines))

        seg_start = clock
        measured = []
        for n, text in enumerate(lines, start=1):
            path = OUT / f"{stem}-{n}.wav"
            seconds = duration(path)
            measured.append({
                "file": path.name,
                "text": text,
                "start": round(clock, 3),
                "seconds": seconds,
            })
            clock += seconds + (GAP_LINE if n < len(lines) else 0.0)

        segments.append({
            "id": stem,
            "visual": segment["visual"],
            "start": round(seg_start, 3),
            "seconds": round(clock - seg_start, 3),
            "lines": measured,
        })
        print(f"  {stem:<20} {clock - seg_start:>6.2f}s  {len(lines)} lines   "
              f"{segment['visual']}")

        if index < len(SEGMENTS) - 1:
            clock += GAP_SEGMENT

    for stale in OUT.glob("*.wav"):
        if stale.name not in keep:
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
    print(f"  spoke {spoke} of {len(SEGMENTS)} segments, {chars:,} characters")


if __name__ == "__main__":
    main()
