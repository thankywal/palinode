import React from 'react';
import {Composition} from 'remotion';
import {Chapter, ChapterProps} from './Chapter';
import {Invoices} from './Invoices';
import {Sweeper} from './Sweeper';
import {ConsoleShot} from './ConsoleShot';
import {LedgerReview, ROWS} from './LedgerReview';
import {CONSOLE_SHOTS} from './consoleShots';
import {Intro} from './Intro';
import {Outro} from './Outro';
import {FPS, theme} from './theme';
import timing from './timing.json';

/**
 * Title cards only.
 *
 * Every duration here is read from timing.json, which plan.py derives from the
 * measured length of the narration. A card that runs a second longer than the
 * line over it is a card the voice is fighting.
 *
 * The demo itself is a screen recording of the real dashboard driving the real
 * control plane, because the rules ask for a live unedited demonstration and
 * an animated reconstruction of a product working is not that. These cards top
 * and tail it and mark the chapters.
 */
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Intro"
      component={Intro}
      durationInFrames={timing.intro.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Chapter"
      component={Chapter}
      durationInFrames={2 * FPS}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={
        {
          index: '01',
          title: 'The fleet does its job',
          subtitle: 'Three ADK agents, five real actions, one poisoned invoice.',
          accent: theme.sky,
        } satisfies ChapterProps
      }
    />

    <Composition
      id="Invoices"
      component={Invoices}
      durationInFrames={timing.invoices.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Review"
      component={LedgerReview}
      durationInFrames={timing.review.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={{
        kicker: 'One run, four of them back',
        title: 'What came back',
        accent: theme.green,
        push: 1.07,
        marks: [
          {...ROWS.db, at: timing.review.beats[0] + 46, tone: '#4ADE80'},
          {...ROWS.slack, at: timing.review.beats[1] + 40, tone: '#FBBF24'},
          {...ROWS.email, at: timing.review.beats[1] + 132, tone: '#FBBF24'},
          {...ROWS.stripe, at: timing.review.beats[2] + 62, tone: '#FBBF24'},
        ],
      }}
    />

    <Composition
      id="Disclosure"
      component={LedgerReview}
      durationInFrames={timing.disclosure.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={{
        kicker: 'And one that does not',
        title: 'What could not be taken back',
        accent: theme.red,
        push: 1.1,
        marks: [
          {...ROWS.wire, at: timing.disclosure.beats[0] + 20, tone: '#F87171'},
          {...ROWS.disclosure, at: timing.disclosure.beats[1] + 44, label: '$4,200.00', labelSide: 'left', tone: '#F87171'},
        ],
      }}
    />

    <Composition
      id="Sweeper"
      component={Sweeper}
      durationInFrames={timing.sweeper.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Outro"
      component={Outro}
      durationInFrames={timing.outro.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />
    {Object.entries(CONSOLE_SHOTS).map(([name, props]) => (
      <Composition
        key={name}
        id={`shot-${name}`}
        component={ConsoleShot}
        durationInFrames={(timing.shots as Record<string, number>)[name] ?? 150}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={props}
      />
    ))}
  </>
);
