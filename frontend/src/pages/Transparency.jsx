import { Check, Cpu, Layers, Scale, Sliders, Table2, X } from 'lucide-react';

import { useApi } from '../lib/api.js';
import { num, percent } from '../lib/format.js';
import { PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function Transparency() {
  const state = useApi('/transparency');

  return (
    <div className="page">
      <Resource state={state} rows={3}>
        {(data) => (
          <>
            <PageHead
              eyebrow="How this works"
              icon={Scale}
              title="What the platform claims"
              lede="The score sets an order of inspection. It does not settle a question of compliance."
            />

            <div className="disclaimer">
              <span className="label">Standing disclaimer</span>
              <p>{data.disclaimer}</p>
            </div>

            <Section icon={Check} title="Scope">
              <div className="grid grid-side">
                <Panel>
                  <span className="label">What it does</span>
                  <ul className="prose-list" style={{ marginTop: 12 }}>
                    {data.does.map((line) => (
                      <li className="yes" key={line}>
                        <Check size={15} strokeWidth={2} />
                        {line}
                      </li>
                    ))}
                  </ul>
                </Panel>

                <Panel>
                  <span className="label">What it does not do</span>
                  <ul className="prose-list" style={{ marginTop: 12 }}>
                    {data.does_not.map((line) => (
                      <li className="no" key={line}>
                        <X size={15} strokeWidth={2} />
                        {line}
                      </li>
                    ))}
                  </ul>
                </Panel>
              </div>
            </Section>

            <Section icon={Layers} title="Principles the scoring holds to">
              <Panel>
                {data.principles.map((principle) => (
                  <div className="principle" key={principle.title}>
                    <h3>{principle.title}</h3>
                    <p>{principle.body}</p>
                  </div>
                ))}
              </Panel>
            </Section>

            <Section icon={Cpu} title="Engines">
              <div className="grid grid-side">
                {data.engines.map((engine) => (
                  <Panel key={engine.name}>
                    <div className="stat-head" style={{ marginBottom: 14 }}>
                      <span className="stat-chip">
                        <Cpu size={14} strokeWidth={1.9} />
                      </span>
                      <span className="label">{engine.kind}</span>
                      <span className="stat-head-action">
                        <Pill tone={engine.active ? 'ok' : engine.ready ? 'cool' : 'mute'}>
                          {engine.active ? 'In service' : engine.ready ? 'Ready' : 'Not available'}
                        </Pill>
                      </span>
                    </div>

                    <div className="mono" style={{ color: 'var(--ink-2)', marginBottom: 10 }}>
                      {engine.version}
                    </div>
                    <p className="stat-note" style={{ marginTop: 0 }}>
                      {engine.description}
                    </p>

                    <div className="divider" />
                    <span className="label">Expected range</span>
                    <p className="stat-note" style={{ marginTop: 8 }}>
                      {engine.produces_interval}
                    </p>

                    {engine.notes.length > 0 && (
                      <ul className="prose-list" style={{ marginTop: 14 }}>
                        {engine.notes.map((note) => (
                          <li key={note} style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>
                            {note}
                          </li>
                        ))}
                      </ul>
                    )}
                  </Panel>
                ))}
              </div>
            </Section>

            <Section icon={Sliders} title="Policy in force">
              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 14 }}>
                    <span className="label">Signal weights</span>
                    <span className="stat-head-action mono" style={{ fontSize: 12 }}>
                      {data.policy.version}
                    </span>
                  </div>
                  <table className="table">
                    <tbody>
                      {data.policy.weights.map((weight) => (
                        <tr key={weight.code}>
                          <td style={{ padding: '9px 0' }}>
                            <span className="signal-code" style={{ marginRight: 8 }}>
                              {weight.code}
                            </span>
                            {weight.name}
                          </td>
                          <td className="num right" style={{ padding: '9px 0', width: 70 }}>
                            {percent(weight.weight * 100)}
                          </td>
                          <td className="right" style={{ padding: '9px 0', width: 90 }}>
                            <Pill tone={weight.enabled ? 'ok' : 'mute'}>
                              {weight.enabled ? 'On' : 'Off'}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>

                <div className="stack">
                  <Panel>
                    <span className="label">Priority bands</span>
                    <dl className="facts" style={{ marginTop: 12 }}>
                      {[...data.policy.bands].reverse().map((band) => (
                        <div key={band.level}>
                          <dt style={{ textTransform: 'capitalize' }}>{band.level.toLowerCase()}</dt>
                          <dd>
                            {band.lower} to {band.upper}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </Panel>

                  <Panel>
                    <span className="label">Calculation</span>
                    <dl className="facts" style={{ marginTop: 12 }}>
                      <div>
                        <dt>Weight of the strongest finding</dt>
                        <dd>{percent(data.policy.strongest_signal_share * 100)}</dd>
                      </div>
                      <div>
                        <dt>Coverage needed for confidence</dt>
                        <dd>{percent(data.policy.min_coverage_for_confidence * 100)}</dd>
                      </div>
                      <div>
                        <dt>Range at full data quality</dt>
                        <dd>±{percent(data.policy.interval_base_spread * 100)}</dd>
                      </div>
                      <div>
                        <dt>Widening at zero data quality</dt>
                        <dd>±{percent((data.policy.interval_base_spread + data.policy.interval_uncertainty_spread) * 100)}</dd>
                      </div>
                    </dl>
                  </Panel>
                </div>
              </div>
            </Section>

            <Section icon={Layers} title="The eight checks">
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Check</th>
                      <th>What it compares</th>
                      <th>Inputs it needs</th>
                      <th>Weight</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.signals.map((signal) => (
                      <tr key={signal.code}>
                        <td className="lead mono">{signal.code}</td>
                        <td className="lead">{signal.name}</td>
                        <td style={{ maxWidth: 340, whiteSpace: 'normal' }}>{signal.summary}</td>
                        <td>{signal.inputs.join(', ')}</td>
                        <td className="num">{percent(signal.weight * 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            <Section icon={Table2} title={`Contribution tariff, ${data.tariff_year}`}>
              <div className="grid grid-side">
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Material</th>
                        <th>Tariff</th>
                        <th>CO2e avoided per tonne recovered</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.tariffs.map((row) => (
                        <tr key={row.key}>
                          <td className="lead">{row.name}</td>
                          <td className="num">{num(row.tariff_try_per_kg, 2)} TL/kg</td>
                          <td className="num">{num(row.co2e_tonnes_avoided_per_tonne, 2)} t</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <Panel>
                  <span className="label">Fields the score reads</span>
                  <dl className="facts" style={{ marginTop: 12 }}>
                    {data.data_fields.map((field) => (
                      <div key={field.key}>
                        <dt>{field.name}</dt>
                        <dd>{percent(field.weight * 100)} of data quality</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="divider" />
                  <span className="label">Decision log</span>
                  <p className="stat-note" style={{ marginTop: 10 }}>
                    {num(data.audit_chain.total_events)} decisions recorded and{' '}
                    {data.audit_chain.intact ? 'verifying' : 'failing verification'} as of the last
                    check.
                  </p>
                </Panel>
              </div>
            </Section>
          </>
        )}
      </Resource>
    </div>
  );
}
