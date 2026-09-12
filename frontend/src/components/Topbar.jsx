import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { KeyRound, LogOut } from 'lucide-react';

import { useApp } from '../App.jsx';
import { getApiKey, post, setApiKey, useApi } from '../lib/api.js';
import { LANGUAGES, useI18n } from '../lib/i18n.jsx';

/**
 * Identity on the left, the language on the right. Navigation is in the dock,
 * and the period is whatever the API reports as current.
 */
export default function Topbar() {
  const { lang, setLang, t } = useI18n();
  const health = useApi('/health');
  const gated = health.data?.writes === 'api-key';

  return (
    <header className="topbar">
      <Link className="brand" to="/">
        <span>
          <span className="brand-mark">GÜS-DEDEKTİV</span>
          <span className="brand-sub">{t('brand.sub')}</span>
        </span>
      </Link>

      <div className="topbar-tools">
        {gated && <KeyControl />}
        <SignOut />

        <div className="lang-switch" role="group" aria-label={t('lang.switch')}>
          {LANGUAGES.map((option) => (
            <button
              key={option.code}
              type="button"
              className={`lang-option${option.code === lang ? ' on' : ''}`}
              onClick={() => setLang(option.code)}
              aria-pressed={option.code === lang}
              lang={option.code}
              title={option.name}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

/**
 * Shown only when the site asks for a sign-in. A deployment that is open has
 * nothing to sign out of, so the control would be a button that did nothing.
 */
function SignOut() {
  const { t } = useI18n();
  const session = useApi('/auth/status');
  if (!session.data?.enabled) return null;

  const leave = async () => {
    try {
      await post('/auth/logout');
    } catch {
      // The cookie may already be gone. Reloading lands on the form either
      // way, which is what the viewer asked for.
    }
    window.location.reload();
  };

  return (
    <button type="button" className="key-button" onClick={leave} title={t('signIn.out')}>
      <LogOut size={13} strokeWidth={2} />
      {t('signIn.out')}
    </button>
  );
}

/**
 * Shown only when the API says writing needs a key. The open prototype never
 * sees it; a gated deployment gets somewhere to put the key instead of every
 * decision failing with 401.
 */
function KeyControl() {
  const { t } = useI18n();
  const { toast } = useApp();

  const [open, setOpen] = useState(false);
  const [hasKey, setHasKey] = useState(() => Boolean(getApiKey()));
  const [draft, setDraft] = useState('');
  const box = useRef(null);
  const field = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    field.current?.focus();
    const onKey = (event) => event.key === 'Escape' && setOpen(false);
    const onPointer = (event) => {
      if (box.current && !box.current.contains(event.target)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onPointer);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onPointer);
    };
  }, [open]);

  const save = (event) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    setApiKey(value);
    setHasKey(true);
    setDraft('');
    setOpen(false);
    toast(t('key.saved'));
  };

  const forget = () => {
    setApiKey('');
    setHasKey(false);
    setOpen(false);
    toast(t('key.cleared'));
  };

  return (
    <div className="key-control" ref={box}>
      <button
        type="button"
        className={`key-button${hasKey ? ' on' : ''}`}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <KeyRound size={13} strokeWidth={2} />
        {t(hasKey ? 'key.set' : 'key.button')}
      </button>

      {open && (
        <form className="key-pop" role="dialog" aria-label={t('key.title')} onSubmit={save}>
          <div className="key-pop-title">{t('key.title')}</div>
          <p className="key-pop-note">{t('key.note')}</p>
          <input
            ref={field}
            className="input mono"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            placeholder={t('key.placeholder')}
            onChange={(event) => setDraft(event.target.value)}
            aria-label={t('key.button')}
          />
          <div className="key-pop-actions">
            {hasKey && (
              <button type="button" className="btn btn-ghost" onClick={forget}>
                {t('key.clear')}
              </button>
            )}
            <button type="submit" className="btn btn-primary" disabled={!draft.trim()}>
              {t('key.save')}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
