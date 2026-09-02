import { Link } from 'react-router-dom';

import { LANGUAGES, useI18n } from '../lib/i18n.jsx';

/**
 * Identity on the left, the language on the right. Navigation is in the dock,
 * and the period is whatever the API reports as current.
 */
export default function Topbar() {
  const { lang, setLang, t } = useI18n();

  return (
    <header className="topbar">
      <Link className="brand" to="/">
        <span>
          <span className="brand-mark">GÜS-DEDEKTİV</span>
          <span className="brand-sub">{t('brand.sub')}</span>
        </span>
      </Link>

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
    </header>
  );
}
