/**
 * Render docs/src/architecture.html to docs/architecture.png.
 *
 *     cd video && node diagram.mjs
 *
 * Lives here because this is where playwright is installed. There was no
 * script at all for a while, which meant the png and the html it came from
 * could drift apart with nothing to notice, and a diagram that disagrees with
 * its own source is worse than no diagram.
 *
 * fullPage, and at 2x, because the one place this is definitely read at full
 * size is a judge opening the attachment.
 */
import {chromium} from 'playwright';
import path from 'node:path';

const html = path.resolve('../docs/src/architecture.html');
const out = path.resolve('../docs/architecture.png');

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: {width: 1200, height: 800},
  deviceScaleFactor: 2,
});
await page.goto(`file://${html}`);
await page.screenshot({path: out, fullPage: true});
await browser.close();
console.log(`  ${out}`);
