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
  fieldLabel,
  levelLabel,
  lira,
  num,
  percent,
  signalName,
  splitUnit,
  statusLabel,
  tonnes,
} from '../lib/format.js';
import { useT } from '../lib/i18n.jsx';
import { Figures, PageHead, Panel, Pill, Resource, Section, Stat } from '../components/ui.jsx';
import QueueTable from '../components/QueueTable.jsx';

const MIX_TONE = { CRITICAL: 'stop', HIGH: 'warn', MEDIUM: 'mute', LOW: 'ok' };

export default function Overview() {
  const { period, toast } = useApp();
  const t = useT();
  const state = useApi(`/dashboard${query({ period })}`, [period]);
  const [running, setRunning] = useState(false);

  const rerun = async () => {
    setRunning(true);
    try {
      const result = await post('/scoring/run', { period });
      toast(
        t('overview.rescored', {
          count: num(result.companies_scored),
          ms: num(result.duration_ms),
        }),
      );
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
              eyebrow={t('overview.eyebrow', { period: data.period })}
              icon={LayoutGrid}
              title={t('overview.title')}
            >
              <button
                type="button"
                className="btn btn-primary"
                onClick={rerun}
                disabled={running}
              >
                {running ? <span className="spin on-ink" /> : <RefreshCw size={15} strokeWidth={1.9} />}
                {t(running ? 'overview.scoring' : 'overview.rescore')}
              </button>
            </PageHead>

            <div className="stat-grid">
              <div className="panel stat-hero">
                <div className="panel-body">
                  <div className="stat-head">
                    <span className="stat-chip">
                      <Boxes size={15} strokeWidth={1.9} />
                    </span>
                    <span className="label">{t('overview.spread')}</span>
                    <span className="stat-head-action">
                      <Link className="btn btn-quiet btn-sm" to="/queue">
                        {t('overview.openQueue')}
                        <ArrowUpRight size={13} strokeWidth={1.9} />
                      </Link>
                    </span>
                  </div>

                  <div className="stat-value">{num(data.companies_analysed)}</div>
                  <div className="stat-note">
                    {t('overview.scoredAcross', {
                      regions: data.regions_covered,
                      sectors: data.sectors_covered,
                    })}
                  </div>

                  <div className="mix">
                    {data.by_level.map((band) => (
                      <span
                        key={band.level}
                        className={`mix-part ${MIX_TONE[band.level]}`}
                        style={{ flex: Math.max(band.count, 0.4) }}
                        title={`${levelLabel(band.level)}: ${num(band.count)}`}
                      />
                    ))}
                  </div>
                  <ul className="mix-legend">
                    {data.by_level.map((band) => (
                      <li key={band.level}>
                        <i className={MIX_TONE[band.level]} />
                        {levelLabel(band.level)} <b>{num(band.count)}</b>
                        <em>{percent(band.share)}</em>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <Figures rows>
                <Stat
                  icon={ListChecks}
                  label={t('overview.awaiting')}
                  value={num(data.awaiting_review)}
                  note={t('overview.awaitingNote', {
                    progress: num(data.in_progress),
                    closed: num(data.reviewed),
                  })}
                />
                <Stat
                  icon={Database}
                  label={t('overview.noFiling')}
                  value={num(data.companies_without_declaration)}
                  note={t('overview.noFilingNote')}
                  tone={data.companies_without_declaration ? 'warn' : undefined}
                />
              </Figures>
            </div>

            <Section icon={Coins} title={t('overview.exposure')}>
              <Figures columns={3}>
                <Stat
                  icon={Boxes}
                  label={t('overview.tonnageIdentified')}
                  {...splitUnit(tonnes(data.additional_tonnage_identified))}
                  note={t('overview.tonnageIdentifiedNote')}
                />
                <Stat
                  icon={Coins}
                  label={t('overview.atStake')}
                  {...splitUnit(lira(data.estimated_gekap_gap_try))}
                  note={t('overview.atStakeNote')}
                />
                <Stat
                  icon={Crosshair}
                  label={t('overview.concentration')}
                  {...splitUnit(percent(data.exposure_share_in_top_50))}
                  note={t('overview.concentrationNote', {
                    value: lira(data.exposure_in_top_50_try),
                  })}
                />
              </Figures>
            </Section>

            <Section
              icon={ListChecks}
              title={t('overview.queue')}
              actions={
                <Link className="btn btn-ghost btn-sm" to="/queue">
                  {t('overview.allCompanies', { count: num(data.companies_analysed) })}
                  <ArrowUpRight size={13} strokeWidth={1.9} />
                </Link>
              }
            >
              <QueueTable items={data.priority_queue} compact />
            </Section>

            <Section icon={Gauge} title={t('overview.coverage')}>
              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 14 }}>
                    <span className="stat-chip">
                      <Database size={14} strokeWidth={1.9} />
                    </span>
                    <span className="label">{t('overview.fieldCoverage')}</span>
                    <span className="stat-head-action">
                      <Link className="btn btn-quiet btn-sm" to="/data-quality">
                        {t('common.detail')}
                        <ArrowUpRight size={13} strokeWidth={1.9} />
                      </Link>
                    </span>
                  </div>

                  {data.field_coverage.map((field) => (
                    <div className="coverage-row" key={field.key}>
                      <div className="coverage-name">
                        {fieldLabel(field.key)}
                        <span>
                          {t('overview.coverageBreakdown', {
                            available: num(field.available),
                            partial: num(field.partial),
                            missing: num(field.missing),
                          })}
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
                    <span className="label">{t('overview.signalsEvaluated')}</span>
                  </div>

                  <table className="table" style={{ marginTop: -4 }}>
                    <tbody>
                      {data.signal_availability.map((signal) => (
                        <tr key={signal.code}>
                          <td style={{ padding: '9px 0' }}>
                            <span className="signal-code" style={{ marginRight: 8 }}>
                              {signal.code}
                            </span>
                            {signalName(signal.code)}
                          </td>
                          <td className="num right" style={{ padding: '9px 0', width: 90 }}>
                            {percent(signal.availability_rate)}
                          </td>
                          <td className="right" style={{ padding: '9px 0', width: 74 }}>
                            <Pill tone={signal.active ? 'warn' : 'mute'}>
                              {t('overview.firing', { count: num(signal.active) })}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="figure-note" style={{ marginTop: 14, paddingTop: 0 }}>
                    {t('overview.heldOut')}
                  </p>
                </Panel>
              </div>
            </Section>

            <Section icon={ListChecks} title={t('overview.workflow')}>
              <Panel>
                <div className="grid grid-3" style={{ gap: 0 }}>
                  {data.by_status.map((status) => (
                    <div
                      key={status.status}
                      style={{ padding: '10px 0', display: 'flex', alignItems: 'center', gap: 12 }}
                    >
                      <Pill tone={statusTone(status.status)}>{statusLabel(status.status)}</Pill>
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
