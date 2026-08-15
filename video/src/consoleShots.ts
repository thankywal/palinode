import {ConsoleShotProps} from './ConsoleShot';
import {theme} from './theme';

/**
 * The eight console captures, and where the camera should end up on each.
 *
 * `focus` is the page point the move settles on, in the texture's own CSS
 * pixels, which for a 1568 wide capture laid out at 1920 means multiplying
 * what you measure on the original by about 1.22. It is chosen per shot
 * because the thing worth reading is in a different place every time: the
 * transaction list on Stripe, the revert commits on GitHub, the one line in
 * the logs where Sentinel scores the run.
 *
 * This is also the file that says what each shot is evidence of. If a caption
 * here stops being true of the capture beside it, the film is lying, so they
 * live together rather than one in a build script and one in a narration.
 */

const SKY = theme.sky;
const VIOLET = theme.violet;
const AMBER = theme.amber;

/** A 1568x764 capture, which is what the browser window gave us. */
const WIDE = 1568 / 764;
/** The scheduler shot, cropped down to the row that matters. */
const STRIP = 1512 / 345;

export const CONSOLE_SHOTS: Record<string, ConsoleShotProps> = {
  scheduler: {
    file: 'p8-scheduler.jpg',
    group: 'WEEKS LATER',
    index: '04',
    title: 'Cloud Scheduler',
    caption:
      'Hourly, against the deployed service. Last run 14:00:21, next run 15:00:02, and nobody was watching either of them.',
    accent: VIOLET,
    // The job row: name, status, frequency, target.
    focus: [860, 300],
    aspect: STRIP,
  },
  stripe: {
    file: 'p1-stripe.jpg',
    group: 'IT WAS REAL',
    index: '05',
    title: 'Stripe',
    caption:
      'Nineteen live charges across the demo runs. Seventeen refunded by Palinode, with nobody asked.',
    accent: SKY,
    // The refunded rows, not the sidebar.
    focus: [1080, 560],
    aspect: WIDE,
  },
  github: {
    file: 'p2-github.jpg',
    group: 'IT WAS REAL',
    index: '06',
    title: 'GitHub',
    caption: 'Every approve commit followed by a revert, on the real default branch.',
    accent: SKY,
    // The commit pairs.
    focus: [900, 520],
    aspect: WIDE,
  },
  slack: {
    file: 'p7-slack.jpg',
    group: 'IT WAS REAL',
    index: '07',
    title: 'Slack',
    caption: 'The approval deleted, and the correction standing where it was.',
    accent: SKY,
    // The retraction lines at the bottom of the channel.
    focus: [1180, 660],
    aspect: WIDE,
  },
  cloudrun: {
    file: 'p3-cloudrun.jpg',
    group: 'GOOGLE CLOUD',
    index: '08',
    title: 'Cloud Run',
    caption: 'Request based billing, minimum zero instances, capped at three.',
    accent: VIOLET,
    // The auto scaling panel on the right.
    focus: [1400, 560],
    aspect: WIDE,
  },
  logs: {
    file: 'p6-logs.jpg',
    group: 'GOOGLE CLOUD',
    index: '09',
    title: 'The logs',
    caption:
      'Sentinel scoring the run at 1.00 on its own, then the instance shutting down.',
    accent: VIOLET,
    // The sentinel line, which is the only one that matters here.
    focus: [1080, 340],
    aspect: WIDE,
  },
  trace: {
    file: 'p5-trace.jpg',
    group: 'GOOGLE CLOUD',
    index: '10',
    title: 'Cloud Trace',
    caption:
      'palinode.sentinel.assess, warden.evaluate, regret.compensate. Our spans, not just what ADK emits.',
    accent: VIOLET,
    // The span name list on the left.
    focus: [420, 400],
    aspect: WIDE,
  },
  firestore: {
    file: 'p4-firestore.jpg',
    group: 'GOOGLE CLOUD',
    index: '11',
    title: 'Firestore',
    caption:
      'A SPIFFE actor, the causal parent, the contract written before the act, and the hash that commits to it.',
    accent: AMBER,
    // The document fields in the right hand pane.
    focus: [1560, 620],
    aspect: WIDE,
  },
};
