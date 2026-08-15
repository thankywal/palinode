/**
 * Composes the console captures into slides on the Palinode backdrop, so the
 * evidence cuts against the rest of the film instead of dropping to a bare
 * browser window on a white page.
 *
 *   node console/build.mjs
 *
 * The captures are shown at their own size and never stretched. An earlier cut
 * blew a 1568 pixel wide screenshot up into a 1920 frame, which turned every
 * line of console text into a smear. Console text is the entire point of these
 * shots, so the frame gives way to the screenshot rather than the other way
 * round.
 */

import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

/** Native size of every capture. Displayed one to one, never scaled. */
const SHOT_W = 1568;
const SHOT_H = 764;

const SKY = '#38BDF8';
const VIOLET = '#C084FC';
const AMBER = '#FBBF24';

/**
 * Segment 07 is the three third party systems, segment 08 is Google Cloud.
 * The order matches the order the narration names them in, because the voice
 * says "here is the Stripe dashboard" and the wrong picture underneath that is
 * worse than no picture at all.
 */
const SLIDES = [
  {
    file: 'p1-stripe.jpg',
    group: 'IT WAS REAL',
    index: '01',
    title: 'Stripe',
    caption: 'Nineteen live charges across the demo runs. Seventeen refunded by Palinode, with nobody asked.',
    accent: SKY,
  },
  {
    file: 'p2-github.jpg',
    group: 'IT WAS REAL',
    index: '02',
    title: 'GitHub',
    caption: 'Every approve commit followed by a revert, on the real default branch.',
    accent: SKY,
  },
  {
    file: 'p7-slack.jpg',
    group: 'IT WAS REAL',
    index: '03',
    title: 'Slack',
    caption: 'The approval deleted, and the correction standing where it was.',
    accent: SKY,
  },
  {
    file: 'p3-cloudrun.jpg',
    group: 'GOOGLE CLOUD',
    index: '04',
    title: 'Cloud Run',
    caption: 'Request based billing, minimum zero instances, capped at three.',
    accent: VIOLET,
  },
  {
    file: 'p6-logs.jpg',
    group: 'GOOGLE CLOUD',
    index: '05',
    title: 'The logs',
    caption:
      'Sentinel scoring the run at 1.00 on its own, then the instance shutting down.',
    accent: VIOLET,
  },
  {
    file: 'p5-trace.jpg',
    group: 'GOOGLE CLOUD',
    index: '06',
    title: 'Cloud Trace',
    caption:
      'palinode.sentinel.assess, warden.evaluate, regret.compensate. Our spans, not just what ADK emits.',
    accent: VIOLET,
  },
  {
    file: 'p4-firestore.jpg',
    group: 'GOOGLE CLOUD',
    index: '07',
    title: 'Firestore',
    caption:
      'A SPIFFE actor, the causal parent, the contract written before the act, and the hash that commits to it.',
    accent: AMBER,
  },
];

const page = (slide, dataUri) => `<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:1920px; height:1080px; }
  body {
    background:#0B1020;
    font-family:"Helvetica Neue", Helvetica, Arial, sans-serif;
    color:#E4EBF6; position:relative; overflow:hidden;
  }
  .glow {
    position:absolute; inset:0;
    background:
      radial-gradient(900px circle at 6% -8%, rgba(56,189,248,.16), transparent 60%),
      radial-gradient(900px circle at 100% 108%, rgba(248,113,113,.12), transparent 60%);
  }
  .wrap {
    position:relative; height:100%;
    display:flex; flex-direction:column; align-items:center;
    padding:72px 0 0;
  }
  .head {
    width:${SHOT_W}px; display:flex; align-items:flex-end; gap:22px; margin-bottom:22px;
  }
  .bar { width:6px; height:62px; border-radius:4px; background:${slide.accent}; }
  .idx {
    font-family:ui-monospace,Menlo,monospace; font-size:15px; letter-spacing:3.5px;
    color:${slide.accent}; font-weight:700;
  }
  .title { font-size:44px; font-weight:800; letter-spacing:-1px; margin-top:5px; line-height:1; }
  .cap {
    font-size:21px; color:#8FA0BC; margin-left:auto; max-width:820px;
    text-align:right; line-height:1.4;
  }
  /* One to one. No width, no height, no object-fit, nothing that resamples. */
  .shot {
    width:${SHOT_W}px; height:${SHOT_H}px;
    border-radius:12px; overflow:hidden;
    border:1px solid rgba(255,255,255,.16);
    box-shadow:0 30px 90px rgba(0,0,0,.55);
  }
  .shot img { display:block; }
</style></head><body>
  <div class="glow"></div>
  <div class="wrap">
    <div class="head">
      <div class="bar"></div>
      <div>
        <div class="idx">${slide.group} &nbsp;${slide.index}</div>
        <div class="title">${slide.title}</div>
      </div>
      <div class="cap">${slide.caption}</div>
    </div>
    <div class="shot"><img src="${dataUri}" width="${SHOT_W}" height="${SHOT_H}"></div>
  </div>
</body></html>`;

mkdirSync(join(HERE, 'slides'), {recursive: true});

SLIDES.forEach((slide, i) => {
  const bytes = readFileSync(join(HERE, slide.file));
  const uri = `data:image/jpeg;base64,${bytes.toString('base64')}`;
  const name = `s${String(i + 1).padStart(2, '0')}.html`;
  writeFileSync(join(HERE, 'slides', name), page(slide, uri));
  console.log(`  wrote ${name}  ${slide.title}`);
});
