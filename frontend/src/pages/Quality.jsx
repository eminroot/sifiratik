import { CircleSlash, Database, Gauge, Layers, ScanSearch, ShieldQuestion } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import {
  FIELD_STATE_LABEL,
  LEVEL_LABEL,
  LEVEL_TONE,
  num,
  percent,
  qualityTone,
} from '../lib/format.js';
import { Meter, PageHead, Panel, Pill, Resource, Section, Stat } from '../components/ui.jsx';

const STATE_CLASS = { AVAILABLE: 'ok', PARTIAL: 'warn', MISSING: 'stop' };

const SHORT_FIELD = {
  production: 'Prod',
  import: 'Imp',
  history: 'Hist',
  gtip: 'GTIP',
  field: 'Site',
  registry: 'Reg',
};

const MATRIX_ROWS = 60;

export default function Quality() {
  const { period } = useApp();
  const navigate = useNavigate();
  const state = useApi(`/data-quality${query({ period })}`, [period]);

  return (
    <div className="page wide">
      <Resource state={state} rows={3}>
        {(data) => {
          const fieldKeys = data.field_coverage.map((field) => field.key);

          return (
            <>
              <PageHead
                eyebrow="Evidence"
                icon={Gauge}
                title="What the platform can see"
                lede="A quiet check and a check that never ran are different findings. This page keeps them apart."
              />

              <div className="grid grid-4">
                <Stat
                  icon={Gauge}
                  label="Mean data quality"
                  value={percent(data.average_data_quality)}
                  note={`across ${num(data.companies_analysed)} scored companies`}
                />
                <Stat
                  icon={Database}
                  label="Complete records"
                  value={num(data.fully_evidenced)}
                  note="every field present"
                />
                <Stat
                  icon={ShieldQuestion}
                  label="Thin evidence"
                  value={num(data.thin_evidence)}
                  note="below 50% completeness"
                  tone={data.thin_evidence ? 'warn' : undefined}
                />
                <Stat
                  icon={CircleSlash}
                  label="Checks not run"
                  value={num(
                    data.signal_availability.reduce((sum, signal) => sum + signal.unavailable, 0),
                  )}
                  note="held out of the calculation"
                />
              </div>

              <Section icon={Database} title="Coverage by field">
                <Panel>
                  {data.field_coverage.map((field) => (
                    <div className="coverage-row" key={field.key}>
                      <div className="coverage-name">
                        {field.label}
                        <span>
                          {num(field.available)} available, {num(field.partial)} partial,{' '}
                          {num(field.missing)} missing
                        </span>
                      </div>
                      <div className="coverage-bar">
                        <i
                          className="ok"
                          style={{ width: `${(field.available / data.companies_analysed) * 100}%` }}
                        />
                        <i
                          className="warn"
                          style={{ width: `${(field.partial / data.companies_analysed) * 100}%` }}
                        />
                        <i
                          className="stop"
                          style={{ width: `${(field.missing / data.companies_analysed) * 100}%` }}
                        />
                      </div>
                      <div className="coverage-value tnum">{percent(field.coverage)}</div>
                    </div>
                  ))}
                </Panel>
              </Section>

              <Section icon={Layers} title="Why checks could not run">
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Check</th>
                        <th>Evaluated</th>
                        <th>Not run</th>
                        <th>Firing</th>
                        <th>Most common reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.signal_availability.map((signal) => (
                        <tr key={signal.code}>
                          <td className="lead">
                            <span className="signal-code" style={{ marginRight: 8 }}>
                              {signal.code}
                            </span>
                            {signal.name}
                          </td>
                          <td className="num">
                            <span className="score-cell">
                              {percent(signal.availability_rate)}
                              <Meter
                                value={signal.availability_rate}
                                tone={qualityTone(signal.availability_rate)}
                              />
                            </span>
                          </td>
                          <td className="num">{num(signal.unavailable)}</td>
                          <td className="num">{num(signal.active)}</td>
                          <td className="prose-cell" style={{ maxWidth: 400 }}>
                            {signal.top_reason ?? (
                              <span className="faint">Ran for every company</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>

              <Section
                icon={ScanSearch}
                title="Weakest records first"
                actions={
                  <span className="stat-note" style={{ marginTop: 0 }}>
                    {Math.min(MATRIX_ROWS, data.companies.length)} of {num(data.companies_analysed)}{' '}
                    shown, weakest first
                  </span>
                }
              >
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>Quality</th>
                        {data.field_coverage.map((field) => (
                          <th key={field.key} style={{ width: 40, textAlign: 'center' }}>
                            {SHORT_FIELD[field.key]}
                          </th>
                        ))}
                        <th>Checks not run</th>
                        <th>Priority</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.companies.slice(0, MATRIX_ROWS).map((company) => (
                        <tr
                          key={company.company_id}
                          className="clickable"
                          onClick={() => navigate(`/companies/${company.company_id}`)}
                        >
                          <td className="lead">
                            <span className="cell-name">
                              {company.company_name}
                              <em>
                                {company.sector_label} · {company.region}
                              </em>
                            </span>
                          </td>
                          <td className="num">
                            <span className="score-cell">
                              {company.quality_score.toFixed(0)}%
                              <Meter
                                value={company.quality_score}
                                tone={qualityTone(company.quality_score)}
                              />
                            </span>
                          </td>
                          {fieldKeys.map((key) => (
                            <td key={key} style={{ textAlign: 'center' }}>
                              <span
                                className={`dot ${STATE_CLASS[company.fields[key]]}`}
                                title={`${data.field_labels[key]}: ${FIELD_STATE_LABEL[company.fields[key]]}`}
                              />
                            </td>
                          ))}
                          <td className="num">{company.unavailable_signals}</td>
                          <td>
                            <Pill tone={LEVEL_TONE[company.priority_level]}>
                              {LEVEL_LABEL[company.priority_level]}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="pager">
                  <span className="dot-row">
                    <span className="dot ok" /> Available
                    <span className="dot warn" style={{ marginLeft: 12 }} /> Partial
                    <span className="dot stop" style={{ marginLeft: 12 }} /> Missing
                  </span>
                  <span>Columns follow the order of the coverage list above.</span>
                </div>
              </Section>
            </>
          );
        }}
      </Resource>
    </div>
  );
}
