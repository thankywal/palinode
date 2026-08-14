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
0:00  Intro           rendered   the palinode hook, 8s
0:08  Chapter 01      rendered   2s
0:10  Screen capture  live       Model Armor: one invoice caught, one not
0:20  Chapter 02      rendered   2s
0:22  Screen capture  live       the fleet acts, Sentinel reverses it unasked
0:40  Chapter 03      rendered   2s
0:42  Screen capture  live       what could not be undone
0:51  Outro           rendered   7s
```

Current cut runs 58 seconds. Four minutes is the hard cap, so there is room for
narration and for the Cloud Run console segment, which still has to be filmed.

The capture records against the deployed service by default, so the address bar
in the footage is itself part of the proof of deployment.

## Build the whole cut

```bash
npm install
npx playwright install chromium

node capture.mjs        # records the deployed dashboard, three segments

# or against a local control plane
# cd .. && uvicorn palinode.api.main:app --app-dir src --port 8099
# PALINODE_URL=http://localhost:8099 node capture.mjs
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

Chapters in the current cut, set in `assemble.sh`:

| Index | Title | Accent |
|-------|-------|--------|
| 01 | Model Armor catches one of these | `#38BDF8` sky |
| 02 | Nobody is watching | `#C084FC` violet |
| 03 | What could not be undone | `#FBBF24` amber |

## Capturing the demo

Run the control plane and record the browser at 1920x1080.

```bash
cd ..
uvicorn palinode.api.main:app --app-dir src --port 8080
open http://localhost:8080
```

Two clicks, in this order, and do not cut between them:

1. **Screen invoices.** One is a prompt injection and Model Armor blocks it at
   HIGH confidence. The other has the bank details changed, contains no
   injection at all, and passes. Say out loud that both send the money to the
   same account. This is the whole argument for the project.
2. **Run the fleet.** Five actions land on the invoice that passed. Point out
   that `wire_transfer` is already red before anything has gone wrong, because
   the tier is decided before the action runs. Then stop talking and let
   Sentinel fire on its own. Nobody presses undo. That is the point, and it is
   worth the silence.

Then show the Cloud Run console, the service URL, and the logs. This is a
scored requirement, not a nice to have.

## Recording notes

- Record at 1920x1080, 30fps, browser in fullscreen with no bookmarks bar.
- Dark mode terminal for the `demo.py` shot if you use one.
- English narration or English subtitles, both are accepted.
- Upload unlisted to YouTube, not private. Private cannot be opened by judges.

## Still missing before submission

- **The Cloud Run console shot.** Scored requirement. The service is deployed
  at https://palinode-173485225974.us-central1.run.app, so this is now just a
  matter of filming the console, the revision list and the logs.
- **Narration.** The current cut runs 58 seconds with no audio.
