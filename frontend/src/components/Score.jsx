import { LEVEL_LABEL, LEVEL_TONE, POSITION_LABEL, lira, tonnes } from '../lib/format.js';
import { Pill } from './ui.jsx';

/**
 * The score against the bands it is read with. A number on its own says
 * nothing; a number sitting inside the scale it was graded on does.
 */
export function ScoreBlock({ score, level, bands, confidence, coverage, quality }) {
  const segments = bands ?? [
    { level: 'LOW', lower: 0, upper: 24 },
    { level: 'MEDIUM', lower: 25, upper: 49 },
    { level: 'HIGH', lower: 50, upper: 74 },
    { level: 'CRITICAL', lower: 75, upper: 100 },
  ];

  return (
    <div>
      <div className="score-hero">
        <div className="score-figure">
          <b className="tnum">{score.toFixed(0)}</b>
          <span>/ 100</span>
        </div>
        <div style={{ paddingTop: 6 }}>
          <Pill tone={LEVEL_TONE[level]}>{LEVEL_LABEL[level]} priority</Pill>
          <div className="stat-note" style={{ marginTop: 9, maxWidth: '32ch' }}>
            {confidence === 'LOW'
              ? 'Ranked on a thin evidence base. Treat the position as provisional.'
              : 'Ranked for human review, not judged.'}
          </div>
        </div>
      </div>

      <div className="score-scale">
        <div className="score-track" aria-hidden="true">
          {segments.map((band) => (
            <i
              key={band.level}
              className={score >= band.lower && score <= band.upper ? 'on' : undefined}
              style={{ width: `${band.upper - band.lower + 1}%` }}
            />
          ))}
        </div>
        <div className="score-marks" aria-hidden="true">
          {segments.map((band, index) => (
            <span key={band.level} style={{ left: `${index === 0 ? 0 : band.lower}%` }}>
              {index === 0 ? '0' : band.lower}
            </span>
          ))}
          <span style={{ left: '100%' }}>100</span>
        </div>
      </div>

      <div className="range-legend">
        <div>
          <span className="label">Evidence coverage</span>
          <b className="tnum">{Math.round(coverage * 100)}%</b>
        </div>
        <div>
          <span className="label">Data quality</span>
          <b className="tnum">{Math.round(quality)}%</b>
        </div>
      </div>
    </div>
  );
}

/**
 * Declared amount against the range the company's own output implies. The
 * band is hatched rather than filled: it is an interval, not a target figure.
 */
export function RangeBar({ expected }) {
  const { lower, median, upper, declared, position, shortfall_tonnage, estimated_gekap_gap_try } =
    expected;

  const ceiling = Math.max(upper, declared ?? 0) * 1.15 || 1;
  const at = (value) => `${Math.max(0, Math.min(100, (value / ceiling) * 100))}%`;
  const filed = declared ?? 0;

  return (
    <div className="range">
      <div className="range-track">
        <div
          className="range-band"
          style={{ left: at(lower), width: `calc(${at(upper)} - ${at(lower)})` }}
        />
        <div className="range-median" style={{ left: at(median) }} />
        <div
          className={`range-actual ${position === 'BELOW' ? 'below' : position === 'ABOVE' ? 'above' : ''}`}
          style={{ left: at(filed) }}
          title={declared === null ? 'No filing' : `${filed} t declared`}
        />
      </div>

      <div className="range-scale" aria-hidden="true">
        <span style={{ left: 0, transform: 'none' }}>0</span>
        <span style={{ left: at(lower) }}>{tonnes(lower, { unit: false })}</span>
        <span style={{ left: at(upper) }}>{tonnes(upper, { unit: false })}</span>
      </div>

      <div className="range-legend">
        <div>
          <span className="label">Declared</span>
          <b className={`tnum${position === 'BELOW' ? ' stop' : ''}`}>{tonnes(declared)}</b>
        </div>
        <div>
          <span className="label">Expected range</span>
          <b className="tnum">
            {tonnes(lower, { unit: false })} to {tonnes(upper)}
          </b>
        </div>
        <div>
          <span className="label">Expected median</span>
          <b className="tnum">{tonnes(median)}</b>
        </div>
        {shortfall_tonnage > 0 && (
          <>
            <div>
              <span className="label">Unexplained</span>
              <b className="tnum stop">{tonnes(shortfall_tonnage)}</b>
            </div>
            <div>
              <span className="label">Contribution at stake</span>
              <b className="tnum">{lira(estimated_gekap_gap_try)}</b>
            </div>
          </>
        )}
      </div>

      <p className="stat-note" style={{ marginTop: 14 }}>
        {POSITION_LABEL[position]}
        {shortfall_tonnage > 0
          ? `. The shortfall is measured against the bottom of the range, not its middle.`
          : '.'}
      </p>
    </div>
  );
}
