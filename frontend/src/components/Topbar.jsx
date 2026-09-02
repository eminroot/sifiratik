import { Link } from 'react-router-dom';
import { CalendarRange, Cpu, ShieldCheck, ShieldAlert } from 'lucide-react';

import { useApp } from '../App.jsx';
import { useApi } from '../lib/api.js';

/**
 * Identity on the left, the three facts that have to stay visible on the
 * right: which period is being read, what produced the scores, and whether
 * the decision log still verifies. Navigation is in the dock.
 */
export default function Topbar() {
  const { period, setPeriod, reference } = useApp();
  const health = useApi('/health');
  const chain = useApi('/audit/verify');

  const periods = reference?.periods ?? [];
  const intact = chain.data?.intact;

  return (
    <header className="topbar">
      <Link className="brand" to="/">
        <span className="brand-glyph" aria-hidden="true">
          <GlyphMark />
        </span>
        <span>
          <span className="brand-mark">GÜS-DEDEKTİV</span>
          <span className="brand-sub">Inspection prioritisation</span>
        </span>
      </Link>

      <div className="topbar-meta">
        <label className="chip" title="Reporting period">
          <CalendarRange size={13} strokeWidth={1.9} />
          <span className="label" style={{ letterSpacing: '0.08em' }}>
            Period
          </span>
          <select
            className="period-select"
            style={{ border: 'none', background: 'none', height: 22, padding: '0 18px 0 0' }}
            value={period ?? ''}
            onChange={(event) => setPeriod(event.target.value)}
            aria-label="Reporting period"
          >
            {periods.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <span className="chip optional" title="Engine that produced the current scores">
          <Cpu size={13} strokeWidth={1.9} />
          <span className="mono">{health.data?.model_version ?? '...'}</span>
        </span>

        <span
          className="chip optional"
          title={intact ? 'Every decision verifies against the one before it' : 'Verification failed'}
        >
          {intact === false ? (
            <ShieldAlert size={13} strokeWidth={1.9} />
          ) : (
            <ShieldCheck size={13} strokeWidth={1.9} />
          )}
          {intact === false ? 'Chain broken' : `${chain.data?.total_events ?? 0} decisions`}
        </span>

        <span className="topbar-user">
          <span className="avatar">MA</span>
          <span>
            <span className="topbar-user-name">M. Aydın</span>
            <span className="topbar-user-role">Inspection lead</span>
          </span>
        </span>
      </div>
    </header>
  );
}

/** The mark: a filing squared off, with the line that does not follow it. */
function GlyphMark() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect
        x="2"
        y="2"
        width="12"
        height="12"
        rx="2.4"
        stroke="currentColor"
        strokeWidth="1.5"
        opacity="0.55"
      />
      <path d="M4.6 10.4 L7 7.4 L9.2 9.1 L11.6 5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
