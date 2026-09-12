import { useEffect, useRef, useState } from 'react';
import { LogIn } from 'lucide-react';

import { post } from '../lib/api.js';
import { LANGUAGES, useI18n } from '../lib/i18n.jsx';

/**
 * The whole interface until the service says the session is good.
 *
 * It draws nothing the viewer has not earned: no figures, no company names,
 * no counts. Everything on a page behind this arrives from an endpoint that
 * refuses without the session, so this form is a door rather than a curtain —
 * hiding it would not reveal anything, because there is nothing here to
 * reveal.
 */
export default function SignIn({ onSignedIn }) {
  const { lang, setLang, t } = useI18n();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const first = useRef(null);

  useEffect(() => {
    first.current?.focus();
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    if (busy || !username.trim() || !password) return;

    setBusy(true);
    setError('');
    try {
      const session = await post('/auth/login', { username, password });
      onSignedIn(session);
    } catch (failure) {
      // The service says only that the pair was wrong, never which half, and
      // this repeats that rather than guessing at something more helpful.
      if (failure.status === 401) setError(t('signIn.wrong'));
      else if (failure.status === 429) setError(t('signIn.tooMany'));
      else setError(t('signIn.failed'));
      setPassword('');
      setBusy(false);
    }
  };

  return (
    <div className="signin">
      <div className="signin-langs" role="group" aria-label={t('lang.switch')}>
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

      <form className="signin-card" onSubmit={submit}>
        <div className="signin-brand">
          <span className="brand-mark">GÜS-DEDEKTİV</span>
          <span className="brand-sub">{t('brand.sub')}</span>
        </div>

        <h1 className="signin-title">{t('signIn.title')}</h1>
        <p className="signin-lede">{t('signIn.lede')}</p>

        <label className="signin-field">
          <span>{t('signIn.user')}</span>
          <input
            ref={first}
            className="input"
            type="text"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            disabled={busy}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>

        <label className="signin-field">
          <span>{t('signIn.password')}</span>
          <input
            className="input"
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            disabled={busy}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {/* assertive: a viewer who has just submitted is waiting on exactly this. */}
        <div className="signin-error" role="alert" aria-live="assertive">
          {error}
        </div>

        <button
          type="submit"
          className="btn btn-primary signin-submit"
          disabled={busy || !username.trim() || !password}
        >
          <LogIn size={14} strokeWidth={2} />
          {t(busy ? 'signIn.working' : 'signIn.submit')}
        </button>

        <p className="signin-foot">{t('signIn.disclaimer')}</p>
      </form>
    </div>
  );
}
