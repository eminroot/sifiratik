import { useState } from 'react';
import { Info } from 'lucide-react';

import { post } from '../lib/api.js';
import { STATUS_LABEL } from '../lib/format.js';
import { Sheet } from './ui.jsx';

const ACTIONS = [
  {
    value: 'MARKED_FOR_INSPECTION',
    note: 'Adds the company to the field schedule.',
  },
  { value: 'UNDER_REVIEW', note: 'Desk review has started, no site visit yet.' },
  {
    value: 'INFORMATION_REQUESTED',
    note: 'Waiting on the company for records that would settle the question.',
  },
  {
    value: 'INSPECTION_COMPLETED',
    note: 'Closes the case. Record the corrected tonnage if one was established.',
  },
  { value: 'NO_ACTION_REQUIRED', note: 'Closes the case with the declaration accepted.' },
];

const AUDITORS = [
  { id: 'aydin.m', name: 'M. Aydın' },
  { id: 'korkmaz.s', name: 'S. Korkmaz' },
  { id: 'demir.e', name: 'E. Demir' },
  { id: 'yilmaz.b', name: 'B. Yılmaz' },
  { id: 'cetin.o', name: 'O. Çetin' },
];

export default function ReviewSheet({ open, company, period, current, onClose, onSaved }) {
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
      title="Record a decision"
      lede={`${company.company_name}. The current standing is ${STATUS_LABEL[current].toLowerCase()}.`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={saving}>
            {saving && <span className="spin on-ink" />}
            Record decision
          </button>
        </>
      }
    >
      <div className="notice">
        <Info size={15} strokeWidth={1.9} />
        <div>
          <div className="notice-title">This is appended, not edited</div>
          The previous standing stays on the record and the new one is linked to it.
        </div>
      </div>

      <div className="field">
        <span className="label">Action</span>
        <div className="steps" style={{ borderTop: 'none' }}>
          {ACTIONS.map((action) => (
            <label
              className="check"
              key={action.value}
              style={{ padding: '10px 0', marginBottom: 0, borderBottom: '1px solid var(--rule)' }}
            >
              <input
                type="radio"
                name="review-status"
                value={action.value}
                checked={status === action.value}
                onChange={() => setStatus(action.value)}
              />
              <span>
                <b style={{ color: 'var(--ink)', fontWeight: 600 }}>{STATUS_LABEL[action.value]}</b>
                <span style={{ display: 'block', fontSize: 12.5, color: 'var(--ink-3)' }}>
                  {action.note}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <label className="field">
        <span className="label">Auditor</span>
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
          <span className="label">Corrected tonnage established</span>
          <input
            className="input"
            type="number"
            min="0"
            step="0.1"
            value={tonnage}
            placeholder="Leave empty if nothing was added"
            onChange={(event) => setTonnage(event.target.value)}
          />
          <span className="field-note">
            Carried into the impact figures as confirmed, separately from what was projected.
          </span>
        </label>
      )}

      <label className="field">
        <span className="label">Notes</span>
        <textarea
          className="textarea"
          rows={4}
          value={notes}
          placeholder="What was checked, and what it showed"
          onChange={(event) => setNotes(event.target.value)}
        />
        {error && <span className="field-error">{error}</span>}
      </label>
    </Sheet>
  );
}
