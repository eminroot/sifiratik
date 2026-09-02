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
import { lira, num, percent, splitUnit, tonnes } from '../lib/format.js';
import QueueTable from '../components/QueueTable.jsx';
import { Figures, PageHead, Panel, Resource, Section, Stat } from '../components/ui.jsx';

const SHORTLIST_SIZES = [25, 50, 100, 200];

export default function Pilot() {
  const { period, reference, toast } = useApp();

  const [region, setRegion] = useState('Antalya');
  const [sector, setSector] = useState('');
  const [size, setSize] = useState(100);

  const state = useApi(
    `/cop31/pilot${query({ period, region, sector, shortlist_size: size })}`,
    [period],
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
      const payload = await post('/cop31/pilot/run', {
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
      toast(`${payload.findings.companies_shortlisted} companies shortlisted in ${region}`);
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
                eyebrow="Pilot"
                icon={Target}
                title={config.name}
              >
                <button type="button" className="btn btn-primary" onClick={run} disabled={running}>
                  {running ? <span className="spin on-ink" /> : <Play size={15} strokeWidth={1.9} />}
                  {running ? 'Running' : 'Run pilot'}
                </button>
              </PageHead>

              <div className="filters">
                <select
                  className="filter-select on"
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  aria-label="Pilot province"
                >
                  {(reference?.regions ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} ({option.count} companies)
                    </option>
                  ))}
                </select>

                <select
                  className={`filter-select${sector ? ' on' : ''}`}
                  value={sector}
                  onChange={(event) => setSector(event.target.value)}
                  aria-label="Pilot sector"
                >
                  <option value="">All sectors</option>
                  {(reference?.sectors ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>

                <select
                  className="filter-select on"
                  value={size}
                  onChange={(event) => setSize(Number(event.target.value))}
                  aria-label="Shortlist size"
                >
                  {SHORTLIST_SIZES.map((value) => (
                    <option key={value} value={value}>
                      Top {value}
                    </option>
                  ))}
                </select>

                <span className="stat-note" style={{ marginTop: 0, marginLeft: 'auto' }}>
                  {result ? 'Run recorded' : 'Showing the configuration as it stands'}
                </span>
              </div>

              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 16 }}>
                    <span className="stat-chip">
                      <ListChecks size={14} strokeWidth={1.9} />
                    </span>
                    <span className="label">Run sequence</span>
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
                    label="Shortlisted"
                    value={`${num(findings.companies_shortlisted)} of ${num(findings.companies_analysed)}`}
                    note={`${findings.critical} critical, ${findings.high} high, ${findings.medium} medium`}
                  />
                  <Stat
                    icon={CircleDollarSign}
                    label="Contribution at stake"
                    {...splitUnit(lira(findings.estimated_gekap_try))}
                    note={`${tonnes(findings.additional_tonnage)} below the expected range`}
                  />
                  <Stat
                    icon={Recycle}
                    label="Recovery potential"
                    {...splitUnit(tonnes(findings.recovery_potential_tonnes))}
                    note="projected from the confirmation rate of closed inspections"
                  />
                  <Stat
                    icon={Cloud}
                    label="Emissions avoided"
                    value={num(findings.co2e_avoided_tonnes)}
                    unit="t CO2e"
                    note={`at ${percent(findings.average_data_quality)} mean data quality`}
                  />
                </Figures>
              </div>

              {findings.by_material.length > 0 && (
                <Section icon={Boxes} title="Material in the shortlist">
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Material</th>
                          <th>Tonnage</th>
                          <th>Contribution</th>
                          <th>CO2e if recovered</th>
                        </tr>
                      </thead>
                      <tbody>
                        {findings.by_material.map((row) => (
                          <tr key={row.key}>
                            <td className="lead">{row.name}</td>
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
                title="Shortlist"
                actions={
                  <span className="stat-note" style={{ marginTop: 0 }}>
                    {findings.signals_unavailable} checks across the shortlist could not run
                  </span>
                }
              >
                <QueueTable items={shortlist.slice(0, 25)} />
                {shortlist.length > 25 && (
                  <div className="pager">
                    <span>
                      Showing the top 25 of {shortlist.length}. The rest carry the same reasons and
                      are in the queue.
                    </span>
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
