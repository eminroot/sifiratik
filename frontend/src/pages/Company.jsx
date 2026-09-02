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
  FIELD_STATE_TONE,
  materialLabel,
  STATUS_TONE,
  confidenceLabel,
  date,
  fieldLabel,
  fieldStateLabel,
  num,
  percent,
  registryLabel,
  relativeDays,
  sectorLabel,
  sizeLabel,
  statusLabel,
  tonnes,
} from '../lib/format.js';
import { useT } from '../lib/i18n.jsx';
import { RangeBar, ScoreBlock } from '../components/Score.jsx';
import { ReasonList, SignalGrid } from '../components/Signals.jsx';
import ReviewSheet from '../components/ReviewSheet.jsx';
import { Empty, PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function Company() {
  const { companyId } = useParams();
  const { period, toast } = useApp();
  const t = useT();
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
                {t('company.backToQueue')}
              </Link>

              <PageHead
                eyebrow={t('company.rank', {
                  rank: num(data.rank),
                  total: num(data.total_ranked),
                })}
                icon={Building2}
                title={company.company_name}
                lede={`${sectorLabel(company.sector)} · ${company.region} · ${sizeLabel(company.company_size)} · ${company.tax_identifier}`}
                note={
                  <>
                    <Pill tone={STATUS_TONE[data.review_status]}>
                      {statusLabel(data.review_status)}
                    </Pill>
                    {company.registry_status !== 'MATCHED' && (
                      <Pill tone="stop">{registryLabel(company.registry_status)}</Pill>
                    )}
                  </>
                }
              >
                <Link className="btn btn-ghost" to={`/companies/${companyId}/history`}>
                  <History size={15} strokeWidth={1.9} />
                  {t('company.history')}
                </Link>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setSheetOpen(true)}
                >
                  <Gavel size={15} strokeWidth={1.9} />
                  {t('company.record')}
                </button>
              </PageHead>

              {!score ? (
                <Empty
                  icon={FileSearch}
                  title={t('company.noResultTitle', { period })}
                  note={t('company.noResultNote')}
                />
              ) : (
                <>
                  <div className="grid grid-side">
                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 20 }}>
                        <span className="stat-chip">
                          <Scale size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">{t('company.priority')}</span>
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
                        <span className="label">{t('company.result')}</span>
                      </div>
                      <dl className="facts">
                        <div>
                          <dt>{t('company.evidenceBase')}</dt>
                          <dd>{confidenceLabel(score.confidence)}</dd>
                        </div>
                        <div>
                          <dt>{t('company.checksRan')}</dt>
                          <dd>
                            {score.signals.length - score.unavailable_signals} {t('common.of')}{' '}
                            {score.signals.length}
                          </dd>
                        </div>
                        <div>
                          <dt>{t('company.checksFiring')}</dt>
                          <dd>{score.active_signals}</dd>
                        </div>
                        <div>
                          <dt>{t('company.scoredAt')}</dt>
                          <dd>{date(score.created_at, { time: true })}</dd>
                        </div>
                        <div>
                          <dt>{t('company.engine')}</dt>
                          <dd className="mono">{score.model_version}</dd>
                        </div>
                        <div>
                          <dt>{t('company.policy')}</dt>
                          <dd className="mono">{score.policy_version}</dd>
                        </div>
                      </dl>
                    </Panel>
                  </div>

                  <Section icon={Factory} title={t('company.declarationFor', { period: score.period })}>
                    <div className="grid grid-wide">
                      <Panel>
                        <dl className="facts">
                          <div>
                            <dt>{t('common.production')}</dt>
                            <dd>{tonnes(data.current_period?.production_volume)}</dd>
                          </div>
                          <div>
                            <dt>{t('common.imports')}</dt>
                            <dd>
                              {data.current_period?.import_volume === null ||
                              data.current_period?.import_volume === undefined ? (
                                <span className="faint">{t('common.notReported')}</span>
                              ) : (
                                tonnes(data.current_period.import_volume)
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>{t('company.exports')}</dt>
                            <dd>{tonnes(data.current_period?.export_volume)}</dd>
                          </div>
                          <div>
                            <dt>{t('company.packagingDeclared')}</dt>
                            <dd>
                              {data.current_period?.declared_tonnage === null ? (
                                <Pill tone="stop">{tonnes(null)}</Pill>
                              ) : (
                                tonnes(data.current_period?.declared_tonnage)
                              )}
                            </dd>
                          </div>
                        </dl>

                        {data.material_breakdown && (
                          <>
                            <div className="divider" />
                            <span className="label">{t('company.materialSplit')}</span>
                            <dl className="facts" style={{ marginTop: 10 }}>
                              {Object.entries(data.material_breakdown).map(([key, value]) => (
                                <div key={key}>
                                  <dt>{materialLabel(key)}</dt>
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
                          <span className="label">{t('company.declaredAgainst')}</span>
                        </div>
                        <RangeBar expected={score.expected} />
                      </Panel>
                    </div>
                  </Section>

                  <Section icon={FileSearch} title={t('company.whyPrioritised')}>
                    <ReasonList signals={score.signals} />
                  </Section>

                  <Section icon={Layers} title={t('company.allChecks')}>
                    <SignalGrid signals={score.signals} />
                  </Section>
                </>
              )}

              <Section icon={Database} title={t('company.evidenceHeld')}>
                <div className="grid grid-side">
                  <Panel>
                    <span className="label">
                      {t('company.dataQuality', { percent: percent(quality.score) })}
                    </span>
                    <div className="bar" style={{ margin: '12px 0 18px' }}>
                      <i style={{ width: `${quality.score}%` }} />
                    </div>
                    <dl className="facts">
                      {Object.entries(quality.fields).map(([key, value]) => (
                        <div key={key}>
                          <dt>{fieldLabel(key)}</dt>
                          <dd>
                            <Pill tone={FIELD_STATE_TONE[value]}>{fieldStateLabel(value)}</Pill>
                          </dd>
                        </div>
                      ))}
                    </dl>
                    <p className="stat-note" style={{ marginTop: 14 }}>
                      {t('company.lastUpdated', { when: relativeDays(quality.freshness_days) })}
                      {quality.missing_fields.length > 0 &&
                        t('company.missingFields', {
                          fields: quality.missing_fields
                            .map((key) => fieldLabel(key).toLocaleLowerCase())
                            .join(', '),
                        })}
                    </p>
                  </Panel>

                  <div className="stack">
                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 14 }}>
                        <span className="stat-chip">
                          <Users size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">{t('company.peerGroup')}</span>
                      </div>
                      <dl className="facts">
                        <div>
                          <dt>{t('company.cohort')}</dt>
                          <dd>
                            {sectorLabel(peers.sector)},{' '}
                            {sizeLabel(peers.company_size).toLocaleLowerCase()}
                          </dd>
                        </div>
                        <div>
                          <dt>{t('company.companiesFiled')}</dt>
                          <dd>{peers.member_count}</dd>
                        </div>
                        <div>
                          <dt>{t('company.thisCompany')}</dt>
                          <dd>
                            {peers.company_intensity_kg_per_tonne === null
                              ? '--'
                              : `${num(peers.company_intensity_kg_per_tonne, 1)} kg/t`}
                          </dd>
                        </div>
                        <div>
                          <dt>{t('company.cohortMedian')}</dt>
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
                        <span className="label">{t('company.siteVisits')}</span>
                      </div>
                      {data.observations.length === 0 ? (
                        <p className="stat-note" style={{ marginTop: 0 }}>
                          {t('company.noVisit')}
                        </p>
                      ) : (
                        <div className="steps">
                          {data.observations.map((observation) => (
                            <div className="step done" key={observation.period}>
                              <span className="step-index">{observation.period.slice(-2)}</span>
                              <div className="step-body">
                                <div className="step-name">
                                  {t('company.measuredOnSite', {
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
                      )}
                    </Panel>
                  </div>
                </div>
              </Section>

              {data.gtip_lines.length > 0 && (
                <Section icon={ListTree} title={t('company.customsLines')}>
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>{t('company.gtip')}</th>
                          <th>{t('company.description')}</th>
                          <th>{t('company.quantity')}</th>
                          <th>{t('company.packagingPerTonne')}</th>
                          <th>{t('company.impliedPackaging')}</th>
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
                  toast(
                    t('company.recordedAs', {
                      status: statusLabel(review.status).toLocaleLowerCase(),
                    }),
                  );
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
