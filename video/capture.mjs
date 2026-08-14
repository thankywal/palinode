/**
 * Records the dashboard driving the real control plane.
 *
 * This is a capture, not a reconstruction. A real browser clicks the real
 * buttons, the requests hit the real API, and the reversal that shows up on
 * screen is the one Sentinel actually decided on and Regret actually ran.
 * Nothing in the captured segments is animated.
 *
 *   PALINODE_URL=https://palinode-...run.app node capture.mjs
 *
 * Defaults to the deployed service so the address bar in the footage is itself
 * the proof of deployment. Point it at localhost to iterate faster.
 */

import {chromium} from 'playwright';
import {mkdirSync, readdirSync, renameSync, statSync} from 'node:fs';
import {join} from 'node:path';

const BASE =
  process.env.PALINODE_URL ?? 'https://palinode-173485225974.us-central1.run.app';
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

  await fetch(`${BASE}/demo/reset`, {method: 'POST'});

  // 01. Model Armor. One invoice is a prompt injection and gets caught at HIGH
  //     confidence. The other has the bank details changed and no injection in
  //     it at all, so there is nothing for a prompt filter to match. Both put
  //     the money in the same account.
  await segment('01-armor', async (page) => {
    await wait(1400);
    await page.click('#screen');
    await page.waitForSelector('.inv', {timeout: 40000});
    await wait(6000);
  });

  // 02. The fleet acts on the invoice that passed, and Sentinel reverses it
  //     without being asked. One continuous shot, because the point is that
  //     nobody intervened between the two halves.
  await segment('02-sentinel', async (page) => {
    await page.click('#screen');
    await page.waitForSelector('.inv', {timeout: 40000});
    await wait(700);

    await page.click('#seed');
    await page.waitForSelector('.node', {timeout: 40000});
    await page.waitForSelector('#sentinel-panel:not([style*="display: none"])', {
      timeout: 60000,
    });
    await wait(2500);
    await page.waitForFunction(
      () =>
        document.querySelectorAll('.node.reversed, .node.compensated').length >= 4,
      {timeout: 120000}
    );
    await wait(5000);
  });

  // 03. What could not be undone, and what the system says about it.
  await segment('03-disclosure', async (page) => {
    await page.waitForSelector('.node.unrecoverable', {timeout: 30000});
    await wait(7000);
  });

  console.log('done');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
