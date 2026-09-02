import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircleCheck, FileX2, Flag } from 'lucide-react';

import { useApp } from '../App.jsx';
import { post } from '../lib/api.js';
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

/**
 * The two decisions an operator can take without leaving the list: put a
 * company on the field schedule, or accept its declaration and take it out of
 * the queue. Both append to the audit chain exactly as the review sheet does,
 * so nothing recorded from here is a shortcut around the record.
 */
const ACTIONS = [
  {
    key: 'flag',
    status: 'MARKED_FOR_INSPECTION',
    icon: Flag,
    label: 'Mark for inspection',
    done: 'is on the field schedule',
    title: 'Mark for inspection — adds the company to the field schedule',
    titleOn: 'Already marked for inspection',
  },
  {
    key: 'clear',
    status: 'NO_ACTION_REQUIRED',
    icon: CircleCheck,
    label: 'Clear',
    done: 'is out of the queue',
    title: 'Clear — accepts the declaration and takes the company out of the queue',
    titleOn: 'Already cleared, no action required',
  },
];

export default function QueueTable({ items, compact = false }) {
  const navigate = useNavigate();
  const { period, toast } = useApp();

  // The list is owned by whichever page fetched it, so a decision taken here
  // is held locally rather than by refetching the whole page underneath the
  // operator and losing their scroll position.
  const [decided, setDecided] = useState({});
  const [saving, setSaving] = useState(null);

  if (!items.length) {
    return (
      <Empty
        icon={FileX2}
        title="Nothing matches those filters"
        note="Widen the selection, or clear it to see the whole period."
      />
    );
  }

  const decide = async (item, action) => {
    setSaving(`${item.company_id}:${action.key}`);
    try {
      await post(`/companies/${item.company_id}/review?period=${period}`, {
        status: action.status,
        auditor_id: 'aydin.m',
        notes: `${action.label} from the inspection queue.`,
      });
      setDecided((current) => ({ ...current, [item.company_id]: action.status }));
      toast(`${item.company_name} ${action.done}`);
    } catch (error) {
      toast(error.message, 'bad');
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className={`table-wrap${compact ? ' compact' : ''}`}>
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
            <th className="col-actions">Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const status = decided[item.company_id] ?? item.review_status;

            return (
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
                  <Pill tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Pill>
                </td>

                <td className="col-actions">
                  <span className="row-actions">
                    {ACTIONS.map((action) => {
                      const on = status === action.status;
                      const busy = saving === `${item.company_id}:${action.key}`;

                      return (
                        <button
                          key={action.key}
                          type="button"
                          className={`row-action ${action.key}${on ? ' on' : ''}`}
                          title={on ? action.titleOn : action.title}
                          aria-label={`${action.label}: ${item.company_name}`}
                          aria-pressed={on}
                          disabled={on || busy || saving !== null}
                          onClick={(event) => {
                            event.stopPropagation();
                            decide(item, action);
                          }}
                        >
                          {busy ? <span className="spin" /> : <action.icon size={14} strokeWidth={1.9} />}
                        </button>
                      );
                    })}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
