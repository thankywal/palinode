import React from 'react';
import {AbsoluteFill} from 'remotion';
import {theme} from './theme';

/**
 * The same background the dashboard uses, so a cut from a title card to the
 * live screen recording does not read as a cut to a different product.
 */
export const Backdrop: React.FC<{children?: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{backgroundColor: theme.bg}}>
    <AbsoluteFill
      style={{
        background: `
          radial-gradient(900px circle at 8% -6%, rgba(56,189,248,.16), transparent 60%),
          radial-gradient(900px circle at 100% 108%, rgba(248,113,113,.12), transparent 60%)
        `,
      }}
    />
    {children}
  </AbsoluteFill>
);
