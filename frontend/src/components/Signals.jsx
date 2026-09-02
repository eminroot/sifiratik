import { CircleSlash, MinusCircle } from 'lucide-react';

import { useT } from '../lib/i18n.jsx';
import { SIGNAL_STATE_TONE, percent, signalName, signalStateLabel } from '../lib/format.js';
import { Empty, Pill } from './ui.jsx';

/** The signals that fired, ranked by how much of the score each one carries. */
export function ReasonList({ signals }) {
  const t = useT();

  const active = signals
    .filter((signal) => signal.status === 'ACTIVE')
    .sort((a, b) => b.contribution - a.contribution);

  if (!active.length) {
    return (
      <Empty
        icon={MinusCircle}
        title={t('signals.quietTitle')}
        note={t('signals.quietNote')}
      />
    );
  }

  return (
    <div className="reasons">
      {active.map((signal, index) => (
        <article className="reason" key={signal.code}>
          <div className="reason-index">{String(index + 1).padStart(2, '0')}</div>
          <div>
            <h3 className="reason-name">
              <span className="reason-code">{signal.code}</span>
              {signalName(signal.code)}
            </h3>
            <p className="reason-text">{signal.explanation}</p>
          </div>
          <div className="reason-share">
            <b>{percent(signal.contribution)}</b>
            <div className="reason-bar">
              <i style={{ width: `${Math.min(100, signal.contribution)}%` }} />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

/** All eight, including the ones that could not run and why. */
export function SignalGrid({ signals }) {
  const t = useT();

  return (
    <div className="signal-grid">
      {signals.map((signal) => {
        const off = !signal.available;
        return (
          <article className={`signal${off ? ' off' : ''}`} key={signal.code}>
            <div className="signal-head">
              <span className="signal-code">{signal.code}</span>
              <span className="signal-name">{signalName(signal.code)}</span>
              <Pill tone={SIGNAL_STATE_TONE[signal.status]}>
                {signalStateLabel(signal.status)}
              </Pill>
            </div>

            <p className={`signal-body${off ? ' quiet' : ''}`}>
              {off ? signal.missing_data_reason : signal.explanation}
            </p>

            <div className="signal-foot">
              {off ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CircleSlash size={12.5} strokeWidth={1.9} />
                  {t('signals.notEvaluated')}
                </span>
              ) : (
                <>
                  <span>
                    {t('signals.score')} <b>{signal.score?.toFixed(0)}</b>
                  </span>
                  <span>
                    {t('signals.contribution')} <b>{percent(signal.contribution)}</b>
                  </span>
                  <span style={{ marginLeft: 'auto' }}>
                    {t('signals.weight', { percent: percent(signal.weight * 100) })}
                  </span>
                </>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}
