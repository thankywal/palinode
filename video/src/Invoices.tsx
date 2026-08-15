import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Backdrop} from './Backdrop';
import {font, mono, theme} from './theme';
import timing from './timing.json';

/**
 * The two documents, read and screened.
 *
 * This is the argument the whole project rests on, so it gets a purpose built
 * shot. Both invoices send the money to the same account. One is a prompt
 * injection and is caught. The other is an ordinary invoice with the bank
 * details changed, and there is nothing in it for a filter to catch.
 *
 * Everything here is a real response from the deployed service. The pages are
 * the files the reader is handed, the extracted fields are what Gemini 3.5
 * Flash returned, and both Model Armor verdicts are what the API said. The
 * pair on the left is the one that matters: the same injection is MATCH_FOUND
 * on its own and NO_MATCH_FOUND inside the page it sits in.
 *
 * When each beat lands is read from timing.json, so a verdict stamps on the
 * sentence that describes it rather than on a frame number that once looked
 * about right.
 */

const Verdict: React.FC<{label: string; value: string; hit: boolean}> = ({
  label,
  value,
  hit,
}) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: 16,
      padding: '9px 0',
      borderTop: '1px solid rgba(255,255,255,.09)',
    }}
  >
    <div style={{fontSize: 18, color: theme.dim}}>{label}</div>
    <div
      style={{
        fontFamily: mono,
        fontSize: 18,
        fontWeight: 700,
        color: hit ? theme.green : theme.amber,
        whiteSpace: 'nowrap',
      }}
    >
      {value}
    </div>
  </div>
);

const Card: React.FC<{
  at: number;
  readAt: number;
  verdictAt: number;
  title: string;
  file: string;
  amount: string;
  remit: string;
  changed: string;
  page: string;
  block: string;
  blockHit: boolean;
  decision: string;
  caught: boolean;
}> = ({
  at,
  readAt,
  verdictAt,
  title,
  file,
  amount,
  remit,
  changed,
  page,
  block,
  blockHit,
  decision,
  caught,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame: frame - at, fps, config: {damping: 200}});
  const read = spring({frame: frame - readAt, fps, config: {damping: 200}});
  const stamp = spring({frame: frame - verdictAt, fps, config: {damping: 200}});

  const accent = caught ? theme.green : theme.red;

  return (
    <div
      style={{
        flex: 1,
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [24, 0])}px)`,
        display: 'flex',
        gap: 24,
        alignItems: 'flex-start',
      }}
    >
      {/* The page itself, at the aspect it was rendered at. */}
      <div
        style={{
          width: 452,
          borderRadius: 10,
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,.16)',
          boxShadow: '0 22px 60px rgba(0,0,0,.5)',
          alignSelf: 'flex-start',
        }}
      >
        <Img src={staticFile(file)} style={{width: '100%', display: 'block'}} />
      </div>

      <div style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
        <div style={{fontSize: 24, color: theme.dim, fontWeight: 600}}>{title}</div>

        <div
          style={{
            marginTop: 14,
            opacity: read,
            border: '1px solid rgba(192,132,252,.4)',
            background: 'rgba(192,132,252,.07)',
            borderRadius: 10,
            padding: '13px 15px',
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              letterSpacing: 2.4,
              textTransform: 'uppercase',
              fontWeight: 800,
              color: theme.violet,
              marginBottom: 9,
            }}
          >
            Read by Gemini 3.5 Flash
          </div>
          {[
            ['amount', amount],
            ['remit to', remit],
            ['bank details changed', changed],
          ].map(([k, v]) => (
            <div
              key={k}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 17,
                padding: '3px 0',
                color: theme.dim,
              }}
            >
              <span>{k}</span>
              <b style={{fontFamily: mono, color: theme.text, fontSize: 16}}>{v}</b>
            </div>
          ))}
        </div>

        <div style={{marginTop: 12, opacity: stamp}}>
          <Verdict label="the whole page" value={page} hit={false} />
          <Verdict
            label="the block addressed to the processor"
            value={block}
            hit={blockHit}
          />
        </div>

        <div
          style={{
            marginTop: 16,
            opacity: stamp,
            border: `2px solid ${accent}`,
            background: caught ? 'rgba(34,197,94,.10)' : 'rgba(239,68,68,.09)',
            borderRadius: 10,
            padding: '12px 16px',
            fontSize: 20,
            fontWeight: 700,
            color: accent,
          }}
        >
          {decision}
        </div>
      </div>
    </div>
  );
};

export const Invoices: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const {readB, verdictA, verdictB, punchline} = timing.invoices;

  const head = spring({frame, fps, config: {damping: 200}});
  const punch = spring({frame: frame - punchline, fps, config: {damping: 200}});
  const out = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames],
    [1, 0],
    {extrapolateLeft: 'clamp'}
  );

  return (
    <Backdrop>
      <AbsoluteFill
        style={{
          fontFamily: font,
          color: theme.text,
          padding: '42px 58px 36px',
          opacity: out,
        }}
      >
        <div style={{opacity: head}}>
          <div
            style={{
              fontSize: 15,
              letterSpacing: 5,
              fontWeight: 700,
              color: theme.sky,
              textTransform: 'uppercase',
            }}
          >
            Two invoices, as they arrive
          </div>
          <div style={{fontSize: 38, fontWeight: 800, letterSpacing: -1, marginTop: 6}}>
            Both of these send the money to the same account
          </div>
        </div>

        <div style={{display: 'flex', gap: 36, marginTop: 22, flex: 1, alignItems: 'flex-start'}}>
          <Card
            at={8}
            readAt={20}
            verdictAt={verdictA}
            title="Invoice A"
            file="loud.png"
            amount="$1,180.00"
            remit="acct-northwind-01"
            changed="no"
            page="NO_MATCH_FOUND"
            block="MATCH_FOUND · HIGH"
            blockHit
            decision="Blocked. The fleet never sees it."
            caught
          />
          <Card
            at={readB}
            readAt={readB + 12}
            verdictAt={verdictB}
            title="Invoice B"
            file="quiet.png"
            amount="$4,200.00"
            remit="acct-unknown-77"
            changed="yes"
            page="NO_MATCH_FOUND"
            block="NO_MATCH_FOUND"
            blockHit={false}
            decision="Passed. There is no injection in it to find."
            caught={false}
          />
        </div>

        <div
          style={{
            marginTop: 20,
            opacity: punch,
            fontSize: 26,
            lineHeight: 1.4,
          }}
        >
          Prevention caught the loud one.{' '}
          <span style={{color: theme.red, fontWeight: 700}}>
            The quiet one is what actually happens to companies.
          </span>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
