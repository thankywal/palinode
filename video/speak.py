"""Turn the narration into audio, one performance per segment, and measure it.

    python speak.py                 # only segments whose text or settings changed
    python speak.py --all           # everything, and it costs what it costs

Writes audio/vo/<segment>.wav, cuts it into audio/vo/<segment>-<n>.wav at the
line boundaries, and writes audio/vo/timing.json carrying the measured length
of every line and the absolute time each one starts in the finished film.
Everything downstream reads that file and nothing downstream guesses.

Google Cloud TTS, Chirp3 HD, Charon. ElevenLabs is still here behind
PALINODE_TTS=elevenlabs; it reads with more range and it is metered, and the
thing that actually went wrong was never the voice.

## One request per segment, not one per line

The picture is cut at line boundaries, so an earlier version of this file asked
for each line separately: thirty four requests, one per cut. It sounded wrong
and the reason is worth writing down, because the fix had nothing to do with
which service was answering.

A text to speech request carries no memory of the one before it. Ask for thirty
four lines separately and you get thirty four independent performances of the
same voice, each rolling its own pitch, energy and pace. Measured across that
cut, the mean pitch was 147.6 Hz and the lines ranged from 135 to 162. Twenty
seven hertz is about three semitones, between one sentence and the next. A
listener heard the voice change partway through and was right.

So a segment is one request now, and one performance. The breath between its
lines is asked for in the text, and the file is cut afterwards to get the per
line boundaries the picture needs. The cut lands in silence, so concatenating
the pieces back gives the take unchanged, sample for sample: the pauses are
part of the performance rather than something spliced in around it.

How you ask for the breath depends on the engine. ElevenLabs takes a break tag
and gives the length you name. Chirp3 refuses SSML entirely, so it is asked the
way a script asks a person: a blank line, which buys about half a second.

## Where the lines actually start

Cutting a paragraph into lines needs to know where each one begins, and three
increasingly careful ways of inferring that from the audio are in this file:
longest pauses, then pauses weighted by how long each line ought to be, then
line lengths measured by speaking each one alone. All three are inference. The
last of them still put a boundary in segment two 2.4 seconds out, and from
inside the inference there was no way to know.

Speech to Text returns the start time of every word. That is the thing all the
inference was approximating, so it is asked directly, and the transcript is
matched to the script with a sequence diff so the disagreements that do not
matter are absorbed. Measured against the transcript, the inference was within
0.25s on nine of the ten boundaries tested and 2.40s out on the tenth, which is
a cut landing in the middle of the wrong sentence.

The inference is kept as a fallback for when the service is unreachable, which
is the honest arrangement: a rebuild without Speech to Text is still possible
and is merely less exact, and it says so when it falls back.
"""

from __future__ import annotations

import base64
import difflib
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

