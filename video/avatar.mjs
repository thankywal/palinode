/**
 * Draw the channel avatar, at the size YouTube actually shows it.
 *
 *     node avatar.mjs
 *
 * Writes ../docs/avatar/<name>.png at 800x800, plus a 32px copy of each, because
 * 32px is where the decision is really made. A channel picture appears beside a
 * comment and under a video at between twenty four and forty eight pixels, and
 * almost never larger. The dashboard screenshot that was in the field is
 * unreadable at that size: it is a picture of a page, and at 32px a page is
 * grey. So the mark has to be one shape.
 *
 * The shape is the film's: sky on the film's navy, and a circle, because
 * YouTube crops to one whether or not you drew one.
 */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';

const BG = '#0B1020';
const SKY = '#38BDF8';
const TEXT = '#E4EBF6';

// The lift from Backdrop.tsx, so the avatar and the film share a ground.
const ground = `
  radial-gradient(700px circle at 12% -10%, rgba(56,189,248,.20), transparent 62%),
  radial-gradient(700px circle at 104% 112%, rgba(248,113,113,.14), transparent 60%),
  ${BG}`;

/**
 * An arrow that goes back the way it came. Drawn rather than typed: at 32px a
 * word is a smudge and an arc is still an arc.
 *
 * Everything is computed from the centre and the radius rather than typed in
 * as path coordinates, because the first version was typed in and the ring,
 * the arrowhead and the letter all ended up centred on three different points.
 * The head is a filled triangle laid on the tangent, not a stroked chevron:
 * a chevron at the end of an arc reads as a tick.
 */
const R = 33;
const point = (deg) => {
  const t = (deg * Math.PI) / 180;
  return [50 + R * Math.cos(t), 50 + R * Math.sin(t)];
};

const undo = (stroke, head) => {
  // Clockwise from the tip, most of the way round, leaving a gap on the left.
  const [TIP_DEG, END_DEG] = [206, 152];
  const [sx, sy] = point(TIP_DEG);
  const [ex, ey] = point(END_DEG);

  // Backwards along the path at the tip, which is where the head must point.
  const t = (TIP_DEG * Math.PI) / 180;
  const [bx, by] = [Math.sin(t), -Math.cos(t)];
  const [px, py] = [-by, bx];
  const tri = [
    [sx + bx * head, sy + by * head],
    [sx - bx * head * 0.35 + px * head * 0.62, sy - by * head * 0.35 + py * head * 0.62],
    [sx - bx * head * 0.35 - px * head * 0.62, sy - by * head * 0.35 - py * head * 0.62],
  ];

  return `
  <svg viewBox="0 0 100 100" width="100%" height="100%">
    <path d="M ${sx.toFixed(2)} ${sy.toFixed(2)}
             A ${R} ${R} 0 1 1 ${ex.toFixed(2)} ${ey.toFixed(2)}"
          fill="none" stroke="${SKY}" stroke-width="${stroke}"
          stroke-linecap="round"/>
    <polygon points="${tri.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')}"
             fill="${SKY}"/>
  </svg>`;
};

// Set in the same coordinate system as the ring, so the two share one centre.
const letter = (size) => `
  <text x="50" y="50" text-anchor="middle" dominant-baseline="central"
        fill="${TEXT}" font-size="${size}" font-weight="800"
        font-family="-apple-system,'Helvetica Neue',sans-serif"
        letter-spacing="-2">P</text>`;

const marks = {
  // The retraction on its own. Nothing to read, so nothing to fail to read.
  arc: `<div style="width:58%;height:58%">${undo(11.5, 18)}</div>`,

  // The monogram the film ends on, with the rule it draws under the wordmark.
  // It says the name rather than the act, and at 32px it is one heavy letter,
  // which is the most legible thing on this page.
  letter: `
    <div style="width:66%;height:66%">
      <svg viewBox="0 0 100 100" width="100%" height="100%">
        ${letter(76).replace('y="50"', 'y="42"').replace('x="50"', 'x="52"')}
        <rect x="26" y="84" width="48" height="8" rx="4" fill="${SKY}"/>
      </svg>
    </div>`,

  // Both: the letter sitting inside the return. Busier at 32px and the one
  // that still says which product it is at full size on the channel page.
  both: `
    <div style="width:74%;height:74%">
      <svg viewBox="0 0 100 100" width="100%" height="100%">
        ${undo(7.5, 11).replace(/^[\s\S]*?<svg[^>]*>/, '').replace('</svg>', '')}
        ${letter(40).replace('x="50"', 'x="51.5"')}
      </svg>
    </div>`,
};

const page = (mark) => `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;width:800px;height:800px}
  body{background:${ground};display:grid;place-items:center;
       border-radius:50%;overflow:hidden}
</style>${mark}`;

const browser = await chromium.launch();
const DIR = '../docs/avatar';
await mkdir(DIR, {recursive: true});

for (const [name, mark] of Object.entries(marks)) {
  const tab = await browser.newPage({
    viewport: {width: 800, height: 800},
    deviceScaleFactor: 1,
  });
  await tab.setContent(page(mark));
  await tab.screenshot({path: `${DIR}/${name}.png`, omitBackground: true});

  // The same thing at the size it will be judged at.
  await tab.setViewportSize({width: 32, height: 32});
  await tab.addStyleTag({content: 'html,body{width:32px;height:32px}'});
  await tab.setContent(
    `<!doctype html><style>html,body{margin:0;width:32px;height:32px}
     img{width:32px;height:32px;border-radius:50%}</style>
     <img src="data:image/png;base64,${
       (await (await import('node:fs/promises')).readFile(`${DIR}/${name}.png`)).toString('base64')
     }">`,
  );
  await tab.screenshot({path: `${DIR}/${name}-32.png`});
  await tab.close();
  console.log(`  ${DIR}/${name}.png`);
}

await browser.close();
