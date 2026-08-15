/**
 * Records the dashboard driving the real control plane.
 *
 * This is a capture, not a reconstruction. A real browser clicks the real
 * buttons, the requests hit the real API, and the reversal that shows up on
 * screen really did refund a Stripe charge, revert a GitHub commit and delete
 * a Slack message.
 *
 *   PALINODE_URL=https://palinode-...run.app node capture.mjs
 *
 * The pacing is set by the narration rather than by taste. Segments 03 to 06
 * run to about seventy two seconds of voiceover, so the dashboard is taken in
 * one continuous shot of that length instead of four cuts. An unbroken take is
 * harder to fake and easier to believe.
 */

import {chromium} from 'playwright';
import {
  mkdirSync,
  readdirSync,
  renameSync,
  statSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE =
  process.env.PALINODE_URL ?? 'https://palinode-173485225974.us-central1.run.app';
const OUT = join(HERE, 'out/capture');

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** How long each narration segment runs, so the picture can be cut to it. */
function narration() {
  try {
    return JSON.parse(readFileSync(join(HERE, 'audio/vo/timing.json'), 'utf8'));
  } catch {
    console.warn('  no timing.json, falling back to estimates');
    return {segments: [], gap_segment: 0.55};
  }
}

const VO = narration();
const seg = Object.fromEntries((VO.segments ?? []).map((s) => [s.id, s]));
const secs = (id, fallback) => ((seg[id] ?? {}).seconds ?? fallback) * 1000;

async function segment(name, steps) {
  mkdirSync(OUT, {recursive: true});

  const browser = await chromium.launch();
  // Recorded at twice the delivery size. The board goes still once the
  // reversal lands, and the back half of the narration is still talking about
  // parts of it, so the edit frames in on whichever panel the voice is on.
  // Framing in on a 1080p capture is how the console slides ended up blurred.
  // At 4K a half frame crop is delivered at its own size and stays sharp, and
  // the take is still one continuous unbroken shot.
  //
  // deviceScaleFactor does not reach the recorder. It writes whatever the
  // viewport is into the top left of the frame and leaves the rest grey. So
  // the viewport is the full 4K and the page is zoomed to lay out at 1920
  // wide, which renders every glyph at twice the resolution for real.
  const context = await browser.newContext({
    viewport: {width: 3840, height: 2160},
    recordVideo: {dir: OUT, size: {width: 3840, height: 2160}},
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // When things happened inside the take, in take time. The film needs to know
  // where the fleet run starts, because everything before it is the screening
  // and the screening has its own card. Guessing that offset put the cut in
  // the middle of an empty board.
  const t0 = Date.now();
  const marks = {};
  const mark = (label) => {
    marks[label] = Number(((Date.now() - t0) / 1000).toFixed(2));
  };

  // Not networkidle. The dashboard polls every 350ms, so the network is never
  // idle and the wait burns the full timeout into the front of every clip.
  // pace=2 doubles the reveal stagger, and only the reveal. The narration
  // names the five actions one at a time and reading is slower than a fetch,
  // so at the default speed the voice is still on the database write while the
  // wire has already landed.
  await page.goto(`${BASE}/?pace=2`, {waitUntil: 'domcontentloaded'});
  await page.waitForLoadState('load');
  await page.addStyleTag({content: 'html { zoom: 2 }'});
  await wait(900);

  await steps(page, mark);

  await context.close();
  await browser.close();

  const videos = readdirSync(OUT)
    .filter((f) => f.endsWith('.webm') && !f.startsWith('seg-'))
    .map((f) => ({f, t: statSync(join(OUT, f)).mtimeMs}))
    .sort((a, b) => b.t - a.t);

  if (videos.length) {
    renameSync(join(OUT, videos[0].f), join(OUT, `seg-${name}.webm`));
    console.log(`  captured seg-${name}.webm`);
  }
  writeFileSync(join(OUT, 'marks.json'), JSON.stringify(marks, null, 2));
  console.log('  marks', JSON.stringify(marks));
}

async function main() {
  console.log('recording against', BASE);
  await fetch(`${BASE}/demo/reset`, {method: 'POST'});

  // Segments 03 to 06, in one take. The fleet acts, Sentinel decides on its
  // own, the reversal runs, and the disclosure lands. Cutting between those
  // would invite the question of what happened in the cut.
  // Four segments and the three breaths between them, plus a little over, so
  // the tail of the take is never the thing that runs out.
  const gaps = 3 * (VO.gap_segment ?? 0.55) * 1000;
  const budget =
    secs('03-fleet-acts', 17.5) +
    secs('04-sentinel', 23) +
    secs('05-what-came-back', 19) +
    secs('06-what-did-not', 12) +
    gaps +
    4000;

  await segment('dashboard', async (page, mark) => {
    // Screen the invoices first so the Model Armor panel is already on screen,
    // with both documents and both verdicts, when the fleet runs. The
    // voiceover has covered all of that by now.
    await page.click('#screen');
    await page.waitForSelector('.inv', {timeout: 60000});
    await page.waitForSelector('.scan img', {timeout: 60000});
    await wait(2500);

    const started = Date.now();
    mark('fleet');

    // The board is empty between this click and the first row landing, and
    // the narration is already naming the actions, so the wait for the first
    // row is the wait, not a fixed pause on nothing.
    await page.click('#seed');
    await page.waitForSelector('.node', {timeout: 40000});

    // The five rows reveal on a stagger, then hold so the tiers can be read.
    await wait(9000);

    await page.waitForSelector('#sentinel-panel:not([style*="display: none"])', {
      timeout: 60000,
    });
    await wait(3000);

    await page.waitForFunction(
      () =>
        document.querySelectorAll('.node.reversed, .node.compensated').length >= 4,
      {timeout: 120000}
    );

    await page.waitForSelector('#disc-panel:not([style*="display: none"])', {
      timeout: 60000,
    });

    // Hold on the finished board for whatever the narration still has to say.
    const spent = Date.now() - started;
    const remaining = Math.max(4000, budget - spent);
    console.log(`  holding ${(remaining / 1000).toFixed(1)}s to reach the voiceover`);
    await wait(remaining);
  });

  console.log('done');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
