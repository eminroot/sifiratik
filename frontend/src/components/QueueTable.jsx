import { useNavigate } from 'react-router-dom';
import { FileX2 } from 'lucide-react';

import {
  LEVEL_LABEL,
  LEVEL_TONE,
  SIZE_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  lira,
  num,
  qualityTone,
  tonnes,
} from '../lib/format.js';
import { Empty, Meter, Pill } from './ui.jsx';

export default function QueueTable({ items, compact = false }) {
  const navigate = useNavigate();

  if (!items.length) {
    return (
      <Empty
        icon={FileX2}
        title="Nothing matches those filters"
        note="Widen the selection, or clear it to see the whole period."
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Company</th>
            <th>Sector</th>
            {!compact && <th>Region</th>}
            <th>Priority</th>
            <th>Leading reason</th>
            {!compact && <th>Declared</th>}
            <th>Data</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.company_id}
              className="clickable"
              onClick={() => navigate(`/companies/${item.company_id}`)}
            >
              <td className="rank num">{item.rank}</td>

              <td className="lead">
                <span className="cell-name">
                  {item.company_name}
                  <em>
                    <span className="mono">{item.tax_identifier}</span>
                    {' · '}
                    {SIZE_LABEL[item.company_size]}
                  </em>
                </span>
              </td>

              <td>{item.sector_label}</td>
              {!compact && <td>{item.region}</td>}

              <td>
                <span className="score-cell">
                  <b>{item.priority_score.toFixed(0)}</b>
                  <Meter value={item.priority_score} tone={LEVEL_TONE[item.priority_level]} />
                  <Pill tone={LEVEL_TONE[item.priority_level]}>
                    {LEVEL_LABEL[item.priority_level]}
                  </Pill>
                </span>
              </td>

              <td className="cell-reason">
                {item.main_reason ? (
                  <>
                    <span className="reason-inline">
                      <span className="signal-code">{item.main_reason.code}</span>
                      {item.main_reason.name}
                    </span>
                    <span>{num(item.main_reason.contribution)}% of the score</span>
                  </>
                ) : (
                  <span>No check raised a concern</span>
                )}
              </td>

              {!compact && (
                <td className="num">
                  {item.declared_tonnage === null ? (
                    <Pill tone="stop">No filing</Pill>
                  ) : (
                    <>
                      {tonnes(item.declared_tonnage)}
                      {item.shortfall_tonnage > 0 && (
                        <span style={{ display: 'block', fontSize: 12, color: 'var(--ink-3)' }}>
                          {lira(item.estimated_gekap_gap_try)} at stake
                        </span>
                      )}
                    </>
                  )}
                </td>
              )}

              <td className="num">
                <span className={`quality-${qualityTone(item.data_quality_score)}`}>
                  {item.data_quality_score.toFixed(0)}%
                </span>
              </td>

              <td>
                <Pill tone={STATUS_TONE[item.review_status]}>
                  {STATUS_LABEL[item.review_status]}
                </Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
