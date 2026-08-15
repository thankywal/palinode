"""Turn the measured narration into the cut.

    python plan.py

Reads audio/vo/timing.json, which speak.py wrote from the actual length of
every synthesised line, and writes two things:

    src/timing.json    frame numbers the Remotion cards animate to
    out/shots.tsv      the cut list assemble.sh runs

Nothing in either file is chosen. Every number is the difference between two
measured moments, so a line that turns out longer than expected moves the
picture rather than desynchronising it. This exists because the first cut
sliced a segment into equal pieces and the voice reached Cloud Trace while the
picture was still on the logs.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent
FPS = 30

# Where the dashboard take actually starts. The recorder runs before the page
# does, so the first half second of it is the white of about:blank.
TAKE_IN = 0.70


def frames(seconds: float) -> int:
    return int(round(seconds * FPS))


def main() -> None:
    timing = json.loads((HERE / "audio" / "vo" / "timing.json").read_text())
    seg = {s["id"]: s for s in timing["segments"]}
    total = timing["total"]

    def line_start(seg_id: str, n: int) -> float:
        return seg[seg_id]["lines"][n]["start"]

    # Every moment the picture changes, in order, with what it changes to.
    # The last entry is the end of the film rather than a shot.
    cuts = [
        (0.0, "00-intro", "remotion", "Intro"),
        (seg["02-two-invoices"]["start"], "01-invoices", "remotion", "Invoices"),
        (seg["03-fleet-acts"]["start"], "02a-dash-wide", "take", "scale=1920:1080"),
        (seg["05-what-came-back"]["start"], "02b-dash-rows", "take",
         "crop=1920:1080:940:170"),
        (seg["06-what-did-not"]["start"], "02c-dash-disclosure", "take",
         "crop=1920:1080:1920:1080"),
        (line_start("07-it-was-real", 0), "03-stripe", "still", "s01"),
        (line_start("07-it-was-real", 1), "04-github", "still", "s02"),
        (line_start("07-it-was-real", 2), "05-slack", "still", "s03"),
        (line_start("08-google-cloud", 0), "06-cloudrun", "still", "s04"),
        (line_start("08-google-cloud", 1), "07-logs", "still", "s05"),
        (line_start("08-google-cloud", 2), "08-trace", "still", "s06"),
        (line_start("08-google-cloud", 3), "09-firestore", "still", "s07"),
        (seg["09-close"]["start"], "10-outro", "remotion", "Outro"),
        (total, "", "", ""),
    ]

    dash_zero = seg["03-fleet-acts"]["start"]

    rows = []
    for (start, name, kind, spec), (nxt, *_) in zip(cuts, cuts[1:]):
        seconds = round(nxt - start, 3)
        # The take is one continuous recording, so a shot's position inside it
        # is wherever the film has got to, never a fresh seek to taste.
        offset = round(TAKE_IN + start - dash_zero, 3) if kind == "take" else 0.0
        rows.append(f"{name}\t{kind}\t{spec}\t{offset}\t{seconds}")

    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out" / "shots.tsv").write_text("\n".join(rows) + "\n")

    # What the cards animate to. Frames, relative to each card's own start.
    hook, inv, close = seg["01-hook"], seg["02-two-invoices"], seg["09-close"]

    def rel(segment: dict, n: int) -> int:
        return frames(segment["lines"][n]["start"] - segment["start"])

    cards = {
        "fps": FPS,
        "intro": {
            "durationInFrames": frames(inv["start"]),
            # Line two of the quote, and the moment the wordmark takes over,
            # which is line three saying this is a palinode for AI agents.
            "second": rel(hook, 1),
            "handoff": rel(hook, 2),
        },
        # Six lines now, and each one has something on screen. Invoice A and
        # its two verdicts, then invoice B and its two, then the line that
        # says why the second one matters.
        "invoices": {
            "durationInFrames": frames(seg["03-fleet-acts"]["start"] - inv["start"]),
            "verdictA": rel(inv, 2),
            "readB": rel(inv, 4),
            "verdictB": rel(inv, 5),
            "punchline": rel(inv, 5) + 60,
        },
        "outro": {
            "durationInFrames": frames(total - close["start"]),
            "second": rel(close, 1),
        },
    }
    (HERE / "src" / "timing.json").write_text(json.dumps(cards, indent=2))

    print(f"  film {total:.2f}s, {len(rows)} shots")
    for row in rows:
        name, kind, spec, offset, seconds = row.split("\t")
        print(f"    {name:<20} {kind:<9} {float(seconds):>6.2f}s  {spec}")


if __name__ == "__main__":
    main()
