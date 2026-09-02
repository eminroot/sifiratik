import { useEffect, useRef, useState } from 'react';
import {
  Boxes,
  Cloud,
  CircleDollarSign,
  ListChecks,
  Play,
  Recycle,
  Target,
} from 'lucide-react';

import { useApp } from '../App.jsx';
import { post, query, useApi } from '../lib/api.js';
import { lira, materialLabel, num, percent, sectorLabel, splitUnit, tonnes } from '../lib/format.js';
import { useI18n } from '../lib/i18n.jsx';
import QueueTable from '../components/QueueTable.jsx';
import { Figures, PageHead, Panel, Resource, Section, Stat } from '../components/ui.jsx';

const SHORTLIST_SIZES = [25, 50, 100, 200];

export default function Pilot() {
  const { period, reference, toast } = useApp();
  const { lang, t } = useI18n();

  const [region, setRegion] = useState('Antalya');
  const [sector, setSector] = useState('');
  const [size, setSize] = useState(100);

  // The run sequence is prose the API writes, so it is fetched in the active
  // language rather than translated after the fact.
  const state = useApi(
    `/cop31/pilot${query({ period, region, sector, shortlist_size: size, lang })}`,
    [period, lang],
  );

  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [revealed, setRevealed] = useState(9);
  const timers = useRef([]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const active = result ?? state.data;

  const run = async () => {
    setRunning(true);
    setRevealed(0);
    try {
      const payload = await post(`/cop31/pilot/run${query({ lang })}`, {
        region,
        sector: sector || null,
        shortlist_size: size,
        simulate_outcomes: true,
        period,
      });
      setResult(payload);
      // Reveal the steps in order, so the run reads as a sequence rather than
      // a block of text appearing at once.
      timers.current = payload.steps.map((_, index) =>
        setTimeout(() => setRevealed(index + 1), 130 * (index + 1)),
      );
      setTimeout(() => setRunning(false), 130 * payload.steps.length);
      toast(
        t('pilot.ranMessage', {
          count: num(payload.findings.companies_shortlisted),
          region,
        }),
      );
    } catch (error) {
      toast(error.message, 'bad');
      setRunning(false);
      setRevealed(9);
    }
  };

  return (
    <div className="page wide">
      <Resource state={state} rows={3}>
        {() => {
          if (!active) return null;
          const { config, steps, findings, shortlist } = active;

          return (
            <>
              <PageHead
                eyebrow={t('pilot.eyebrow')}
                icon={Target}
                title={config.name}
              >
                <button type="button" className="btn btn-primary" onClick={run} disabled={running}>
                  {running ? <span className="spin on-ink" /> : <Play size={15} strokeWidth={1.9} />}
                  {t(running ? 'pilot.running' : 'pilot.run')}
                </button>
              </PageHead>

              <div className="filters">
                <select
                  className="filter-select on"
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  aria-label={t('pilot.province')}
                >
                  {(reference?.regions ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {t('pilot.regionOption', {
                        region: option.label,
                        count: num(option.count),
                      })}
                    </option>
                  ))}
                </select>

                <select
                  className={`filter-select${sector ? ' on' : ''}`}
                  value={sector}
                  onChange={(event) => setSector(event.target.value)}
                  aria-label={t('pilot.sector')}
                >
                  <option value="">{t('pilot.allSectors')}</option>
                  {(reference?.sectors ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {sectorLabel(option.value)}
                    </option>
                  ))}
                </select>

                <select
                  className="filter-select on"
                  value={size}
                  onChange={(event) => setSize(Number(event.target.value))}
                  aria-label={t('pilot.shortlistSize')}
                >
                  {SHORTLIST_SIZES.map((value) => (
                    <option key={value} value={value}>
                      {t('pilot.top', { count: value })}
                    </option>
                  ))}
                </select>

                <span className="stat-note" style={{ marginTop: 0, marginLeft: 'auto' }}>
                  {t(result ? 'pilot.runRecorded' : 'pilot.asConfigured')}
                </span>
              </div>

              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 16 }}>
                    <span className="stat-chip">
                      <ListChecks size={14} strokeWidth={1.9} />
                    </span>
                    <span className="label">{t('pilot.sequence')}</span>
                  </div>

                  <div className="runbook">
                    {steps.map((step) => (
                      <div
                        className={`run-step${step.index <= revealed ? ' reached' : ''}`}
                        key={step.key}
                      >
                        <span className="run-index">{String(step.index).padStart(2, '0')}</span>
                        <div>
                          <div className="run-label">{step.label}</div>
                          <div className="run-detail">{step.detail}</div>
                        </div>
                        {step.value && <span className="run-value">{step.value}</span>}
                      </div>
                    ))}
                  </div>
                </Panel>

                <Figures rows>
                  <Stat
                    icon={Boxes}
                    label={t('pilot.shortlisted')}
                    value={t('pilot.shortlistedValue', {
                      shortlisted: num(findings.companies_shortlisted),
                      analysed: num(findings.companies_analysed),
                    })}
                    note={t('pilot.shortlistedNote', {
                      critical: findings.critical,
                      high: findings.high,
                      medium: findings.medium,
                    })}
                  />
                  <Stat
                    icon={CircleDollarSign}
                    label={t('pilot.atStake')}
                    {...splitUnit(lira(findings.estimated_gekap_try))}
                    note={t('pilot.atStakeNote', {
                      tonnes: tonnes(findings.additional_tonnage),
                    })}
                  />
                  <Stat
                    icon={Recycle}
                    label={t('pilot.recovery')}
                    {...splitUnit(tonnes(findings.recovery_potential_tonnes))}
                    note={t('pilot.recoveryNote')}
                  />
                  <Stat
                    icon={Cloud}
                    label={t('pilot.emissions')}
                    value={num(findings.co2e_avoided_tonnes)}
                    unit="t CO2e"
                    note={t('pilot.emissionsNote', {
                      percent: percent(findings.average_data_quality),
                    })}
                  />
                </Figures>
              </div>

              {findings.by_material.length > 0 && (
                <Section icon={Boxes} title={t('pilot.material')}>
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>{t('common.material')}</th>
                          <th>{t('common.tonnage')}</th>
                          <th>{t('pilot.contribution')}</th>
                          <th>{t('pilot.co2eIfRecovered')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {findings.by_material.map((row) => (
                          <tr key={row.key}>
                            <td className="lead">{materialLabel(row.key)}</td>
                            <td className="num">{tonnes(row.tonnes)}</td>
                            <td className="num">{lira(row.gekap_value_try)}</td>
                            <td className="num">{num(row.co2e_avoided_tonnes)} t</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              )}

              <Section
                icon={ListChecks}
                title={t('pilot.shortlist')}
                actions={
                  <span className="stat-note" style={{ marginTop: 0 }}>
                    {t('pilot.unavailableNote', { count: num(findings.signals_unavailable) })}
                  </span>
                }
              >
                <QueueTable items={shortlist.slice(0, 25)} />
                {shortlist.length > 25 && (
                  <div className="pager">
                    <span>{t('pilot.showingTop', { total: num(shortlist.length) })}</span>
                  </div>
                )}
              </Section>
            </>
          );
        }}
      </Resource>
    </div>
  );
}
