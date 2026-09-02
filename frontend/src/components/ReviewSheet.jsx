import { useState } from 'react';
import { Info } from 'lucide-react';

import { post } from '../lib/api.js';
import { useT } from '../lib/i18n.jsx';
import { statusLabel } from '../lib/format.js';
import { Sheet } from './ui.jsx';

const ACTIONS = [
  'MARKED_FOR_INSPECTION',
  'UNDER_REVIEW',
  'INFORMATION_REQUESTED',
  'INSPECTION_COMPLETED',
  'NO_ACTION_REQUIRED',
];

// Names, not labels: an auditor is a person, and a person's name is not
// translated between languages.
const AUDITORS = [
  { id: 'aydin.m', name: 'M. Aydın' },
  { id: 'korkmaz.s', name: 'S. Korkmaz' },
  { id: 'demir.e', name: 'E. Demir' },
  { id: 'yilmaz.b', name: 'B. Yılmaz' },
  { id: 'cetin.o', name: 'O. Çetin' },
];

export default function ReviewSheet({ open, company, period, current, onClose, onSaved }) {
  const t = useT();

  const [status, setStatus] = useState('MARKED_FOR_INSPECTION');
  const [auditor, setAuditor] = useState('aydin.m');
  const [notes, setNotes] = useState('');
  const [tonnage, setTonnage] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await post(`/companies/${company.id}/review?period=${period}`, {
        status,
        auditor_id: auditor,
        notes: notes.trim() || null,
        confirmed_additional_tonnage:
          status === 'INSPECTION_COMPLETED' && tonnage !== '' ? Number(tonnage) : null,
      });
      setNotes('');
      setTonnage('');
      onSaved(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet
      open={open}
      title={t('review.title')}
      closeLabel={t('common.close')}
      lede={t('review.lede', {
        company: company.company_name,
        status: statusLabel(current).toLocaleLowerCase(),
      })}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
            {t('common.cancel')}
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={saving}>
            {saving && <span className="spin on-ink" />}
            {t('review.submit')}
          </button>
        </>
      }
    >
      <div className="notice">
        <Info size={15} strokeWidth={1.9} />
        <div>
          <div className="notice-title">{t('review.appendedTitle')}</div>
          {t('review.appendedNote')}
        </div>
      </div>

      <div className="field">
        <span className="label">{t('review.action')}</span>
        <div className="steps" style={{ borderTop: 'none' }}>
          {ACTIONS.map((value) => (
            <label
              className="check"
              key={value}
              style={{ padding: '10px 0', marginBottom: 0, borderBottom: '1px solid var(--rule)' }}
            >
              <input
                type="radio"
                name="review-status"
                value={value}
                checked={status === value}
                onChange={() => setStatus(value)}
              />
              <span>
                <b style={{ color: 'var(--ink)', fontWeight: 600 }}>{statusLabel(value)}</b>
                <span style={{ display: 'block', fontSize: 12.5, color: 'var(--ink-3)' }}>
                  {t(`review.note.${value}`)}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <label className="field">
        <span className="label">{t('review.auditor')}</span>
        <select
          className="select"
          value={auditor}
          onChange={(event) => setAuditor(event.target.value)}
        >
          {AUDITORS.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>

      {status === 'INSPECTION_COMPLETED' && (
        <label className="field">
          <span className="label">{t('review.tonnage')}</span>
          <input
            className="input"
            type="number"
            min="0"
            step="0.1"
            value={tonnage}
            placeholder={t('review.tonnagePlaceholder')}
            onChange={(event) => setTonnage(event.target.value)}
          />
          <span className="field-note">{t('review.tonnageNote')}</span>
        </label>
      )}

      <label className="field">
        <span className="label">{t('review.notes')}</span>
        <textarea
          className="textarea"
          rows={4}
          value={notes}
          placeholder={t('review.notesPlaceholder')}
          onChange={(event) => setNotes(event.target.value)}
        />
        {error && <span className="field-error">{error}</span>}
      </label>
    </Sheet>
  );
}
