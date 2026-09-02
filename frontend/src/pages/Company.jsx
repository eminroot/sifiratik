import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  Database,
  Factory,
  FileSearch,
  Gavel,
  History,
  Layers,
  ListTree,
  MapPin,
  Scale,
  Users,
} from 'lucide-react';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import {
  CONFIDENCE_LABEL,
  FIELD_STATE_LABEL,
  FIELD_STATE_TONE,
  REGISTRY_LABEL,
  SIZE_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  date,
  num,
  percent,
  relativeDays,
  tonnes,
} from '../lib/format.js';
import { RangeBar, ScoreBlock } from '../components/Score.jsx';
import { ReasonList, SignalGrid } from '../components/Signals.jsx';
import ReviewSheet from '../components/ReviewSheet.jsx';
import { Empty, PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function Company() {
  const { companyId } = useParams();
  const { period, toast } = useApp();
  const state = useApi(`/companies/${companyId}${query({ period })}`, [period]);
  const policy = useApi('/scoring/policy');
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <div className="page">
      <Resource state={state} rows={4}>
        {(data) => {
          const { company, score, quality, peers } = data;
          return (
            <>
              <Link className="back-link" to="/queue">
                <ArrowLeft size={13} strokeWidth={1.9} />
                Inspection queue
              </Link>

              <PageHead
                eyebrow={`Rank ${data.rank} of ${num(data.total_ranked)}`}
                icon={Building2}
                title={company.company_name}
                lede={`${company.sector_label} · ${company.region} · ${SIZE_LABEL[company.company_size]} · ${company.tax_identifier}`}
                note={
                  <>
                    <Pill tone={STATUS_TONE[data.review_status]}>
                      {STATUS_LABEL[data.review_status]}
                    </Pill>
                    {company.registry_status !== 'MATCHED' && (
                      <Pill tone="stop">{REGISTRY_LABEL[company.registry_status]}</Pill>
                    )}
                  </>
                }
              >
                <Link className="btn btn-ghost" to={`/companies/${companyId}/history`}>
                  <History size={15} strokeWidth={1.9} />
                  History
                </Link>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setSheetOpen(true)}
                >
                  <Gavel size={15} strokeWidth={1.9} />
                  Record decision
                </button>
              </PageHead>

              {!score ? (
                <Empty
                  icon={FileSearch}
                  title={`No result for ${period}`}
                  note="The company has no scored record in this period. Pick another period from the header."
                />
              ) : (
                <>
                  <div className="grid grid-side">
                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 20 }}>
                        <span className="stat-chip">
                          <Scale size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">Inspection priority</span>
                      </div>
                      <ScoreBlock
                        score={score.priority_score}
                        level={score.priority_level}
                        bands={policy.data?.bands}
                        confidence={score.confidence}
                        coverage={score.signal_coverage}
                        quality={score.data_quality_score}
                      />
                    </Panel>

                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 16 }}>
                        <span className="stat-chip">
                          <Layers size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">Result</span>
                      </div>
                      <dl className="facts">
                        <div>
                          <dt>Evidence base</dt>
                          <dd>{CONFIDENCE_LABEL[score.confidence]}</dd>
                        </div>
                        <div>
                          <dt>Checks that ran</dt>
                          <dd>
                            {score.signals.length - score.unavailable_signals} of{' '}
                            {score.signals.length}
                          </dd>
                        </div>
                        <div>
                          <dt>Checks firing</dt>
                          <dd>{score.active_signals}</dd>
                        </div>
                        <div>
                          <dt>Scored</dt>
                          <dd>{date(score.created_at, { time: true })}</dd>
                        </div>
                        <div>
                          <dt>Engine</dt>
                          <dd className="mono">{score.model_version}</dd>
                        </div>
                        <div>
                          <dt>Policy</dt>
                          <dd className="mono">{score.policy_version}</dd>
                        </div>
                      </dl>
                    </Panel>
                  </div>

                  <Section icon={Factory} title={`Declaration for ${score.period}`}>
                    <div className="grid grid-wide">
                      <Panel>
                        <dl className="facts">
                          <div>
                            <dt>Production</dt>
                            <dd>{tonnes(data.current_period?.production_volume)}</dd>
                          </div>
                          <div>
                            <dt>Imports</dt>
                            <dd>
                              {data.current_period?.import_volume === null ||
                              data.current_period?.import_volume === undefined ? (
                                <span className="faint">Not reported</span>
                              ) : (
                                tonnes(data.current_period.import_volume)
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>Exports</dt>
                            <dd>{tonnes(data.current_period?.export_volume)}</dd>
                          </div>
                          <div>
                            <dt>Packaging declared</dt>
                            <dd>
                              {data.current_period?.declared_tonnage === null ? (
                                <Pill tone="stop">No filing</Pill>
                              ) : (
                                tonnes(data.current_period?.declared_tonnage)
                              )}
                            </dd>
                          </div>
                        </dl>

                        {data.material_breakdown && (
                          <>
                            <div className="divider" />
                            <span className="label">Material split as declared</span>
                            <dl className="facts" style={{ marginTop: 10 }}>
                              {Object.entries(data.material_breakdown).map(([key, value]) => (
                                <div key={key}>
                                  <dt style={{ textTransform: 'capitalize' }}>{key}</dt>
                                  <dd>{tonnes(value)}</dd>
                                </div>
                              ))}
                            </dl>
                          </>
                        )}
                      </Panel>

                      <Panel>
                        <div className="stat-head" style={{ marginBottom: 18 }}>
                          <span className="stat-chip">
                            <ListTree size={14} strokeWidth={1.9} />
                          </span>
                          <span className="label">Declared against expected</span>
                        </div>
                        <RangeBar expected={score.expected} />
                      </Panel>
                    </div>
                  </Section>

                  <Section icon={FileSearch} title="Why this company is prioritised">
                    <ReasonList signals={score.signals} />
                  </Section>

                  <Section icon={Layers} title="All eight checks">
                    <SignalGrid signals={score.signals} />
                  </Section>
                </>
              )}

              <Section icon={Database} title="Evidence held on this company">
                <div className="grid grid-side">
                  <Panel>
                    <span className="label">Data quality {percent(quality.score)}</span>
                    <div className="bar" style={{ margin: '12px 0 18px' }}>
                      <i style={{ width: `${quality.score}%` }} />
                    </div>
                    <dl className="facts">
                      {Object.entries(quality.fields).map(([key, value]) => (
                        <div key={key}>
                          <dt>{quality.field_labels[key]}</dt>
                          <dd>
                            <Pill tone={FIELD_STATE_TONE[value]}>{FIELD_STATE_LABEL[value]}</Pill>
                          </dd>
                        </div>
                      ))}
                    </dl>
                    <p className="stat-note" style={{ marginTop: 14 }}>
                      Last updated {relativeDays(quality.freshness_days)}.
                      {quality.missing_fields.length > 0 &&
                        ` Missing: ${quality.missing_fields.join(', ').toLowerCase()}.`}
                    </p>
                  </Panel>

                  <div className="stack">
                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 14 }}>
                        <span className="stat-chip">
                          <Users size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">Peer group</span>
                      </div>
                      <dl className="facts">
                        <div>
                          <dt>Cohort</dt>
                          <dd>
                            {peers.sector}, {SIZE_LABEL[peers.company_size].toLowerCase()}
                          </dd>
                        </div>
                        <div>
                          <dt>Companies that filed</dt>
                          <dd>{peers.member_count}</dd>
                        </div>
                        <div>
                          <dt>This company</dt>
                          <dd>
                            {peers.company_intensity_kg_per_tonne === null
                              ? '--'
                              : `${num(peers.company_intensity_kg_per_tonne, 1)} kg/t`}
                          </dd>
                        </div>
                        <div>
                          <dt>Cohort median</dt>
                          <dd>
                            {peers.median_intensity_kg_per_tonne === null
                              ? '--'
                              : `${num(peers.median_intensity_kg_per_tonne, 1)} kg/t`}
                          </dd>
                        </div>
                      </dl>
                    </Panel>

                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 14 }}>
                        <span className="stat-chip">
                          <MapPin size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">Site visits</span>
                      </div>
                      {data.observations.length === 0 ? (
                        <p className="stat-note" style={{ marginTop: 0 }}>
                          No visit has been recorded, so the field check could not be evaluated.
                        </p>
                      ) : (
                        <div className="steps">
                          {data.observations.map((observation) => (
                            <div className="step done" key={observation.period}>
                              <span className="step-index">{observation.period.slice(-2)}</span>
                              <div className="step-body">
                                <div className="step-name">
                                  {tonnes(observation.observed_packaging_tonnage)} measured on site
                                </div>
                                <div className="step-detail">
                                  {observation.observation} {observation.inspector},{' '}
                                  {date(observation.observed_at)}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </Panel>
                  </div>
                </div>
              </Section>

              {data.gtip_lines.length > 0 && (
                <Section icon={ListTree} title="Customs lines matched to this period">
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>GTIP</th>
                          <th>Description</th>
                          <th>Quantity</th>
                          <th>Packaging per tonne</th>
                          <th>Implied packaging</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.gtip_lines.map((line) => (
                          <tr key={line.gtip_code}>
                            <td className="lead mono">{line.gtip_code}</td>
                            <td>{line.description}</td>
                            <td className="num">{tonnes(line.quantity_tonnes)}</td>
                            <td className="num">
                              {num(line.packaging_coefficient * 1000, 1)} kg
                            </td>
                            <td className="num">
                              {tonnes(line.quantity_tonnes * line.packaging_coefficient)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              )}

              <ReviewSheet
                open={sheetOpen}
                company={company}
                period={period}
                current={data.review_status}
                onClose={() => setSheetOpen(false)}
                onSaved={(review) => {
                  setSheetOpen(false);
                  toast(`Recorded as ${STATUS_LABEL[review.status].toLowerCase()}`);
                  state.reload();
                }}
              />
            </>
          );
        }}
      </Resource>
    </div>
  );
}
