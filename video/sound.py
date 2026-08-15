"""Where every sound effect lands, written against the narration.

    python sound.py            # print the cue sheet with absolute times

A cue is anchored to a line of narration rather than to a wall clock time,
because the lines move whenever the script changes and the sounds have to move
with them. `("04-sentinel", 2, -0.35)` means a third of a second before the
third line of the sentinel segment begins.

The effects come from video-shotcraft's library, which collects them from
Mixkit under the Sound Effects Free License. Three of the ones I first picked
had no traceable source in the upstream attribution table, and this film is
going on YouTube, so they were dropped for ones that do. Every file under
audio/sfx traces to a Mixkit URL.

The rule for placing them: a sound goes where something happens, not where a
sentence begins. A whoosh on every cut is a trailer. A hit on the frame where
Model Armor returns MATCH_FOUND is an edit.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent
SFX = HERE / "audio" / "sfx"

# (segment, line index, offset seconds, file, gain dB, optional length)
#
# The length is there because several of these run four or five seconds. A
# whoosh chosen for the half second where something happens is still ringing
# under the next sentence, which is how 1:47 ended up with a low rumble sitting
# on nothing. Where a cue carries a length it is trimmed to it and faded.
CUES: list[tuple] = [
    # --- open ------------------------------------------------------------
    ("01-hook", 1, -0.20, "air-zoom-vacuum", -14),
    # The wordmark arrives on the third line.
    ("01-hook", 2, -0.10, "bass-hit-futuristic", -9),

    # --- the two documents ------------------------------------------------
    ("02-two-invoices", 1, 0.30, "data-scan", -15, 3.6),   # Gemini starts reading A
    ("02-two-invoices", 1, 2.20, "ui-select-click", -19),
    ("02-two-invoices", 1, 3.40, "ui-select-click", -19),
    ("02-two-invoices", 1, 4.60, "ui-select-click", -19),
    # Model Armor catches it. This is the one hit in the film that should
    # make somebody sit up.
    ("02-two-invoices", 2, 0.65, "hit-fast-exciting", -8),
    ("02-two-invoices", 4, 0.30, "data-scan", -15, 3.6),   # and now B
    ("02-two-invoices", 4, 2.40, "ui-select-click", -19),
    ("02-two-invoices", 4, 3.60, "ui-select-click", -19),
    ("02-two-invoices", 4, 4.80, "ui-select-click", -19),
    # And it passes. Soft, wrong, no triumph in it.
    ("02-two-invoices", 5, 0.55, "ui-message-pop", -17),

    # --- the fleet acts ---------------------------------------------------
    ("03-fleet-acts", 0, 0.10, "whoosh-fast", -15),
    ("03-fleet-acts", 0, 3.10, "ui-confirm-tone", -21),
    ("03-fleet-acts", 0, 4.60, "ui-confirm-tone", -21),
    ("03-fleet-acts", 0, 6.10, "ui-confirm-tone", -21),
    ("03-fleet-acts", 0, 7.60, "ui-confirm-tone", -21),
    # The wire. Lower and heavier than the four before it.
    ("03-fleet-acts", 0, 9.10, "bass-hit-short", -12),

    # --- sentinel decides -------------------------------------------------
    ("04-sentinel", 1, -0.30, "power-up-static", -14, 2.0),
    ("04-sentinel", 2, 3.10, "power-up-electronic", -12, 2.2),
    # There was a deep whoosh here too. It is four seconds long, so it was
    # still rumbling under 1:47 with nothing on screen to justify it. The
    # power up already marks the moment Sentinel fires; two low sounds
    # overlapping only made the room feel muddy.

    # --- what came back ---------------------------------------------------
    ("05-what-came-back", 0, 1.90, "ui-success-soft", -17),
    ("05-what-came-back", 1, 1.60, "ui-success-soft", -18),
    ("05-what-came-back", 1, 4.90, "ui-success-soft", -18),
    ("05-what-came-back", 2, 2.40, "ui-success-soft", -17),

    # --- what did not -----------------------------------------------------
    # No confirmation tone anywhere in this segment. Nothing was confirmed.
    ("06-what-did-not", 0, 0.10, "impact-deep-whoosh", -13, 3.0),
    ("06-what-did-not", 1, 5.60, "bass-hit-short", -10),

    # --- weeks later ------------------------------------------------------
    ("07-weeks-later", 1, -0.25, "swoosh-quick", -16),
    ("07-weeks-later", 2, -0.25, "swoosh-quick", -16),
    ("07-weeks-later", 2, 2.60, "data-compute", -15, 2.4),
    ("07-weeks-later", 3, -0.25, "swoosh-quick", -16),
    ("07-weeks-later", 3, 3.20, "bass-hit-futuristic", -11),

    # --- the proof --------------------------------------------------------
    # A shutter on each console shot. These are photographs of somebody's
    # dashboard and the sound says so.
    ("08-it-was-real", 0, -0.15, "camera-shutter-hard", -18),
    ("08-it-was-real", 1, -0.15, "camera-shutter-hard", -18),
    ("08-it-was-real", 2, -0.15, "camera-shutter-hard", -18),
    ("09-google-cloud", 0, -0.15, "click-camera", -19),
    ("09-google-cloud", 1, -0.15, "click-camera", -19),
    ("09-google-cloud", 2, -0.15, "click-camera", -19),
    ("09-google-cloud", 3, -0.15, "click-camera", -19),

    # --- close ------------------------------------------------------------
    ("10-close", 0, -0.30, "transition-snap", -15),
    ("10-close", 1, -0.20, "air-zoom-vacuum", -15),
    # The wordmark, one more time, and then the last line lands on nothing but
    # the music.
    ("10-close", 1, 0.55, "bass-hit-futuristic", -9),
    ("10-close", 3, -0.20, "impact-deep-whoosh", -12),
]


def cue_sheet() -> list[dict]:
    """Absolute times for every cue, from the measured narration."""
    timing = json.loads((HERE / "audio" / "vo" / "timing.json").read_text())
    seg = {s["id"]: s for s in timing["segments"]}

    sheet = []
    for cue in CUES:
        segment, line, offset, name, gain = cue[:5]
        length = cue[5] if len(cue) > 5 else None
        if segment not in seg:
            raise SystemExit(f"cue points at unknown segment {segment}")
        lines = seg[segment]["lines"]
        if line >= len(lines):
            raise SystemExit(f"{segment} has {len(lines)} lines, cue wants {line}")
        path = SFX / f"{name}.mp3"
        if not path.is_file():
            raise SystemExit(f"no such effect: {path}")
        sheet.append({
            "at": round(max(0.0, lines[line]["start"] + offset), 3),
            "file": str(path.relative_to(HERE)),
            "gain": gain,
            "length": length,
            "why": f"{segment} line {line + 1}",
        })

    sheet.sort(key=lambda c: c["at"])
    return sheet


if __name__ == "__main__":
    for cue in cue_sheet():
        cut = f"cut to {cue['length']}s" if cue["length"] else ""
        print(f"  {cue['at']:>7.2f}s  {cue['gain']:>4} dB  "
              f"{pathlib.Path(cue['file']).stem:<22} {cue['why']:<26} {cut}")
    print(f"\n  {len(CUES)} cues")
