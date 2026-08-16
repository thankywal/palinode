/**
 * One take, no cuts, no sound, nothing added afterwards.
 *
 *   node rawdemo.mjs
 *   PALINODE_URL=http://localhost:8080 node rawdemo.mjs
 *
 * Writes out/rawdemo/palinode-raw-demo.webm, which is the file playwright
 * wrote and not a file anything else has touched.
 *
 * ## Why this exists next to a four minute film
 *
 * The judging asks for a "live, unedited demo". The film is not that and does
 * not pretend to be: it has title cards, a camera, a score and forty two sound
 * effects, and it cuts fifteen times. Everything in it is real footage of the
 * real service, but somebody who reads "unedited" strictly is entitled to say
 * that a film is a film.
 *
 * So this is the other artifact. A browser opens the deployed service, clicks
 * what a person would click, and waits exactly as long as the service takes.
 * Where it looks slow, that is how long it took. There is no post production
 * step in this file, and deliberately none afterwards either: the webm goes up
 * as it comes out, because the moment it is re-encoded somebody has to take my
 * word for what the re-encode did.
 *
 * ## What it can and cannot prove
 *
 * The public deployment runs with PALINODE_PUBLIC_DEMO=1, so the five systems
 * of record are simulated there and nothing this recording does reaches Stripe
 * or GitHub or Slack. That is a deliberate property of a URL anybody can post
 * to, and the take opens on /status so the viewer is told rather than left to
 * assume.
 *
 * Everything else in shot is real and is running on Google Cloud: Cloud Run
 * serves it, Gemini 3.5 Flash classifies each action's reversibility, Model
 * Armor screens the invoice, and the ledger being verified at the end is a
 * hash chain in Firestore. The film covers the three live connectors.
 */

import {chromium} from 'playwright';
import {mkdirSync, readdirSync, renameSync} from 'node:fs';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE =
  process.env.PALINODE_URL ?? 'https://palinode-173485225974.us-central1.run.app';
const OUT = join(HERE, 'out/rawdemo');

// 1080p. A raw demo is watched for what happens in it, not for its sharpness,
// and a smaller file is a file that finishes uploading.
const SIZE = {width: 1920, height: 1080};

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** Say what is about to happen, so the log reads as a transcript of the take. */
function step(n, what) {
  console.log(`  ${String(n).padStart(2)}  ${what}`);
}

async function main() {
  mkdirSync(OUT, {recursive: true});
  console.log(`recording one take against ${BASE}\n`);

  // Reset before the recorder starts, so the take opens on a clean board
  // rather than on housekeeping.
  await fetch(`${BASE}/demo/reset`, {method: 'POST'});

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: SIZE,
    deviceScaleFactor: 1,
    recordVideo: {dir: OUT, size: SIZE},
  });
  const page = await context.newPage();
  const began = Date.now();

  step(1, 'open /status, so the viewer knows what is live and what is not');
  await page.goto(`${BASE}/status`, {waitUntil: 'load'});
  await wait(6000);

  step(2, 'open the dashboard');
  await page.goto(`${BASE}/`, {waitUntil: 'load'});
  await wait(4000);

  step(3, 'read both invoices with Gemini and screen them with Model Armor');
  await page.click('#screen');
  await page.waitForSelector('.inv', {timeout: 120000});
  await page.waitForSelector('.scan img', {timeout: 120000});
  // Long enough to read both verdicts, since the point of the panel is that
  // the second invoice passes.
  await wait(11000);

  step(4, 'run the fleet against the poisoned invoice');
  await page.click('#seed');
  await page.waitForSelector('.node', {timeout: 120000});
  await wait(9000);

  step(5, 'wait for Sentinel to decide on its own, with nobody pressing a button');
  await page.waitForSelector('#sentinel-panel:not([style*="display: none"])', {
    timeout: 180000,
  });
  await wait(6000);

  step(6, 'wait for the reversal to land, action by action');
  await page.waitForFunction(
    () => document.querySelectorAll('.node.reversed, .node.compensated').length >= 4,
    {timeout: 180000}
  );
  await wait(4000);

  step(7, 'the wire that does not come back, and the disclosure');
  await page.waitForSelector('#disc-panel:not([style*="display: none"])', {
    timeout: 120000,
  });
  await wait(9000);

  // The chain is the claim that is easiest to make and hardest to check, so
  // check it on camera rather than assert it in a caption.
  step(8, 'verify the hash chain on the run that just happened');
  // The dashboard prints the id it is watching, so take it from the screen
  // the viewer is looking at rather than from anywhere they cannot see.
  const run = await page.evaluate(
    () => document.getElementById('runid')?.textContent?.trim() || null
  );
  if (!run) throw new Error('the dashboard is not showing a run id');
  console.log(`      run ${run}`);
  await page.goto(`${BASE}/runs/${run}/verify`, {waitUntil: 'load'});
  await wait(9000);

  step(9, 'close on /status again, unchanged, nothing outside was touched');
  await page.goto(`${BASE}/status`, {waitUntil: 'load'});
  await wait(5000);

  await context.close();
  await browser.close();

  const made = readdirSync(OUT).filter((f) => f.endsWith('.webm'));
  const raw = made.sort().pop();
  const final = join(OUT, 'palinode-raw-demo.webm');
  renameSync(join(OUT, raw), final);

  const took = (Date.now() - began) / 1000;
  console.log(`\n  one take, ${took.toFixed(0)}s, no cuts`);
  console.log(`  ${final}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
