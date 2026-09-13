import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { setLocale } from './format.js';
import { STRINGS } from './strings.js';

export const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'tr', label: 'TR', name: 'Türkçe' },
];

const STORAGE_KEY = 'gus.lang';

// The language a first-time visitor gets. Turkish: this is a Turkish platform,
// about Turkish regulation, read by Turkish auditors, and arriving in English
// made every one of them start by hunting for the switch.
const DEFAULT_LANG = 'tr';

// Where a missing string is looked up instead. English, because that catalogue
// is the complete one; a key added in Turkish alone would otherwise render as
// its own key. This is not the default language and must not be confused with
// one — that mix-up is what used to open the interface in English.
const FALLBACK = 'en';

const I18nContext = createContext(null);

function supported(code) {
  return LANGUAGES.some((item) => item.code === code);
}

function readStored() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (supported(saved)) return saved;
  } catch {
    // A browser that refuses storage still gets a working interface.
  }

  // Nothing chosen yet: follow the browser, so a visitor who reads English
  // is not handed Turkish and a Turkish one is not handed English. `en-GB`
  // and `tr-TR` both carry the language in front of the dash.
  try {
    for (const tag of navigator.languages ?? [navigator.language]) {
      const code = String(tag).toLowerCase().split('-')[0];
      if (supported(code)) return code;
    }
  } catch {
    // No navigator, or a browser that hides it. The default stands.
  }

  return DEFAULT_LANG;
}

/**
 * One language for the whole interface. The choice is held here, mirrored into
 * the number and date formatters, and written to `lang` on the document so a
 * screen reader and the browser's own hyphenation follow it too.
 */
export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(readStored);

  // Before first paint: a table of Turkish figures must not flash in English
  // separators on the way in.
  useMemo(() => setLocale(lang), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Nothing to do; the session still holds the choice.
    }
  }, [lang]);

  const setLang = useCallback((next) => {
    setLocale(next);
    setLangState(next);
  }, []);

  const t = useCallback(
    (key, params) => translate(lang, key, params),
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error('useI18n must be used inside a LanguageProvider');
  return context;
}

/** The common case: only the lookup function is wanted. */
export function useT() {
  return useI18n().t;
}

/**
 * `{name}` placeholders are filled from `params`. A key with no entry in
 * either language falls through as itself, which makes a gap obvious on
 * screen rather than silently blank.
 */
export function translate(lang, key, params) {
  const template = STRINGS[lang]?.[key] ?? STRINGS[FALLBACK][key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name) =>
    params[name] === undefined ? whole : String(params[name]),
  );
}
