# Video

Title cards for the demo video, built with [Remotion](https://github.com/remotion-dev/remotion).

## What is animated and what is not

The rules ask for a **live, unedited demonstration of the agent performing its
task**, plus visible proof of the Cloud Run deployment. So the demo itself is a
screen recording of the real dashboard driving the real control plane. Nothing
in the middle of this video is a reconstruction.

Remotion handles the parts that are not the demo: the opening, the chapter
markers, and the closing numbers. Those are titles, and titles have always been
allowed to be titles.

```
0:00  Intro          rendered      the palinode hook, 8s
0:08  Chapter 01     rendered      2s
0:10  Screen capture live          the fleet does its job
0:55  Chapter 02     rendered      2s
0:57  Screen capture live          the reveal and the undo
1:50  Chapter 03     rendered      2s
1:52  Screen capture live          what could not be undone
2:25  Chapter 04     rendered      2s
2:27  Screen capture live          architecture and Cloud Run console
3:30  Outro          rendered      7s
```

Four minutes is the hard cap. The screen capture is roughly three of them.

## Build the whole cut

```bash
npm install
npx playwright install chromium

# control plane in another shell
cd .. && uvicorn palinode.api.main:app --app-dir src --port 8099

node capture.mjs        # records the real dashboard, three segments
./assemble.sh           # renders the cards and stitches everything
open out/palinode-demo.mp4
```

`capture.mjs` drives a real browser against the real API. The reversal on
screen is the one Regret actually planned and ran. Nothing in the captured
segments is animated.

## Render cards only

```bash
npm run studio          # preview and scrub
npm run render:all      # intro and outro to out/
```

One chapter card per chapter, with props:

```bash
npx remotion render Chapter out/ch01.mp4 --props='{
  "index": "01",
  "title": "The fleet does its job",
  "subtitle": "Three ADK agents, five real actions, one poisoned invoice.",
  "accent": "#38BDF8"
}'
```

Suggested chapters:

| Index | Title | Accent |
|-------|-------|--------|
| 01 | The fleet does its job | `#38BDF8` sky |
| 02 | The invoice was poisoned | `#F87171` red |
| 03 | What could not be undone | `#FBBF24` amber |
| 04 | How it is built | `#C084FC` violet |

## Capturing the demo

Run the control plane and record the browser at 1920x1080.

```bash
cd ..
uvicorn palinode.api.main:app --app-dir src --port 8080
open http://localhost:8080
```

Three clicks, in this order, and do not cut between them:

1. **Run the fleet.** Five actions land. Say the tier out loud as each appears,
   and point out that `wire_transfer` is already red before anything has gone
   wrong, because the tier is decided before the action runs, not after.
2. **Preview undo.** The dry run shows the plan and the order. Worth four
   seconds, it proves the reversal is planned rather than improvised.
3. **Undo.** Four rows come back. One does not. Let the disclosure panel finish
   rendering before cutting away.

Then show the Cloud Run console, the service URL, and the logs. This is a
scored requirement, not a nice to have.

## Recording notes

- Record at 1920x1080, 30fps, browser in fullscreen with no bookmarks bar.
- Dark mode terminal for the `demo.py` shot if you use one.
- English narration or English subtitles, both are accepted.
- Upload unlisted to YouTube, not private. Private cannot be opened by judges.

## Still missing before submission

- **The Cloud Run console shot.** Scored requirement, and there is nothing to
  film until the service is deployed.
- **Narration.** The current cut runs 58 seconds with no audio. Four minutes is
  the cap, so there is room.
