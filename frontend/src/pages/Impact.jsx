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
import { lira, num, splitUnit, tonnes } from '../lib/format.js';
import { Figures, PageHead, Panel, Resource, Section, Stat } from '../components/ui.jsx';

export default function Impact() {
  const { period } = useApp();
  const state = useApi(`/climate-impact${query({ period })}`, [period]);

  return (
    <div className="page">
      <Resource state={state} rows={3}>
        {(data) => {
          const maxRegion = Math.max(...data.by_region.map((row) => row.value), 1);
          const maxMaterial = Math.max(...data.by_material.map((row) => row.tonnes), 1);

          return (
            <>
              <PageHead eyebrow="COP31" icon={Leaf} title="Climate impact">
                <Link className="btn btn-ghost" to="/pilot">
                  <Target size={15} strokeWidth={1.9} />
                  Antalya pilot
                </Link>
              </PageHead>

              <Figures columns={4}>
                <Stat
                  icon={Boxes}
                  label="Identified"
                  {...splitUnit(tonnes(data.additional_tonnage_identified))}
                  note={`across ${num(data.companies_flagged)} flagged companies`}
                />
                <Stat
                  icon={Recycle}
                  label="Confirmed by inspection"
                  {...splitUnit(tonnes(data.additional_tonnage_confirmed))}
                  note={`${num(data.companies_inspected)} inspections closed`}
                />
                <Stat
                  icon={CircleDollarSign}
                  label="Contribution recovered"
                  {...splitUnit(lira(data.confirmed_gekap_revenue_try))}
                  note={`${lira(data.estimated_gekap_revenue_try)} identified but not yet confirmed`}
                />
                <Stat
                  icon={Cloud}
                  label="Emissions avoided"
                  value={num(data.co2e_avoided_tonnes)}
                  unit="t CO2e"
                  note="against disposal of the same material"
                />
              </Figures>

              <Section icon={Recycle} title="Impact chain">
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
                              {step.unit === 'companies'
                                ? num(step.value)
                                : step.unit === 'tonnes'
                                  ? tonnes(step.value)
                                  : `${num(step.value)} ${step.unit}`}
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
                        <span className="label">Identified tonnage by province</span>
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
                          <dt>Provinces covered</dt>
                          <dd>{data.cities_covered}</dd>
                        </div>
                        <div>
                          <dt>Sectors covered</dt>
                          <dd>{data.sectors_covered}</dd>
                        </div>
                        <div>
                          <dt>Records corrected after inspection</dt>
                          <dd>{num(data.records_updated)}</dd>
                        </div>
                      </dl>
                    </Panel>
                  </div>
                </div>
              </Section>

              <Section icon={Boxes} title="By material">
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Material</th>
                        <th>Share</th>
                        <th>Tonnage</th>
                        <th>Contribution at the 2026 tariff</th>
                        <th>CO2e avoided</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_material.map((row) => (
                        <tr key={row.key}>
                          <td className="lead">{row.name}</td>
                          <td style={{ width: 200 }}>
                            <div className="coverage-bar">
                              <i
                                className="ok"
                                style={{ width: `${(row.tonnes / maxMaterial) * 100}%` }}
                              />
                            </div>
                          </td>
                          <td className="num">{tonnes(row.tonnes)}</td>
                          <td className="num">{lira(row.gekap_value_try)}</td>
                          <td className="num">{num(row.co2e_avoided_tonnes)} t</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>

              <Section icon={Users} title="Collector formalisation">
                <div className="grid grid-side">
                  <Panel>
                    <p className="page-lede" style={{ marginTop: 0, maxWidth: '58ch' }}>
                      A share of the contribution recovered through inspection funds the move of
                      informal collectors into insured work. Better field coverage then feeds the
                      next round of inspections.
                    </p>

                    <div className="divider" />

                    <div className="grid grid-3" style={{ gap: 20 }}>
                      <div>
                        <span className="label">Collectors supported</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.collectors_supported)}
                        </div>
                      </div>
                      <div>
                        <span className="label">Moved to formal work</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.formal_transitions)}
                        </div>
                      </div>
                      <div>
                        <span className="label">Insured working days</span>
                        <div className="stat-value sm" style={{ marginTop: 10 }}>
                          {num(data.social.insured_days)}
                        </div>
                      </div>
                    </div>
                  </Panel>

                  <div className="stack">
                    <Stat
                      icon={HandCoins}
                      label="Programme funding"
                      value={lira(data.social.funding_allocated_try)}
                      note={`allocated across ${num(data.social.municipalities)} districts`}
                    />
                    <Stat
                      icon={Building}
                      label="From closed inspections"
                      value={lira(data.social.funding_available_try)}
                      note={`${num(data.social.worker_years_funded, 1)} insured worker years at ${lira(data.social.cost_per_transition_try)} each`}
                    />
                    <Stat
                      icon={Recycle}
                      label="If the open cases close"
                      value={lira(data.social.funding_potential_try)}
                      note={`a further ${num(data.social.worker_years_potential, 1)} worker years, not yet recovered`}
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
