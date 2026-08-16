"""Write the subtitle file and the chapter list, from measured word times.

    python captions.py

Writes out/palinode-demo.srt and prints the chapter list for the YouTube
description.

Subtitles could be faked from timing.json alone: every line's start and length
is already measured, so a long line could be chopped into two cues by splitting
its duration in proportion to its characters. That is the same inference
speak.py had to abandon, and it fails the same way. "Four thousand two hundred
dollars" takes far longer to say than its character count suggests, so a cue
boundary placed by proportion drifts, and a subtitle that appears half a second
before its words is worse than no subtitle.

So the word times come from Speech to Text, the same call speak.py makes to
find the line boundaries, and the script is matched to the transcript with a
sequence diff so the recogniser's disagreements do not become the caption.
Every cue starts when its first word is actually spoken.

The text of the cue is always the script, never the transcript. The transcript
is only ever consulted for when.
"""

from __future__ import annotations

import base64
import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import speak  # noqa: E402
from narration import SEGMENTS  # noqa: E402

VO = pathlib.Path(__file__).parent / "audio" / "vo"
OUT = pathlib.Path(__file__).parent / "out"

# A caption is read at a glance, not studied. Two lines, and short enough that
# the eye takes the whole cue in one movement rather than tracking across it.
WIDEST = 42
LINES = 2
BRIEFEST = 1.2

# The chapters, as the argument breaks rather than as the segments break: two
# segments that are one idea get one chapter, and a chapter shorter than ten
# seconds is not a chapter as far as YouTube is concerned.
CHAPTERS = [
    ("01-hook", "A palinode is a poem that takes back an earlier poem"),
    ("02-two-invoices", "Two invoices, and the one that gets through"),
    ("03-fleet-acts", "The fleet acts, and one action cannot be undone"),
    ("04-sentinel", "Nobody presses a button"),
    ("05-what-came-back", "Four come back, one does not"),
    ("07-weeks-later", "The other kind of incident, three weeks late"),
    ("08-it-was-real", "Stripe, GitHub and Slack, after the fact"),
    ("09-google-cloud", "Where it runs"),
    ("10-close", "What connecting the real systems broke"),
]


