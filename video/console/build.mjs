/**
 * Composes the Cloud Run console captures into slides on the Palinode
 * backdrop, so the deployment evidence cuts against the rest of the film
 * instead of dropping to a bare browser window on a white page.
 *
 *   node console/build.mjs
 *
 * The captures themselves are untouched. Only the frame around them is ours.
 */

import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

const SLIDES = [
  {
    file: '01-service.jpg',
    index: '01',
    title: 'Deployed and serving',
    caption: 'Cloud Run, us-central1. The URL in the demo is this service.',
    accent: '#38BDF8',
  },
  {
    file: '02-revisions.jpg',
    index: '02',
    title: 'Sixteen revisions',
    caption:
      'Request based billing, scales to zero, capped at three instances.',
    accent: '#38BDF8',
  },
  {
    file: '03-logs.jpg',
    index: '03',
    title: 'What the service said',
    caption:
      'Model Armor blocked the injection. Sentinel reversed the run without human approval, score 2.40.',
    accent: '#C084FC',
  },
  {
    file: '04-trace.jpg',
    index: '04',
    title: 'Our spans, in Cloud Trace',
    caption:
      'palinode.sentinel.assess, warden.evaluate, regret.compensate. OpenTelemetry, not just what ADK emits.',
    accent: '#C084FC',
  },
  {
    file: '05-firestore.jpg',
    index: '05',
    title: 'One action in the ledger',
    caption:
      'A SPIFFE actor, the causal parent, the contract with no reversal, and the hash that commits to it.',
    accent: '#FBBF24',
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
  .wrap { position:relative; padding:52px 70px; height:100%; display:flex; flex-direction:column; }
  .head { display:flex; align-items:flex-end; gap:26px; margin-bottom:26px; }
  .bar { width:7px; height:74px; border-radius:4px; background:${slide.accent}; }
  .idx {
    font-family:ui-monospace,Menlo,monospace; font-size:17px; letter-spacing:3.5px;
    color:${slide.accent}; font-weight:700;
  }
  .title { font-size:52px; font-weight:800; letter-spacing:-1.2px; margin-top:6px; line-height:1; }
  .cap { font-size:25px; color:#8FA0BC; margin-left:auto; max-width:760px; text-align:right; line-height:1.45; }
  .shot {
    flex:1; border-radius:14px; overflow:hidden;
    border:1px solid rgba(255,255,255,.16);
    box-shadow:0 30px 90px rgba(0,0,0,.55);
    background:#fff; display:flex; align-items:flex-start; justify-content:center;
  }
  .shot img { width:100%; height:100%; object-fit:cover; object-position:top center; display:block; }
</style></head><body>
  <div class="glow"></div>
  <div class="wrap">
    <div class="head">
      <div class="bar"></div>
      <div>
        <div class="idx">CLOUD RUN ${slide.index}</div>
        <div class="title">${slide.title}</div>
      </div>
      <div class="cap">${slide.caption}</div>
    </div>
    <div class="shot"><img src="${dataUri}"></div>
  </div>
</body></html>`;

mkdirSync(join(HERE, 'slides'), {recursive: true});

for (const slide of SLIDES) {
  const bytes = readFileSync(join(HERE, slide.file));
  const uri = `data:image/jpeg;base64,${bytes.toString('base64')}`;
  writeFileSync(join(HERE, 'slides', slide.file.replace('.jpg', '.html')), page(slide, uri));
  console.log('  wrote', slide.file.replace('.jpg', '.html'));
}
