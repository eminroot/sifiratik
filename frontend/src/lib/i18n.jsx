import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { setLocale } from './format.js';
import { STRINGS } from './strings.js';

export const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'tr', label: 'TR', name: 'Türkçe' },
];

const STORAGE_KEY = 'gus.lang';
const FALLBACK = 'en';

const I18nContext = createContext(null);

function readStored() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (LANGUAGES.some((item) => item.code === saved)) return saved;
  } catch {
    // A browser that refuses storage still gets a working interface.
  }
  return FALLBACK;
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
