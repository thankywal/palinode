/**
 * Records the dashboard driving the real control plane.
 *
 * This is a capture, not a reconstruction. A real browser clicks the real
 * buttons, the requests hit the real API, and the reversal that shows up on
 * screen is the one Regret actually planned and ran. Nothing here is animated.
 *
 *   node capture.mjs
 *
 * Expects the control plane on http://localhost:8099. Writes 1920x1080 webm
 * segments into out/capture, which assemble.sh converts and stitches.
 */

import {chromium} from 'playwright';
import {mkdirSync, readdirSync, renameSync, statSync} from 'node:fs';
import {join} from 'node:path';

const BASE = process.env.PALINODE_URL ?? 'http://localhost:8099';
const OUT = 'out/capture';

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** One recorded segment. Each becomes its own clip in the final cut. */
async function segment(name, steps) {
  mkdirSync(OUT, {recursive: true});

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: {width: 1920, height: 1080},
    recordVideo: {dir: OUT, size: {width: 1920, height: 1080}},
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // Not networkidle. The dashboard polls every 350ms, so the network is never
  // idle and the wait burns the full timeout into the front of every clip.
  await page.goto(BASE, {waitUntil: 'domcontentloaded'});
  await page.waitForLoadState('load');
  await wait(900);

  await steps(page);

  await context.close();
  await browser.close();

  // Playwright names videos by an internal id, so claim the newest one.
  const videos = readdirSync(OUT)
    .filter((f) => f.endsWith('.webm') && !f.startsWith('seg-'))
    .map((f) => ({f, t: statSync(join(OUT, f)).mtimeMs}))
    .sort((a, b) => b.t - a.t);

  if (videos.length) {
    renameSync(join(OUT, videos[0].f), join(OUT, `seg-${name}.webm`));
    console.log(`  captured seg-${name}.webm`);
  }
}

async function main() {
  console.log('recording against', BASE);

  // Start from an empty ledger so the first segment opens on an empty board.
  await fetch(`${BASE}/demo/reset`, {method: 'POST'});

  // 01. The fleet does its job. Five actions land, and wire_transfer is
  //     already red before anything has gone wrong, because the tier is
  //     decided before the action runs.
  await segment('01-fleet', async (page) => {
    await wait(1800);
    await page.click('#seed');
    await page.waitForSelector('.node', {timeout: 15000});
    await wait(5200);
  });

  // 02. The plan, then the undo. Preview first so it is visible that the
  //     reversal is planned rather than improvised.
  await segment('02-undo', async (page) => {
    await page.waitForSelector('.node');
    await wait(1200);
    await page.click('#preview');
    await page.waitForSelector('.step', {timeout: 10000});
    await wait(4500);
    await page.click('#undo');
    await page.waitForFunction(
      () => document.querySelectorAll('.node.reversed, .node.compensated').length >= 4,
      {timeout: 30000}
    );
    await wait(5500);
  });

  // 03. What could not be undone.
  await segment('03-disclosure', async (page) => {
    await page.waitForSelector('#disc-panel');
    await wait(1000);
    await page.evaluate(() => {
      const el = document.getElementById('disc-panel');
      if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'});
    });
    await wait(6000);
  });

  console.log('done');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