def heard(path: pathlib.Path) -> list[tuple[str, float, float]]:
    """Every word in a take, with when it starts and when it ends."""
    body = json.dumps({
        "config": {
            "encoding": "LINEAR16",
            "sampleRateHertz": 24000,
            "languageCode": "en-US",
            "enableWordTimeOffsets": True,
            "model": "latest_long",
        },
        "audio": {"content": base64.b64encode(path.read_bytes()).decode()},
    }).encode()
    import urllib.request

    request = urllib.request.Request(
        speak.STT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {speak.shell('gcloud', 'auth', 'print-access-token')}",
            "x-goog-user-project": speak.shell("gcloud", "config", "get-value", "project"),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.load(response)

    return [
        (speak.normalise(w["word"]),
         float(w["startTime"].rstrip("s")),
         float(w["endTime"].rstrip("s")))
        for result in payload.get("results", [])
        for w in result["alternatives"][0].get("words", [])
    ]


def when(script: list[str], spoken: list[tuple[str, float, float]], last: float
         ) -> list[tuple[float, float]]:
    """Line up the script against what was heard, and keep the times.

    Every script word gets a time, including the ones the recogniser did not
    agree with. Dropping those was the first version and it put a cue's end at
    the last word it happened to recognise: "Four come back" was on screen for
    0.16 seconds because "back" was not matched and "four" was. A word between
    two anchors is placed between them instead, which is inference, but over a
    gap of one or two words rather than over a whole line.
    """
    matcher = difflib.SequenceMatcher(
        None, [speak.normalise(w) for w in script], [w for w, _, _ in spoken],
        autojunk=False,
    )
    found: dict[int, tuple[float, float]] = {}
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            found[a + k] = (spoken[b + k][1], spoken[b + k][2])

    anchors = sorted(found)
    if not anchors:
        step = last / max(1, len(script))
        return [(i * step, (i + 1) * step) for i in range(len(script))]

    times: list[tuple[float, float]] = []
    for i in range(len(script)):
        if i in found:
            times.append(found[i])
            continue
        before = max((a for a in anchors if a < i), default=None)
        after = min((a for a in anchors if a > i), default=None)
        if before is None:
            start, end = 0.0, found[after][0]
        elif after is None:
            start, end = found[before][1], last
        else:
            start, end = found[before][1], found[after][0]
        # Share the gap out between however many words fell into it.
        missing = [j for j in range(len(script))
                   if j not in found
                   and (before is None or j > before)
                   and (after is None or j < after)]
        share = (end - start) / max(1, len(missing))
        seat = missing.index(i)
        times.append((start + seat * share, start + (seat + 1) * share))
    return times


def wrap(words: list[str]) -> list[str]:
    """Break a cue into lines that can be read without tracking."""
    rows, row = [], ""
    for word in words:
        if row and len(row) + 1 + len(word) > WIDEST:
            rows.append(row)
            row = word
        else:
            row = f"{row} {word}".strip()
    if row:
        rows.append(row)
    return rows


def chunk(words: list[str]) -> list[list[int]]:
    """Group a line's words into cues, preferring to break where it does.

    A sentence end is the natural place, so those are taken first. What is
    still too long to fit two rows is split again at the latest word that fits.
    """
    pieces, run = [], []
    for i, word in enumerate(words):
        run.append(i)
        if word.endswith((".", "?", "!")) or i == len(words) - 1:
            pieces.append(run)
            run = []

    out = []
    for piece in pieces:
        while piece:
            take = piece
            while len(wrap([words[i] for i in take])) > LINES:
                take = take[:-1]
            out.append(take)
            piece = piece[len(take):]
    return out


def stamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def main() -> None:
    timing = json.loads((VO / "timing.json").read_text())
    cues: list[tuple[float, float, list[str]]] = []
    guessed = 0

    for segment in timing["segments"]:
        take = VO / f"{segment['id']}.wav"
        spoken = heard(take)
        script = [w for line in segment["lines"] for w in line["text"].split()]
        times = when(script, spoken, segment["seconds"])

        guessed += sum(1 for w in script if speak.normalise(w) not in
                       {h for h, _, _ in spoken})
        at = 0
        for line in segment["lines"]:
            words = line["text"].split()
            for group in chunk(words):
                start = times[at + group[0]][0] + segment["start"] - 0.08
                end = times[at + group[-1]][1] + segment["start"] + 0.12
                cues.append((max(0.0, start), end,
                             wrap([words[i] for i in group])))
            at += len(words)

    # A cue leaves when the words do, unless there is quiet afterwards it can
    # borrow. Reading takes about seventeen characters a second, and several
    # cues are short sentences the voice says quickly and lands on: without
    # this they flash. Nothing is borrowed from the next cue.
    for i, (start, end, rows) in enumerate(cues):
        text = " ".join(rows)
        wants = start + max(BRIEFEST, len(text) / 17)
        ceiling = cues[i + 1][0] - 0.06 if i + 1 < len(cues) else end + 1.0
        cues[i] = (start, min(max(end, wants), max(ceiling, start + BRIEFEST)),
                   rows)

    # And no cue may still be up when the next one arrives.
    for i in range(len(cues) - 1):
        if cues[i][1] > cues[i + 1][0]:
            cues[i] = (cues[i][0], max(cues[i][0] + 0.4, cues[i + 1][0] - 0.04),
                       cues[i][2])

    srt = []
    for n, (start, end, rows) in enumerate(cues, start=1):
        srt.append(f"{n}\n{stamp(start)} --> {stamp(end)}\n" + "\n".join(rows))
    OUT.mkdir(exist_ok=True)
    (OUT / "palinode-demo.srt").write_text("\n\n".join(srt) + "\n")

    print(f"  out/palinode-demo.srt   {len(cues)} cues from {len(cues)} groups, "
          f"{guessed} words the recogniser did not confirm")
    longest = max(len(r) for _, _, rows in cues for r in rows)
    print(f"  widest line {longest} characters, at most {LINES} rows\n")

    print("  chapters for the description:\n")
    starts = {s["id"]: s["start"] for s in timing["segments"]}
    for sid, label in CHAPTERS:
        print(f"    {clock(starts[sid])}  {label}")


if __name__ == "__main__":
    main()
