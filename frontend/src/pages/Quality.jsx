import { CircleSlash, Database, Gauge, Layers, ScanSearch, ShieldQuestion } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import {
  LEVEL_TONE,
  fieldLabel,
  fieldShort,
  fieldStateLabel,
  levelLabel,
  num,
  percent,
  qualityTone,
  sectorLabel,
  signalName,
  splitUnit,
} from '../lib/format.js';
import { useT } from '../lib/i18n.jsx';
import { Figures, Meter, PageHead, Panel, Pill, Resource, Section, Stat } from '../components/ui.jsx';

const STATE_CLASS = { AVAILABLE: 'ok', PARTIAL: 'warn', MISSING: 'stop' };

const MATRIX_ROWS = 60;

export default function Quality() {
  const { period } = useApp();
  const t = useT();
  const navigate = useNavigate();
  const state = useApi(`/data-quality${query({ period })}`, [period]);

  return (
    <div className="page wide">
      <Resource state={state} rows={3}>
        {(data) => {
          const fieldKeys = data.field_coverage.map((field) => field.key);

          return (
            <>
              <PageHead eyebrow={t('quality.eyebrow')} icon={Gauge} title={t('quality.title')} />

              <Figures columns={4}>
                <Stat
                  icon={Gauge}
                  label={t('quality.mean')}
                  {...splitUnit(percent(data.average_data_quality))}
                  note={t('quality.meanNote', { count: num(data.companies_analysed) })}
                />
                <Stat
                  icon={Database}
                  label={t('quality.complete')}
                  value={num(data.fully_evidenced)}
                  note={t('quality.completeNote')}
                />
                <Stat
                  icon={ShieldQuestion}
                  label={t('quality.thin')}
                  value={num(data.thin_evidence)}
                  note={t('quality.thinNote')}
                  tone={data.thin_evidence ? 'warn' : undefined}
                />
                <Stat
                  icon={CircleSlash}
                  label={t('quality.notRun')}
                  value={num(
                    data.signal_availability.reduce((sum, signal) => sum + signal.unavailable, 0),
                  )}
                  note={t('quality.notRunNote')}
                />
              </Figures>

              <Section icon={Database} title={t('quality.byField')}>
                <Panel>
                  {data.field_coverage.map((field) => (
                    <div className="coverage-row" key={field.key}>
                      <div className="coverage-name">
                        {fieldLabel(field.key)}
                        <span>
                          {t('quality.fieldBreakdown', {
                            available: num(field.available),
                            partial: num(field.partial),
                            missing: num(field.missing),
                          })}
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

              <Section icon={Layers} title={t('quality.couldNotRun')}>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('common.check')}</th>
                        <th>{t('quality.evaluated')}</th>
                        <th>{t('quality.unavailable')}</th>
                        <th>{t('quality.firing')}</th>
                        <th>{t('quality.commonReason')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.signal_availability.map((signal) => (
                        <tr key={signal.code}>
                          <td className="lead">
                            <span className="signal-code" style={{ marginRight: 8 }}>
                              {signal.code}
                            </span>
                            {signalName(signal.code)}
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
                              <span className="faint">{t('quality.ranForEvery')}</span>
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
                title={t('quality.weakest')}
                actions={
                  <span className="stat-note" style={{ marginTop: 0 }}>
                    {t('quality.shown', {
                      shown: num(Math.min(MATRIX_ROWS, data.companies.length)),
                      total: num(data.companies_analysed),
                    })}
                  </span>
                }
              >
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('common.company')}</th>
                        <th>{t('quality.quality')}</th>
                        {data.field_coverage.map((field) => (
                          <th key={field.key} style={{ width: 40, textAlign: 'center' }}>
                            {fieldShort(field.key)}
                          </th>
                        ))}
                        <th>{t('quality.checksNotRun')}</th>
                        <th>{t('common.priority')}</th>
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
                                {sectorLabel(company.sector)} · {company.region}
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
                                title={`${fieldLabel(key)}: ${fieldStateLabel(company.fields[key])}`}
                              />
                            </td>
                          ))}
                          <td className="num">{company.unavailable_signals}</td>
                          <td>
                            <Pill tone={LEVEL_TONE[company.priority_level]}>
                              {levelLabel(company.priority_level)}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="pager">
                  <span className="dot-row">
                    <span className="dot ok" /> {fieldStateLabel('AVAILABLE')}
                    <span className="dot warn" style={{ marginLeft: 12 }} />{' '}
                    {fieldStateLabel('PARTIAL')}
                    <span className="dot stop" style={{ marginLeft: 12 }} />{' '}
                    {fieldStateLabel('MISSING')}
                  </span>
                  <span>{t('quality.columnOrder')}</span>
                </div>
              </Section>
            </>
          );
        }}
      </Resource>
    </div>
  );
}
