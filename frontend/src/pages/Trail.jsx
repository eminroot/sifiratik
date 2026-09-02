import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Link2,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';

import { get, query, useApi } from '../lib/api.js';
import { STATUS_LABEL, STATUS_TONE, date, num, shortHash } from '../lib/format.js';
import { PageHead, Panel, Pill, Resource, Section, Stat } from '../components/ui.jsx';

const PAGE_SIZE = 40;

export default function Trail() {
  const [offset, setOffset] = useState(0);
  const events = useApi(`/audit/events${query({ limit: PAGE_SIZE, offset })}`, [offset]);
  const chain = useApi('/audit/verify');
  const [verifying, setVerifying] = useState(false);

  const reverify = async () => {
    setVerifying(true);
    try {
      await get('/audit/verify');
      chain.reload();
    } finally {
      setVerifying(false);
    }
  };

  const intact = chain.data?.intact;

  return (
    <div className="page">
      <PageHead
        eyebrow="Traceability"
        icon={ScrollText}
        title="Decision log"
      >
        <button type="button" className="btn btn-ghost" onClick={reverify} disabled={verifying}>
          {verifying ? <span className="spin" /> : <ShieldCheck size={15} strokeWidth={1.9} />}
          Verify chain
        </button>
      </PageHead>

      <div className="grid grid-side">
        <Panel>
          <div className="stat-head" style={{ marginBottom: 16 }}>
            <span className="stat-chip">
              {intact === false ? (
                <ShieldAlert size={14} strokeWidth={1.9} />
              ) : (
                <ShieldCheck size={14} strokeWidth={1.9} />
              )}
            </span>
            <span className="label">Verification</span>
            <span className="stat-head-action">
              <Pill tone={intact === false ? 'stop' : 'ok'}>
                {intact === false ? 'Broken' : 'Intact'}
              </Pill>
            </span>
          </div>

          <dl className="facts">
            <div>
              <dt>Decisions checked</dt>
              <dd>{num(chain.data?.events_checked ?? 0)}</dd>
            </div>
            <div>
              <dt>Last verified</dt>
              <dd>{date(chain.data?.verified_at, { time: true })}</dd>
            </div>
            {chain.data?.broken_at && (
              <div>
                <dt>First break</dt>
                <dd>Sequence {chain.data.broken_at}</dd>
              </div>
            )}
          </dl>

          <div className="divider" />
          <span className="label">Head digest</span>
          <p className="hex" style={{ marginTop: 8 }}>
            {chain.data?.head_hash ?? '--'}
          </p>
          {chain.data?.reason && <p className="field-error">{chain.data.reason}</p>}
        </Panel>

        <div className="stack">
          <Stat
            icon={ScrollText}
            label="Decisions on record"
            value={num(chain.data?.total_events ?? 0)}
            note="appended, never edited in place"
          />
          <Panel warm>
            <span className="label">How the link is formed</span>
            <p className="stat-note" style={{ marginTop: 10 }}>
              The digest covers the company, the auditor, the action, the statuses either side of
              it, the note and the timestamp, together with the digest of the previous decision.
            </p>
          </Panel>
        </div>
      </div>

      <Section icon={Link2} title="Recent decisions">
        <Resource state={events} rows={2}>
          {(data) => (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Company</th>
                      <th>Auditor</th>
                      <th>Change</th>
                      <th>Recorded</th>
                      <th>Digest</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((event) => (
                      <tr key={event.sequence}>
                        <td className="rank num">{event.sequence}</td>
                        <td className="lead">
                          {event.company_id ? (
                            <Link
                              to={`/companies/${event.company_id}`}
                              style={{ textDecoration: 'none' }}
                            >
                              {event.company_name}
                            </Link>
                          ) : (
                            <span className="faint">System</span>
                          )}
                          {event.notes && <p className="event-note">{event.notes}</p>}
                        </td>
                        <td className="mono">{event.user_id}</td>
                        <td>
                          <span className="row gap-sm">
                            {event.previous_status && (
                              <span className="faint" style={{ fontSize: 12.5 }}>
                                {STATUS_LABEL[event.previous_status]}
                              </span>
                            )}
                            <ChevronRight size={12} strokeWidth={1.9} className="faint" />
                            <Pill tone={STATUS_TONE[event.new_status]}>
                              {STATUS_LABEL[event.new_status] ?? event.new_status}
                            </Pill>
                          </span>
                        </td>
                        <td className="nowrap">{date(event.created_at, { time: true })}</td>
                        <td>
                          <span className="hash-line" title={event.current_hash}>
                            <Link2 size={12} strokeWidth={1.9} />
                            {shortHash(event.current_hash, 8)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pager">
                <span>
                  {num(data.offset + 1)} to {num(Math.min(data.offset + data.limit, data.total))} of{' '}
                  {num(data.total)}
                </span>
                <span className="row">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  >
                    <ChevronLeft size={13} strokeWidth={1.9} />
                    Newer
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={offset + PAGE_SIZE >= data.total}
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                  >
                    Older
                    <ChevronRight size={13} strokeWidth={1.9} />
                  </button>
                </span>
              </div>
            </>
          )}
        </Resource>
      </Section>
    </div>
  );
}
