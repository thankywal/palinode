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

def take_in() -> float:
    """Where the fleet run starts inside the dashboard take.

    The take opens on the screening, which has its own card in the film, so
    the dashboard section starts at the moment the fleet was told to run.
    capture.mjs writes down when that was rather than leaving it to be
    guessed, because guessing it put the cut in the middle of an empty board.
    """
    marks = HERE / "out" / "capture" / "marks.json"
    if marks.is_file():
        return float(json.loads(marks.read_text()).get("fleet", 0.70))
    # No marks means an older take, whose only lead in was the half second of
    # about:blank the recorder catches before the page paints.
    return 0.70


def frames(seconds: float) -> int:
    return int(round(seconds * FPS))


def main() -> None:
    TAKE_IN = take_in()
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
        # The take is 4K, so the wide shot is delivered untouched. The two
        # framings that follow are cut out of it at 2560x1440 rather than
        # 1920x1080 and brought up to delivery size, because a one and a half
        # times scale holds together and a two times scale does not. Both drift
        # a little across the shot: the board is still by then and a frame that
        # is perfectly still for twenty seconds reads as a screenshot.
        (seg["03-fleet-acts"]["start"], "02a-dash-wide", "take", "null"),
        # Layered sines at frequencies that do not divide into each other, the
        # same trick the vendored handheld noise uses. A purely linear drift
        # is a machine moving the frame; this is closer to a hand holding it.
        # Not crops of the take any more. The board is settled by here and a
        # crop of a still frame sliding around is a camera move over a
        # photograph, which is what it looked like. These are compositions
        # with a light that goes to the row being named.
        (seg["05-what-came-back"]["start"], "02b-review", "remotion", "Review"),
        (seg["06-what-did-not"]["start"], "02c-disclosure", "remotion", "Disclosure"),
        # The cold case, in four beats: the run, the score of zero, the
        # report that arrives later, and the scheduler acting on it.
        (seg["07-weeks-later"]["start"], "03-sweeper", "remotion", "Sweeper"),
        (line_start("07-weeks-later", 3), "04-scheduler", "console", "scheduler"),
        (line_start("08-it-was-real", 0), "05-stripe", "console", "stripe"),
        (line_start("08-it-was-real", 1), "06-github", "console", "github"),
        (line_start("08-it-was-real", 2), "07-slack", "console", "slack"),
        (line_start("09-google-cloud", 0), "08-cloudrun", "console", "cloudrun"),
        (line_start("09-google-cloud", 1), "09-logs", "console", "logs"),
        (line_start("09-google-cloud", 2), "10-trace", "console", "trace"),
        (line_start("09-google-cloud", 3), "11-firestore", "console", "firestore"),
        (seg["10-close"]["start"], "12-outro", "remotion", "Outro"),
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
    hook, inv, close = seg["01-hook"], seg["02-two-invoices"], seg["10-close"]
    sweep = seg["07-weeks-later"]

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
        "sweeper": {
            "durationInFrames": frames(
                seg["08-it-was-real"]["start"] - sweep["start"]
            ),
            "beats": [rel(sweep, n) for n in range(len(sweep["lines"]))],
        },
        # Every console shot is its own composition, rendered to the length
        # its line takes, because the camera move has to arrive when the
        # sentence does.
        "shots": {
            spec: frames(seconds)
            for name, kind, spec, offset, seconds in [
                (r.split("\t")[0], r.split("\t")[1], r.split("\t")[2],
                 r.split("\t")[3], float(r.split("\t")[4]))
                for r in rows
            ]
            if kind == "console"
        },
        "review": {
            "durationInFrames": frames(
                seg["06-what-did-not"]["start"] - seg["05-what-came-back"]["start"]
            ),
            "beats": [rel(seg["05-what-came-back"], n) for n in range(3)],
        },
        "disclosure": {
            "durationInFrames": frames(
                seg["07-weeks-later"]["start"] - seg["06-what-did-not"]["start"]
            ),
            "beats": [rel(seg["06-what-did-not"], n) for n in range(2)],
        },
        # Four beats now: what broke, the name, the number, and the ask.
        "outro": {
            "durationInFrames": frames(total - close["start"]),
            "beats": [rel(close, n) for n in range(len(close["lines"]))],
        },
    }
    (HERE / "src" / "timing.json").write_text(json.dumps(cards, indent=2))

    print(f"  film {total:.2f}s, {len(rows)} shots")
    for row in rows:
        name, kind, spec, offset, seconds = row.split("\t")
        print(f"    {name:<20} {kind:<9} {float(seconds):>6.2f}s  {spec}")


if __name__ == "__main__":
    main()
