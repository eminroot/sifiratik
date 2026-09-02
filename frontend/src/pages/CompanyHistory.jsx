import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Gavel, History, LineChart, MapPin, Table2 } from 'lucide-react';

import { useApi } from '../lib/api.js';
import { LEVEL_TONE, date, levelLabel, positionShort, statusLabel, tonnes } from '../lib/format.js';
import { useT } from '../lib/i18n.jsx';
import HistoryChart from '../components/HistoryChart.jsx';
import { Empty, PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function CompanyHistory() {
  const { companyId } = useParams();
  const t = useT();
  const state = useApi(`/companies/${companyId}/history`);

  return (
    <div className="page">
      <Resource state={state} rows={3}>
        {(data) => {
          const filed = data.periods.filter((row) => row.declared_tonnage !== null);
          const below = data.periods.filter((row) => row.position === 'BELOW').length;

          return (
            <>
              <Link className="back-link" to={`/companies/${companyId}`}>
                <ArrowLeft size={13} strokeWidth={1.9} />
                {data.company.company_name}
              </Link>

              <PageHead
                eyebrow={t('history.eyebrow')}
                icon={History}
                title={t('history.title')}
              >
                <div className="page-head-figures">
                  <div className="head-figure">
                    <span className="label">{t('history.periodsFiled')}</span>
                    <b className="tnum">
                      {filed.length}/{data.periods.length}
                    </b>
                  </div>
                  <div className="head-figure">
                    <span className="label">{t('history.belowRange')}</span>
                    <b className="tnum">{below}</b>
                  </div>
                </div>
              </PageHead>

              <Section icon={LineChart} title={t('history.declaredAgainst')} first>
                <Panel>
                  <HistoryChart rows={data.periods} />
                </Panel>
              </Section>

              <Section icon={Table2} title={t('history.periodByPeriod')}>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('common.period')}</th>
                        <th>{t('common.production')}</th>
                        <th>{t('common.imports')}</th>
                        <th>{t('common.declared')}</th>
                        <th>{t('history.expectedRange')}</th>
                        <th>{t('history.position')}</th>
                        <th>{t('common.priority')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...data.periods].reverse().map((row) => (
                        <tr key={row.period}>
                          <td className="lead mono">{row.period}</td>
                          <td className="num">{tonnes(row.production_volume)}</td>
                          <td className="num">
                            {row.import_volume === null ? (
                              <span className="faint">--</span>
                            ) : (
                              tonnes(row.import_volume)
                            )}
                          </td>
                          <td className="num">
                            {row.declared_tonnage === null ? (
                              <Pill tone="stop">{tonnes(null)}</Pill>
                            ) : (
                              tonnes(row.declared_tonnage)
                            )}
                          </td>
                          <td className="num">
                            {row.expected_lower === null
                              ? '--'
                              : t('common.range', {
                                  from: tonnes(row.expected_lower, { unit: false }),
                                  to: tonnes(row.expected_upper),
                                })}
                          </td>
                          <td>
                            <Pill
                              tone={
                                row.position === 'BELOW'
                                  ? 'stop'
                                  : row.position === 'ABOVE'
                                    ? 'warn'
                                    : 'ok'
                              }
                            >
                              {positionShort(row.position)}
                            </Pill>
                          </td>
                          <td>
                            {row.priority_score === null ? (
                              '--'
                            ) : (
                              <span className="score-cell">
                                <b>{row.priority_score.toFixed(0)}</b>
                                <Pill tone={LEVEL_TONE[row.priority_level]}>
                                  {levelLabel(row.priority_level)}
                                </Pill>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>

              <div className="grid grid-side" style={{ marginTop: 42 }}>
                <div>
                  <div className="section-head">
                    <h2 className="section-title">
                      <Gavel size={15} strokeWidth={1.9} />
                      {t('history.decisions')}
                    </h2>
                  </div>
                  {data.decisions.length === 0 ? (
                    <Empty
                      icon={Gavel}
                      title={t('history.noDecisionTitle')}
                      note={t('history.noDecisionNote')}
                    />
                  ) : (
                    <Panel>
                      <div className="steps">
                        {data.decisions.map((decision) => (
                          <div className="step done" key={decision.decision_id ?? decision.created_at}>
                            <span className="step-index">
                              {decision.new_status === 'INSPECTION_COMPLETED' ? '✓' : '·'}
                            </span>
                            <div className="step-body">
                              <div className="step-name">
                                {decision.new_status
                                  ? statusLabel(decision.new_status)
                                  : decision.action}
                              </div>
                              <div className="step-detail">
                                {decision.previous_status &&
                                  t('history.from', {
                                    status: statusLabel(
                                      decision.previous_status,
                                    ).toLocaleLowerCase(),
                                  })}
                                {decision.user_id} · {date(decision.created_at, { time: true })}
                              </div>
                              {decision.notes && <p className="event-note">{decision.notes}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  )}
                </div>

                <div>
                  <div className="section-head">
                    <h2 className="section-title">
                      <MapPin size={15} strokeWidth={1.9} />
                      {t('company.siteVisits')}
                    </h2>
                  </div>
                  {data.observations.length === 0 ? (
                    <Empty
                      icon={MapPin}
                      title={t('history.noVisitTitle')}
                      note={t('history.noVisitNote')}
                    />
                  ) : (
                    <Panel>
                      <div className="steps">
                        {[...data.observations].reverse().map((observation) => (
                          <div className="step done" key={observation.period}>
                            <span className="step-index mono">{observation.period.slice(-2)}</span>
                            <div className="step-body">
                              <div className="step-name">
                                {t('company.measured', {
                                  amount: tonnes(observation.observed_packaging_tonnage),
                                })}
                              </div>
                              <div className="step-detail">
                                {observation.observation} {observation.inspector},{' '}
                                {date(observation.observed_at)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  )}
                </div>
              </div>

            </>
          );
        }}
      </Resource>
    </div>
  );
}
