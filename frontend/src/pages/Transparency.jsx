import { Check, Cpu, Layers, Scale, Sliders, Table2, X } from 'lucide-react';

import { useApi } from '../lib/api.js';
import { fieldLabel, levelLabel, materialLabel, num, percent, signalName } from '../lib/format.js';
import { useI18n } from '../lib/i18n.jsx';
import { PageHead, Panel, Pill, Resource, Section } from '../components/ui.jsx';

export default function Transparency() {
  const { lang, t } = useI18n();
  // This page is almost entirely prose the API owns on purpose, so the whole
  // payload is fetched in the active language.
  const state = useApi(`/transparency?lang=${lang}`, [lang]);

  return (
    <div className="page">
      <Resource state={state} rows={3}>
        {(data) => (
          <>
            <PageHead
              eyebrow={t('transparency.eyebrow')}
              icon={Scale}
              title={t('transparency.title')}
            />

            <div className="disclaimer">
              <span className="label">{t('transparency.disclaimer')}</span>
              <p>{data.disclaimer}</p>
            </div>

            <Section icon={Check} title={t('transparency.scope')}>
              <div className="grid grid-side">
                <Panel>
                  <span className="label">{t('transparency.does')}</span>
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
                  <span className="label">{t('transparency.doesNot')}</span>
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

            <Section icon={Layers} title={t('transparency.principles')}>
              <Panel>
                {data.principles.map((principle) => (
                  <div className="principle" key={principle.title}>
                    <h3>{principle.title}</h3>
                    <p>{principle.body}</p>
                  </div>
                ))}
              </Panel>
            </Section>

            <Section icon={Cpu} title={t('transparency.engines')}>
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
                          {t(
                            engine.active
                              ? 'transparency.inService'
                              : engine.ready
                                ? 'transparency.ready'
                                : 'transparency.notAvailable',
                          )}
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
                    <span className="label">{t('transparency.expectedRange')}</span>
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

            <Section icon={Sliders} title={t('transparency.policy')}>
              <div className="grid grid-side">
                <Panel>
                  <div className="stat-head" style={{ marginBottom: 14 }}>
                    <span className="label">{t('transparency.weights')}</span>
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
                            {signalName(weight.code)}
                          </td>
                          <td className="num right" style={{ padding: '9px 0', width: 70 }}>
                            {percent(weight.weight * 100)}
                          </td>
                          <td className="right" style={{ padding: '9px 0', width: 90 }}>
                            <Pill tone={weight.enabled ? 'ok' : 'mute'}>
                              {t(weight.enabled ? 'common.on' : 'common.off')}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>

                <div className="stack">
                  <Panel>
                    <span className="label">{t('transparency.bands')}</span>
                    <dl className="facts" style={{ marginTop: 12 }}>
                      {[...data.policy.bands].reverse().map((band) => (
                        <div key={band.level}>
                          <dt>{levelLabel(band.level)}</dt>
                          <dd>{t('common.range', { from: band.lower, to: band.upper })}</dd>
                        </div>
                      ))}
                    </dl>
                  </Panel>

                  <Panel>
                    <span className="label">{t('transparency.calculation')}</span>
                    <dl className="facts" style={{ marginTop: 12 }}>
                      <div>
                        <dt>{t('transparency.strongest')}</dt>
                        <dd>{percent(data.policy.strongest_signal_share * 100)}</dd>
                      </div>
                      <div>
                        <dt>{t('transparency.coverageNeeded')}</dt>
                        <dd>{percent(data.policy.min_coverage_for_confidence * 100)}</dd>
                      </div>
                      <div>
                        <dt>{t('transparency.rangeFull')}</dt>
                        <dd>±{percent(data.policy.interval_base_spread * 100)}</dd>
                      </div>
                      <div>
                        <dt>{t('transparency.rangeZero')}</dt>
                        <dd>±{percent((data.policy.interval_base_spread + data.policy.interval_uncertainty_spread) * 100)}</dd>
                      </div>
                    </dl>
                  </Panel>
                </div>
              </div>
            </Section>

            <Section icon={Layers} title={t('transparency.eightChecks')}>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t('transparency.code')}</th>
                      <th>{t('common.check')}</th>
                      <th>{t('transparency.compares')}</th>
                      <th>{t('transparency.inputs')}</th>
                      <th>{t('signals.score')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.signals.map((signal) => (
                      <tr key={signal.code}>
                        <td className="lead mono">{signal.code}</td>
                        <td className="lead">{signalName(signal.code)}</td>
                        <td style={{ maxWidth: 340, whiteSpace: 'normal' }}>{signal.summary}</td>
                        <td>{signal.inputs.join(', ')}</td>
                        <td className="num">{percent(signal.weight * 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            <Section icon={Table2} title={t('transparency.tariff', { year: data.tariff_year })}>
              <div className="grid grid-side">
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('common.material')}</th>
                        <th>{t('transparency.tariffColumn')}</th>
                        <th>{t('transparency.co2ePerTonne')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.tariffs.map((row) => (
                        <tr key={row.key}>
                          <td className="lead">{materialLabel(row.key)}</td>
                          <td className="num">{num(row.tariff_try_per_kg, 2)} TL/kg</td>
                          <td className="num">{num(row.co2e_tonnes_avoided_per_tonne, 2)} t</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <Panel>
                  <span className="label">{t('transparency.fieldsRead')}</span>
                  <dl className="facts" style={{ marginTop: 12 }}>
                    {data.data_fields.map((field) => (
                      <div key={field.key}>
                        <dt>{fieldLabel(field.key)}</dt>
                        <dd>
                          {t('transparency.ofDataQuality', {
                            percent: percent(field.weight * 100),
                          })}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <div className="divider" />
                  <span className="label">{t('transparency.decisionLog')}</span>
                  <p className="stat-note" style={{ marginTop: 10 }}>
                    {t('transparency.decisionLogNote', {
                      count: num(data.audit_chain.total_events),
                      state: t(
                        data.audit_chain.intact
                          ? 'transparency.verifying'
                          : 'transparency.failing',
                      ),
                    })}
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
