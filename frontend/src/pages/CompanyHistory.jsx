import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Gavel, History, LineChart, MapPin, Table2 } from 'lucide-react';

import { useApi } from '../lib/api.js';
import { LEVEL_LABEL, LEVEL_TONE, STATUS_LABEL, date, tonnes } from '../lib/format.js';
import HistoryChart from '../components/HistoryChart.jsx';
import { Empty, PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function CompanyHistory() {
  const { companyId } = useParams();
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
                eyebrow="History"
                icon={History}
                title="Behaviour over time"
                lede={
                  below === 0
                    ? 'Every filed period has landed inside its expected range.'
                    : `${below} of ${data.periods.length} periods fell below the range expected at the time.`
                }
              >
                <div className="page-head-figures">
                  <div className="head-figure">
                    <span className="label">Periods filed</span>
                    <b className="tnum">
                      {filed.length}/{data.periods.length}
                    </b>
                  </div>
                  <div className="head-figure">
                    <span className="label">Below range</span>
                    <b className="tnum">{below}</b>
                  </div>
                </div>
              </PageHead>

              <Section icon={LineChart} title="Declared against expected" first>
                <Panel>
                  <HistoryChart rows={data.periods} />
                </Panel>
              </Section>

              <Section icon={Table2} title="Period by period">
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Production</th>
                        <th>Imports</th>
                        <th>Declared</th>
                        <th>Expected range</th>
                        <th>Position</th>
                        <th>Priority</th>
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
                              <Pill tone="stop">No filing</Pill>
                            ) : (
                              tonnes(row.declared_tonnage)
                            )}
                          </td>
                          <td className="num">
                            {row.expected_lower === null
                              ? '--'
                              : `${tonnes(row.expected_lower, { unit: false })} to ${tonnes(row.expected_upper)}`}
                          </td>
                          <td>
                            {row.position === 'BELOW' ? (
                              <Pill tone="stop">Below</Pill>
                            ) : row.position === 'ABOVE' ? (
                              <Pill tone="warn">Above</Pill>
                            ) : (
                              <Pill tone="ok">Within</Pill>
                            )}
                          </td>
                          <td>
                            {row.priority_score === null ? (
                              '--'
                            ) : (
                              <span className="score-cell">
                                <b>{row.priority_score.toFixed(0)}</b>
                                <Pill tone={LEVEL_TONE[row.priority_level]}>
                                  {LEVEL_LABEL[row.priority_level]}
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
                      Decisions taken
                    </h2>
                  </div>
                  {data.decisions.length === 0 ? (
                    <Empty
                      icon={Gavel}
                      title="No decision recorded yet"
                      note="Nothing has been decided on this company since it entered the queue."
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
                                {STATUS_LABEL[decision.new_status] ?? decision.action}
                              </div>
                              <div className="step-detail">
                                {decision.previous_status && (
                                  <>from {STATUS_LABEL[decision.previous_status].toLowerCase()}, </>
                                )}
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
                      Site visits
                    </h2>
                  </div>
                  {data.observations.length === 0 ? (
                    <Empty
                      icon={MapPin}
                      title="No site visit on record"
                      note="Field evidence is the one input the platform cannot collect on its own."
                    />
                  ) : (
                    <Panel>
                      <div className="steps">
                        {[...data.observations].reverse().map((observation) => (
                          <div className="step done" key={observation.period}>
                            <span className="step-index mono">{observation.period.slice(-2)}</span>
                            <div className="step-body">
                              <div className="step-name">
                                {tonnes(observation.observed_packaging_tonnage)} measured
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
