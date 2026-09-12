import { Link } from 'react-router-dom';
import {
  Boxes,
  Building,
  CircleDollarSign,
  Cloud,
  HandCoins,
  Leaf,
  Map,
  Recycle,
  Target,
  Users,
} from 'lucide-react';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import { lira, materialLabel, num, splitUnit, tonnes } from '../lib/format.js';
import { useI18n } from '../lib/i18n.jsx';
import { Figures, PageHead, Panel, Resource, Section, Stat } from '../components/ui.jsx';

export default function Impact() {
  const { period } = useApp();
  const { lang, t } = useI18n();
  // Step labels and notes are prose the API writes, so the language goes with
  // the request rather than into a lookup here.
  const state = useApi(`/climate-impact${query({ period, lang })}`, [period, lang]);

  return (
    <div className="page">
      <Resource state={state} rows={3}>
        {(data) => {
          const maxRegion = Math.max(...data.by_region.map((row) => row.value), 1);
          const maxMaterial = Math.max(...data.by_material.map((row) => row.tonnes), 1);

          return (
            <>
              <PageHead eyebrow={t('impact.eyebrow')} icon={Leaf} title={t('impact.title')}>
                <Link className="btn btn-ghost" to="/pilot">
                  <Target size={15} strokeWidth={1.9} />
                  {t('impact.pilotLink')}
                </Link>
              </PageHead>

              <Figures columns={4}>
                <Stat
                  icon={Boxes}
                  label={t('impact.identified')}
                  {...splitUnit(tonnes(data.additional_tonnage_identified))}
                  note={t('impact.identifiedNote', { count: num(data.companies_flagged) })}
                />
                <Stat
                  icon={Recycle}
                  label={t('impact.confirmed')}
                  {...splitUnit(tonnes(data.additional_tonnage_confirmed))}
                  note={t('impact.confirmedNote', { count: num(data.companies_inspected) })}
                />
                <Stat
                  icon={CircleDollarSign}
                  label={t('impact.recovered')}
                  {...splitUnit(lira(data.confirmed_gekap_revenue_try))}
                  note={t('impact.recoveredNote', {
                    value: lira(data.estimated_gekap_revenue_try),
                  })}
                />
                <Stat
                  icon={Cloud}
                  label={t('impact.emissions')}
                  value={tonnes(data.co2e_avoided_tonnes, { unit: false })}
                  unit="t CO2e"
                  note={t('impact.emissionsNote')}
                />
              </Figures>

              <Section icon={Recycle} title={t('impact.chain')}>
                <div className="grid grid-side">
                  <Panel>
                    <div className="chain">
                      {data.impact_chain.map((step, index) => (
                        <div
                          className={`chain-step${index === data.impact_chain.length - 1 ? ' lead' : ''}`}
                          key={step.key}
                        >
                          <div className="chain-head">
                            <span className="chain-label">{step.label}</span>
                            <span className="chain-value tnum">
                              {/* Every unit but a headcount is a tonnage, CO2e
                                  included, so it keeps its decimal below 100
                                  instead of rounding a real figure to zero. */}
                              {step.unit === 'companies'
                                ? num(step.value)
                                : step.unit === 'tonnes'
                                  ? tonnes(step.value)
                                  : `${tonnes(step.value, { unit: false })} ${step.unit}`}
                            </span>
                          </div>
                          {step.note && <div className="chain-note">{step.note}</div>}
                        </div>
                      ))}
                    </div>
                  </Panel>

                  <div className="stack">
                    <Panel>
                      <div className="stat-head" style={{ marginBottom: 14 }}>
                        <span className="stat-chip">
                          <Map size={14} strokeWidth={1.9} />
                        </span>
                        <span className="label">{t('impact.byProvince')}</span>
                      </div>
                      {data.by_region.map((row) => (
                        <div className="coverage-row" key={row.key}>
                          <div className="coverage-name">{row.label}</div>
                          <div className="coverage-bar">
                            <i className="ok" style={{ width: `${(row.value / maxRegion) * 100}%` }} />
                          </div>
                          <div className="coverage-value tnum">
                            {tonnes(row.value, { unit: false })}
                          </div>
                        </div>
                      ))}
                    </Panel>

                    <Panel>
                      <dl className="facts">
                        <div>
                          <dt>{t('impact.provincesCovered')}</dt>
                          <dd>{data.cities_covered}</dd>
                        </div>
                        <div>
                          <dt>{t('impact.sectorsCovered')}</dt>
                          <dd>{data.sectors_covered}</dd>
                        </div>
                        <div>
                          <dt>{t('impact.recordsCorrected')}</dt>
                          <dd>{num(data.records_updated)}</dd>
                        </div>
                      </dl>
                    </Panel>
                  </div>
                </div>
              </Section>

              <Section icon={Boxes} title={t('impact.byMaterial')}>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('common.material')}</th>
                        <th>{t('impact.share')}</th>
                        <th>{t('common.tonnage')}</th>
                        <th>{t('impact.contributionAtTariff')}</th>
                        <th>{t('impact.co2eAvoided')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_material.map((row) => (
                        <tr key={row.key}>
                          <td className="lead">{materialLabel(row.key)}</td>
                          <td style={{ width: 200 }}>
                            <div className="coverage-bar">
                              <i
                                className="ok"
                                style={{ width: `${(row.tonnes / maxMaterial) * 100}%` }}
                              />
                            </div>
                          </td>
                          <td className="num">{tonnes(row.tonnes)}</td>
                          <td className="num">
                            {row.priced_by_weight ? (
                              lira(row.gekap_value_try)
                            ) : (
                              <span title={t('impact.notPricedByWeightNote')}>
                                {t('impact.notPricedByWeight')}
                              </span>
                            )}
                          </td>
                          <td className="num">{tonnes(row.co2e_avoided_tonnes)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {data.by_material.some((row) => !row.priced_by_weight) && (
                  <p className="note">{t('impact.notPricedByWeightNote')}</p>
                )}
              </Section>

              <Section icon={Users} title={t('impact.collectors')}>
                <div className="grid grid-side">
                  <Panel>
                    <p className="page-lede" style={{ marginTop: 0, maxWidth: '58ch' }}>
                      {t('impact.collectorsNote')}
                    </p>

                    <div className="divider" />

                    <div className="grid grid-3" style={{ gap: 20 }}>
                      <div>
                        <span className="label">{t('impact.collectorsSupported')}</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.collectors_supported)}
                        </div>
                      </div>
                      <div>
                        <span className="label">{t('impact.movedToFormal')}</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.formal_transitions)}
                        </div>
                      </div>
                      <div>
                        <span className="label">{t('impact.insuredDays')}</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.insured_days)}
                        </div>
                      </div>
                    </div>
                  </Panel>

                  <div className="stack">
                    <Stat
                      icon={HandCoins}
                      label={t('impact.funding')}
                      value={lira(data.social.funding_allocated_try)}
                      note={t('impact.fundingNote', { count: num(data.social.municipalities) })}
                    />
                    <Stat
                      icon={Building}
                      label={t('impact.fromClosed')}
                      value={lira(data.social.funding_available_try)}
                      note={t('impact.fromClosedNote', {
                        years: num(data.social.worker_years_funded, 1),
                        cost: lira(data.social.cost_per_transition_try),
                      })}
                    />
                    <Stat
                      icon={Recycle}
                      label={t('impact.ifClosed')}
                      value={lira(data.social.funding_potential_try)}
                      note={t('impact.ifClosedNote', {
                        years: num(data.social.worker_years_potential, 1),
                      })}
                      tone="warn"
                    />
                  </div>
                </div>
              </Section>
            </>
          );
        }}
      </Resource>
    </div>
  );
}