ENGINE = os.getenv("PALINODE_TTS", "google").strip().lower()

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
# Chirp3 reads faster than Daniel does at the same nominal rate, and the script
# has since lost nine percent of its words, so the rate that suited the old
# longer script would now finish well short of four minutes. Measured rather
# than assumed: see the note on the run in the module docstring.
GOOGLE_RATE = 0.92
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
    """The segment as one utterance, with the breaths asked for out loud.

    How you ask depends on who is listening. ElevenLabs takes a break tag and
    gives you the length you name. Chirp3 does not accept SSML at all, so the
    breath has to be asked for the way it is asked for in a script: a blank
    line. It obliges with roughly half a second, which is shorter than the tag
    would give and long enough to find afterwards.
    """
    if ENGINE == "google":
        return "\n\n".join(lines)
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
    body = json.dumps({
        # Plain text, not SSML: Chirp3 voices reject it. before and after are
        # not sent either, because this API has nowhere to put them. It is a
        # smaller loss than it sounds, since the drift being fixed here was
        # between lines and those are now inside one request.
        "input": {"text": spoken(lines)},
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


STT_URL = "https://speech.googleapis.com/v1/speech:recognize"


def normalise(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def align(path: pathlib.Path, lines: list[str]) -> list[float] | None:
    """Ask where each line actually starts, instead of working it out.

    Everything else in this file is a way of guessing where one line ends and
    the next begins from the shape of the audio: pause lengths, expected
    durations, a scoring function to reconcile them. It is all inference, it
    was wrong by a second and a half in the segment that argues in short
    sentences, and there was no way to tell from inside it whether a given cut
    was right.

    Speech to Text returns the start time of every word it hears. That is the
    thing the guessing was trying to approximate, so ask for it. The script is
    matched against the transcript with a plain sequence diff, which absorbs
    the disagreements that do not matter: the voice says four thousand two
    hundred and the recogniser writes 4200, the recogniser drops a the. What
    survives is the position of each line's first word, in seconds.

    Returns None if the service is not reachable or the transcript is too far
    from the script to trust, and the caller falls back to inference. Costs
    about a tenth of a cent per segment.
    """
    audio = base64.b64encode(path.read_bytes()).decode()
    body = json.dumps({
        "config": {
            "encoding": "LINEAR16",
            "sampleRateHertz": 24000,
            "languageCode": "en-US",
            "enableWordTimeOffsets": True,
            "model": "latest_long",
        },
        "audio": {"content": audio},
    }).encode()
    request = urllib.request.Request(
        STT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {shell('gcloud', 'auth', 'print-access-token')}",
            "x-goog-user-project": shell("gcloud", "config", "get-value", "project"),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.load(response)
    except Exception as why:  # noqa: BLE001 - any failure means fall back
        print(f"    (speech to text unavailable: {why})")
        return None

    heard = [
        (normalise(w["word"]), float(w["startTime"].rstrip("s")))
        for result in payload.get("results", [])
        for w in result["alternatives"][0].get("words", [])
    ]
    if not heard:
        return None

    script = [normalise(w) for line in lines for w in line.split()]
    first = []
    run = 0
    for line in lines[:-1]:
        run += len(line.split())
        first.append(run)

    matcher = difflib.SequenceMatcher(None, script, [w for w, _ in heard],
                                      autojunk=False)
    same = sum(block.size for block in matcher.get_matching_blocks())
    if same < 0.75 * len(script):
        print(f"    (transcript matched only {same}/{len(script)} words, "
              f"falling back)")
        return None

    # Where each script word ended up in the transcript.
    where: dict[int, int] = {}
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            where[a + k] = b + k

    cuts = []
    for index in first:
        # The first word of the next line, or the nearest one after it that
        # the recogniser and the script agree on.
        nudge = next((index + k for k in range(6) if index + k in where), None)
        if nudge is None:
            return None
        start = heard[where[nudge]][1]
        previous = heard[where[nudge] - 1][1] if where[nudge] else 0.0
        # Cut in the gap before the word, not on its first sound.
        cuts.append(max(previous + 0.05, start - 0.22))

    if any(b <= a for a, b in zip(cuts, cuts[1:])):
        return None
    return cuts


def widths(lines: list[str], stem: str) -> list[float]:
    """How long each line is, in whatever unit we can afford to measure it in.

    Characters are the free answer and a rough one. They cannot tell that "four
    thousand two hundred dollars" is read slowly and "prevention failing" is
    read quickly, and in segment two two lines of 109 and 112 characters are
    genuinely 9.0s and 6.2s apart. Guessing from length put the boundary
    between them more than a second out.

    So on Google, where a synthesis request costs a fraction of a cent, each
    line is also spoken alone once and its duration measured. That audio is
    never used in the film; only its length is, and only as a proportion. It is
    a far better prior than character count, and it is cached so the price is
    paid once. On ElevenLabs, where the same trick would double a metered
    budget, characters remain the estimate.
    """
    if ENGINE != "google":
        return [float(len(line)) for line in lines]

    room = OUT / "measure"
    room.mkdir(exist_ok=True)
    out = []
    for n, line in enumerate(lines, start=1):
        one = room / f"{stem}-{n}.wav"
        if not one.is_file():
            say_google([line], one, "", "")
        out.append(duration(one))
    return out


def boundaries(lines: list[str], total: float, quiet: list[tuple[float, float]],
               widths: list[float]) -> list[float]:
    """Work out which of the pauses in a take are the ones we asked for.

    The obvious rule is that the breaths are the longest pauses, and for most
    segments it is right. It is not right for segment two, which argues in
    short sentences: the fifth breath came back 0.91s and a full stop inside a
    line came back 0.83s. Nothing about length separates those, and guessing
    wrong does not shift one cut, it shifts every cut after it.

    So pause length is only half the evidence. The other half is knowing how
    long each line ought to be, which says roughly where its boundary belongs,
    and a full stop in the middle of a line is nowhere near there. Scoring both
    together and taking the best run of pauses in order gets it right where
    either signal alone does not.
    """
    want = len(lines) - 1
    breath = sorted((e - s for s, e in quiet), reverse=True)[:want]
    breath = sum(breath) / len(breath)

    # Where each boundary lands if the voice spends time on each line in
    # proportion to what that line measured on its own.
    speech = max(total - want * breath, total * 0.5)
    expect, run = [], 0.0
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

    cuts = align(path, lines)
    if cuts is None:
        quiet = pauses(path)
        if len(quiet) < want:
            raise SystemExit(
                f"{stem}: asked for {want} breaks, found {len(quiet)} pauses. "
                f"The take cannot be cut to the script."
            )
        cuts = boundaries(lines, duration(path), quiet, widths(lines, stem))

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
