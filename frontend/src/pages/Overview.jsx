import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  Boxes,
  Coins,
  Crosshair,
  Database,
  Gauge,
  LayoutGrid,
  ListChecks,
  RefreshCw,
  SignalHigh,
} from 'lucide-react';

import { useApp } from '../App.jsx';
import { post, query, useApi } from '../lib/api.js';
import {
  LEVEL_LABEL,
  STATUS_LABEL,
  lira,
  num,
  percent,
  splitUnit,
  tonnes,
} from '../lib/format.js';
import { Figures, PageHead, Panel, Pill, Resource, Section, Stat } from '../components/ui.jsx';
import QueueTable from '../components/QueueTable.jsx';

const MIX_TONE = { CRITICAL: 'stop', HIGH: 'warn', MEDIUM: 'mute', LOW: 'ok' };

export default function Overview() {
  const { period, toast } = useApp();
  const state = useApi(`/dashboard${query({ period })}`, [period]);
  const [running, setRunning] = useState(false);

  const rerun = async () => {
    setRunning(true);
    try {
      const result = await post('/scoring/run', { period });
      toast(`${result.companies_scored} companies rescored in ${result.duration_ms} ms`);
      state.reload();
    } catch (error) {
      toast(error.message, 'bad');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page">
      <Resource state={state}>
        {(data) => (
          <>
            <PageHead
              eyebrow={`Period ${data.period}`}
              icon={LayoutGrid}
              title="Overview"
            >
              <button
                type="button"
                className="btn btn-primary"
                onClick={rerun}
                disabled={running}
              >
                {running ? <span className="spin on-ink" /> : <RefreshCw size={15} strokeWidth={1.9} />}
                {running ? 'Scoring' : 'Re-run scoring'}
              </button>
            </PageHead>

            <div className="stat-grid">
              <div className="panel stat-hero">
                <div className="panel-body">
                  <div className="stat-head">
                    <span className="stat-chip">
                      <Boxes size={15} strokeWidth={1.9} />
                    </span>
                    <span className="label">Priority spread</span>
                    <span className="stat-head-action">
                      <Link className="btn btn-quiet btn-sm" to="/queue">
                        Open queue
                        <ArrowUpRight size={13} strokeWidth={1.9} />
                      </Link>
                    </span>
                  </div>

                  <div className="stat-value">{num(data.companies_analysed)}</div>
                  <div className="stat-note">
                    companies scored across {data.regions_covered} provinces and{' '}
                    {data.sectors_covered} sectors
                  </div>

                  <div className="mix">
                    {data.by_level.map((band) => (
                      <span
                        key={band.level}
                        className={`mix-part ${MIX_TONE[band.level]}`}
                        style={{ flex: Math.max(band.count, 0.4) }}
                        title={`${LEVEL_LABEL[band.level]}: ${band.count}`}
                      />
                    ))}
                  </div>
                  <ul className="mix-legend">
                    {data.by_level.map((band) => (
                      <li key={band.level}>
                        <i className={MIX_TONE[band.level]} />
                        {LEVEL_LABEL[band.level]} <b>{num(band.count)}</b>
                        <em>{percent(band.share)}</em>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <Figures rows>
                <Stat
                  icon={ListChecks}
                  label="Awaiting a decision"
                  value={num(data.awaiting_review)}
                  note={`${num(data.in_progress)} in progress, ${num(data.reviewed)} closed`}
                />
                <Stat
                  icon={Database}
                  label="No filing on record"
                  value={num(data.companies_without_declaration)}
                  note="Output is known, a declaration is not"
                  tone={data.companies_without_declaration ? 'warn' : undefined}
                />
              </Figures>
            </div>

            <Section icon={Coins} title="Exposure">
              <Figures columns={3}>
                <Stat
                  icon={Boxes}
                  label="Tonnage identified"
                  {...splitUnit(tonnes(data.additional_tonnage_identified))}
                  note="Below the expected range, at high and critical priority"
                />
                <Stat
                  icon={Coins}
                  label="Contribution at stake"
                  {...splitUnit(lira(data.estimated_gekap_gap_try))}
                  note="2026 tariff applied to the unexplained tonnage"
                />
                <Stat
                  icon={Crosshair}
                  label="Concentration"
                  {...splitUnit(percent(data.exposure_share_in_top_50))}
                  note={`of that sits in the top 50 companies, worth ${lira(data.exposure_in_top_50_try)}`}
                />
              </Figures>
            </Section>

            <Section
              icon={ListChecks}
              title="Priority queue"
              actions={
                <Link className="btn btn-ghost btn-sm" to="/queue">
                  All {num(data.companies_analysed)} companies
                  <ArrowUpRight size={13} strokeWidth={1.9} />
                </Link>
              }
            >
              <QueueTable items={data.priority_queue} compact />
            </Section>

            <Section icon={Gauge} title="Coverage">
              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 14 }}>
                    <span className="stat-chip">
                      <Database size={14} strokeWidth={1.9} />
                    </span>
                    <span className="label">Field coverage</span>
                    <span className="stat-head-action">
                      <Link className="btn btn-quiet btn-sm" to="/data-quality">
                        Detail
                        <ArrowUpRight size={13} strokeWidth={1.9} />
                      </Link>
                    </span>
                  </div>

                  {data.field_coverage.map((field) => (
                    <div className="coverage-row" key={field.key}>
                      <div className="coverage-name">
                        {field.label}
                        <span>
                          {num(field.available)} complete, {num(field.partial)} partial,{' '}
                          {num(field.missing)} missing
                        </span>
                      </div>
                      <div className="coverage-bar">
                        <i className="ok" style={{ width: `${(field.available / data.companies_analysed) * 100}%` }} />
                        <i className="warn" style={{ width: `${(field.partial / data.companies_analysed) * 100}%` }} />
                        <i className="stop" style={{ width: `${(field.missing / data.companies_analysed) * 100}%` }} />
                      </div>
                      <div className="coverage-value tnum">{percent(field.coverage)}</div>
                    </div>
                  ))}
                </Panel>

                <Panel>
                  <div className="stat-head" style={{ marginBottom: 14 }}>
                    <span className="stat-chip">
                      <SignalHigh size={14} strokeWidth={1.9} />
                    </span>
                    <span className="label">Signals evaluated</span>
                  </div>

                  <table className="table" style={{ marginTop: -4 }}>
                    <tbody>
                      {data.signal_availability.map((signal) => (
                        <tr key={signal.code}>
                          <td style={{ padding: '9px 0' }}>
                            <span className="signal-code" style={{ marginRight: 8 }}>
                              {signal.code}
                            </span>
                            {signal.name}
                          </td>
                          <td className="num right" style={{ padding: '9px 0', width: 90 }}>
                            {percent(signal.availability_rate)}
                          </td>
                          <td className="right" style={{ padding: '9px 0', width: 74 }}>
                            <Pill tone={signal.active ? 'warn' : 'mute'}>{signal.active} firing</Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="figure-note" style={{ marginTop: 14, paddingTop: 0 }}>
                    A check that cannot run is held out of the calculation, never counted as a
                    check that passed.
                  </p>
                </Panel>
              </div>
            </Section>

            <Section icon={ListChecks} title="Workflow">
              <Panel>
                <div className="grid grid-3" style={{ gap: 0 }}>
                  {data.by_status.map((status) => (
                    <div
                      key={status.status}
                      style={{ padding: '10px 0', display: 'flex', alignItems: 'center', gap: 12 }}
                    >
                      <Pill tone={statusTone(status.status)}>{STATUS_LABEL[status.status]}</Pill>
                      <b className="tnum" style={{ fontSize: 15, fontWeight: 600 }}>
                        {num(status.count)}
                      </b>
                    </div>
                  ))}
                </div>
              </Panel>
            </Section>
          </>
        )}
      </Resource>
    </div>
  );
}

function statusTone(status) {
  if (status === 'AWAITING_REVIEW') return 'mute';
  if (status === 'INSPECTION_COMPLETED' || status === 'NO_ACTION_REQUIRED') return 'ok';
  if (status === 'MARKED_FOR_INSPECTION') return 'warn';
  return 'cool';
}
