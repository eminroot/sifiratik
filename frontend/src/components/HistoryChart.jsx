import { num, tonnes } from '../lib/format.js';

const axisLabel = (value) => num(Math.round(value));

const WIDTH = 760;
const PAD_LEFT = 46;
const PAD_RIGHT = 14;
const TOP_H = 176;
const GAP = 42;
const BOTTOM_H = 62;
const HEIGHT = TOP_H + GAP + BOTTOM_H + 24;

function niceCeiling(value) {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const scaled = value / magnitude;
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
  return step * magnitude;
}

/**
 * Two panels on one axis: what was declared against what was expected, and
 * underneath it the output the expectation was built from. Kept apart rather
 * than drawn on twin scales, because two y-axes in one frame invite the reader
 * to compare things that are not comparable.
 */
export default function HistoryChart({ rows }) {
  const periods = rows.filter(Boolean);
  if (periods.length < 2) return null;

  const declaredMax = Math.max(
    ...periods.map((row) => Math.max(row.declared_tonnage ?? 0, row.expected_upper ?? 0)),
  );
  const top = niceCeiling(declaredMax * 1.08);

  const basis = periods.map(
    (row) => (row.production_volume ?? 0) + (row.import_volume ?? 0),
  );
  const basisMax = niceCeiling(Math.max(...basis) * 1.05);

  const innerWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const step = innerWidth / Math.max(1, periods.length - 1);
  const x = (index) => PAD_LEFT + index * step;
  const y = (value) => TOP_H - (Math.max(0, value) / top) * (TOP_H - 14) + 6;

  const bandTop = periods
    .map((row, index) => `${x(index)},${y(row.expected_upper ?? 0)}`)
    .join(' ');
  const bandBottom = periods
    .map((row, index) => `${x(index)},${y(row.expected_lower ?? 0)}`)
    .reverse()
    .join(' ');

  // A period without a filing breaks the line rather than being bridged over.
  const segments = [];
  let current = [];
  periods.forEach((row, index) => {
    if (row.declared_tonnage === null || row.declared_tonnage === undefined) {
      if (current.length) segments.push(current);
      current = [];
      return;
    }
    current.push(`${x(index)},${y(row.declared_tonnage)}`);
  });
  if (current.length) segments.push(current);

  const ticks = [0, top / 2, top];
  const barWidth = Math.min(26, step * 0.5);
  const barBase = TOP_H + GAP + BOTTOM_H;

  return (
    <div>
      <svg
        className="chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Declared packaging against the expected range, with output underneath"
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid-line" x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={y(tick)} y2={y(tick)} />
            <text className="tick" x={PAD_LEFT - 8} y={y(tick) + 3} textAnchor="end">
              {axisLabel(tick)}
            </text>
          </g>
        ))}

        <polygon className="band" points={`${bandTop} ${bandBottom}`} />
        <polyline className="band-edge" points={bandTop} />
        <polyline className="band-edge" points={bandBottom} />

        {segments.map((segment, index) => (
          <polyline className="series" key={index} points={segment.join(' ')} />
        ))}

        {periods.map((row, index) => {
          if (row.declared_tonnage === null || row.declared_tonnage === undefined) return null;
          const below = row.expected_lower !== null && row.declared_tonnage < row.expected_lower;
          return (
            <circle
              key={row.period}
              className={`point${below ? ' miss' : ''}`}
              cx={x(index)}
              cy={y(row.declared_tonnage)}
              r={3.4}
            >
              <title>{`${row.period}: ${tonnes(row.declared_tonnage)} declared`}</title>
            </circle>
          );
        })}

        <line className="axis" x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={TOP_H + 6} y2={TOP_H + 6} />

        {periods.map((row, index) => {
          const height = (basis[index] / basisMax) * BOTTOM_H;
          return (
            <rect
              key={row.period}
              className={`col${index === periods.length - 1 ? ' now' : ''}`}
              x={x(index) - barWidth / 2}
              y={barBase - height}
              width={barWidth}
              height={Math.max(1, height)}
              rx="2"
            >
              <title>{`${row.period}: ${tonnes(basis[index])} of output`}</title>
            </rect>
          );
        })}

        <line className="axis" x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={barBase} y2={barBase} />
        <text className="tick" x={PAD_LEFT - 8} y={barBase - BOTTOM_H + 9} textAnchor="end">
          {axisLabel(basisMax)}
        </text>
        <text className="tick-x" x={PAD_LEFT} y={TOP_H + GAP - 8} textAnchor="start">
          Output, tonnes
        </text>
        <text className="tick-x" x={PAD_LEFT} y={16} textAnchor="start">
          Packaging, tonnes
        </text>

        {periods.map((row, index) => {
          const skip = periods.length > 7 && index % 2 === 1 && index !== periods.length - 1;
          if (skip) return null;
          return (
            <text className="tick-x" key={row.period} x={x(index)} y={HEIGHT - 4} textAnchor="middle">
              {row.period}
            </text>
          );
        })}
      </svg>

      <div className="chart-legend">
        <span>
          <i />
          Declared packaging
        </span>
        <span>
          <i className="band" />
          Expected range at the time
        </span>
        <span>
          <i className="col" />
          Production and imports
        </span>
      </div>
    </div>
  );
}
