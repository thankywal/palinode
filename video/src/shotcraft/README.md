# Vendored from video-shotcraft

`PageCam.tsx`, `Motion.tsx`, `shake.ts` and `physics.ts` are taken unmodified from

    https://github.com/Vincentwei1021/video-shotcraft

which is Apache License 2.0. The licence text is in `LICENSE` beside them, and
each file carries a header saying where it came from.

## Why these three

The console captures are the evidence half of this film: Stripe, GitHub,
Slack, Cloud Run, Cloud Scheduler, Cloud Trace and Firestore, all of them
somebody else's dashboard. They were held perfectly still at first, then given
a linear pan in ffmpeg, and both readings were the same: a slide. A page that
is translated across a frame looks like a screenshot. A page with a camera
over it looks like somewhere you are standing.

`PageCam` is a 2.5D camera over a full page texture, keyframed on centre,
zoom, three rotations and perspective. The part worth vendoring rather than
reimplementing is a paragraph of comment in the middle of it: scaling a 3D
composited layer makes Chromium rasterise at layout size and then upscale on
the GPU, so every glyph goes soft exactly when you magnify it to be read.
Applying the magnification as the CSS `zoom` property instead rasterises the
layout at the enlarged size. Screen text under a moving camera is the whole
problem this film has, and that is the answer to it.

`shake.handheld` is layered sines at frequencies that do not divide into each
other, which reads as a hand rather than a machine. The same idea is applied
to the dashboard framings in `plan.py`, in ffmpeg crop expressions, because
that footage is cut outside Remotion.

## What is ours

`ConsoleShot.tsx` and `consoleShots.ts` are ours. The camera path, the scrim,
the framing of each capture and every caption are written here. Nothing from
the upstream template, its brand assets or its example content is used.

## One local change

Upstream calls the velocity helpers `motion.ts` and the easing vocabulary
`Motion.tsx`. Two files whose names differ only in case are fine on Linux and
ambiguous on macOS, where `import './shotcraft/Motion'` quietly resolved to the
wrong one and every easing came back undefined. The velocity helpers are
`physics.ts` here. Nothing inside either file changed.
