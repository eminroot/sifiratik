/**
 * Figures, dates and the domain's fixed vocabulary.
 *
 * The active language lives here as module state rather than being threaded
 * through every call, because a formatter is called from render bodies that
 * have no business taking a locale argument. `LanguageProvider` sets it before
 * it sets its own state, so the re-render that follows already reads the new
 * one.
 */

const LOCALES = { en: 'en-GB', tr: 'tr-TR' };

let lang = 'en';
let locale = LOCALES.en;
let number = new Intl.NumberFormat(locale);
let oneDecimal = new Intl.NumberFormat(locale, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function setLocale(next) {
  if (!LOCALES[next] || next === lang) return;
  lang = next;
  locale = LOCALES[next];
  number = new Intl.NumberFormat(locale);
  oneDecimal = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Tonnes, with a decimal only where it carries information. */
export function tonnes(value, { unit = true } = {}) {
  if (value === null || value === undefined) return unit ? word('noFiling') : '--';
  const body = Math.abs(value) >= 100 ? number.format(Math.round(value)) : oneDecimal.format(value);
  return unit ? `${body} t` : body;
}

// Turkish abbreviates milyar / milyon / bin, so the letters differ even though
// the thresholds do not.
const SCALE = {
  en: { billion: 'B', million: 'M', thousand: 'K' },
  tr: { billion: ' Mr', million: ' Mn', thousand: ' B' },
};

/** Turkish lira, abbreviated once the figure stops being readable in full. */
export function lira(value, { compact = true } = {}) {
  if (value === null || value === undefined) return '--';
  if (!compact) return `${number.format(Math.round(value))} TL`;
  const scale = SCALE[lang] ?? SCALE.en;
  if (Math.abs(value) >= 1_000_000_000)
    return `${oneDecimal.format(value / 1_000_000_000)}${scale.billion} TL`;
  if (Math.abs(value) >= 1_000_000)
    return `${oneDecimal.format(value / 1_000_000)}${scale.million} TL`;
  if (Math.abs(value) >= 10_000)
    return `${number.format(Math.round(value / 1000))}${scale.thousand} TL`;
  return `${number.format(Math.round(value))} TL`;
}

export function percent(value, digits = 0) {
  if (value === null || value === undefined) return '--';
  return `${num(value, digits)}%`;
}

const UNIT_SUFFIXES = [' TL', ' t'];

/**
 * Splits a formatted figure into the quantity and its unit, so a component can
 * set the two at different weights. A value with no unit it recognises comes
 * back whole, which keeps a string like "No filing" intact.
 */
export function splitUnit(text) {
  if (typeof text !== 'string') return { value: text };
  if (text.length > 1 && text.endsWith('%')) return { value: text.slice(0, -1), unit: '%' };
  const suffix = UNIT_SUFFIXES.find((candidate) => text.endsWith(candidate));
  if (!suffix) return { value: text };
  return { value: text.slice(0, -suffix.length), unit: suffix.trim() };
}

export function date(value, { time = false } = {}) {
  if (!value) return '--';
  const parsed = new Date(value);
  const options = { day: '2-digit', month: 'short', year: 'numeric' };
  if (time) {
    options.hour = '2-digit';
    options.minute = '2-digit';
  }
  return new Intl.DateTimeFormat(locale, options).format(parsed);
}

export function relativeDays(days) {
  if (days === null || days === undefined) return '--';
  if (days === 0) return word('today');
  if (days === 1) return word('yesterday');
  if (days < 30) return word('daysAgo').replace('{n}', num(days));
  if (days < 60) return word('lastMonth');
  return word('monthsAgo').replace('{n}', num(Math.round(days / 30)));
}

export function shortHash(value, length = 10) {
  if (!value) return '--';
  return `${value.slice(0, length)}…${value.slice(-4)}`;
}

const WORDS = {
  en: {
    noFiling: 'No filing',
    today: 'today',
    yesterday: 'yesterday',
    daysAgo: '{n} days ago',
    lastMonth: 'last month',
    monthsAgo: '{n} months ago',
  },
  tr: {
    noFiling: 'Beyan yok',
    today: 'bugün',
    yesterday: 'dün',
    daysAgo: '{n} gün önce',
    lastMonth: 'geçen ay',
    monthsAgo: '{n} ay önce',
  },
};

function word(key) {
  return WORDS[lang]?.[key] ?? WORDS.en[key];
}

// --------------------------------------------------------------------------
// Domain vocabulary
//
// A tone is language independent; only the words change. Every lookup falls
// back to English and then to the code itself, so an unknown value from the
// API shows up on screen rather than as a blank cell.
// --------------------------------------------------------------------------

export const LEVEL_TONE = {
  CRITICAL: 'stop',
  HIGH: 'warn',
  MEDIUM: 'cool',
  LOW: 'ok',
};

export const STATUS_TONE = {
  AWAITING_REVIEW: 'mute',
  MARKED_FOR_INSPECTION: 'warn',
  UNDER_REVIEW: 'cool',
  INFORMATION_REQUESTED: 'cool',
  INSPECTION_COMPLETED: 'ok',
  NO_ACTION_REQUIRED: 'ok',
};

export const SIGNAL_STATE_TONE = {
  ACTIVE: 'stop',
  CLEAR: 'ok',
  UNAVAILABLE: 'mute',
  DISABLED: 'mute',
};

export const FIELD_STATE_TONE = {
  AVAILABLE: 'ok',
  PARTIAL: 'warn',
  MISSING: 'stop',
};

const VOCAB = {
  en: {
    level: { CRITICAL: 'Critical', HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' },
    status: {
      AWAITING_REVIEW: 'Awaiting review',
      MARKED_FOR_INSPECTION: 'Marked for inspection',
      UNDER_REVIEW: 'Under review',
      INFORMATION_REQUESTED: 'Information requested',
      INSPECTION_COMPLETED: 'Inspection completed',
      NO_ACTION_REQUIRED: 'No action required',
    },
    size: { MICRO: 'Micro', SMALL: 'Small', MEDIUM: 'Medium', LARGE: 'Large' },
    signalState: {
      ACTIVE: 'Firing',
      CLEAR: 'Quiet',
      UNAVAILABLE: 'Unavailable',
      DISABLED: 'Switched off',
    },
    fieldState: { AVAILABLE: 'Available', PARTIAL: 'Partial', MISSING: 'Missing' },
    confidence: {
      HIGH: 'Well evidenced',
      MEDIUM: 'Partly evidenced',
      LOW: 'Thin evidence',
      NONE: 'No evidence',
    },
    position: {
      BELOW: 'Below the expected range',
      WITHIN: 'Within the expected range',
      ABOVE: 'Above the expected range',
    },
    positionShort: { BELOW: 'Below', WITHIN: 'Within', ABOVE: 'Above' },
    registry: {
      MATCHED: 'Matched',
      PARTIAL: 'Partial match',
      UNREGISTERED: 'Not in the register',
    },
    sector: {
      beverage: 'Beverage',
      food: 'Packaged food',
      cosmetics: 'Cosmetics and personal care',
      cleaning: 'Detergent and cleaning',
      pharma: 'Pharmaceutical',
      electronics: 'Electrical and electronic',
      textile: 'Textile and apparel',
      chemicals: 'Chemical and industrial',
      agriculture: 'Agriculture and fresh produce',
      construction: 'Construction materials',
    },
    material: {
      plastic: 'Plastic',
      paper: 'Paper and cardboard',
      glass: 'Glass',
      metal: 'Metal',
      composite: 'Composite',
      wood: 'Wood',
    },
    field: {
      production: 'Production volume',
      import: 'Import volume',
      history: 'Declaration history',
      gtip: 'GTIP customs lines',
      field: 'Field inspection records',
      registry: 'Registry match',
    },
    fieldShort: {
      production: 'Prod',
      import: 'Imp',
      history: 'Hist',
      gtip: 'GTIP',
      field: 'Site',
      registry: 'Reg',
    },
    signal: {
      E1: 'Historical shortfall',
      E2: 'Structural shortfall',
      E3: 'Peer deviation',
      E4: 'Production and declaration mismatch',
      E5: 'Temporal inconsistency',
      E6: 'Numerical pattern',
      E7: 'Field contradiction',
      E8: 'Customs tariff evidence',
    },
  },
  tr: {
    level: { CRITICAL: 'Kritik', HIGH: 'Yüksek', MEDIUM: 'Orta', LOW: 'Düşük' },
    status: {
      AWAITING_REVIEW: 'İnceleme bekliyor',
      MARKED_FOR_INSPECTION: 'Denetime alındı',
      UNDER_REVIEW: 'İnceleniyor',
      INFORMATION_REQUESTED: 'Bilgi istendi',
      INSPECTION_COMPLETED: 'Denetim tamamlandı',
      NO_ACTION_REQUIRED: 'İşlem gerekmiyor',
    },
    size: { MICRO: 'Mikro', SMALL: 'Küçük', MEDIUM: 'Orta', LARGE: 'Büyük' },
    signalState: {
      ACTIVE: 'Tetiklendi',
      CLEAR: 'Sessiz',
      UNAVAILABLE: 'Çalıştırılamadı',
      DISABLED: 'Kapalı',
    },
    fieldState: { AVAILABLE: 'Mevcut', PARTIAL: 'Kısmi', MISSING: 'Eksik' },
    confidence: {
      HIGH: 'Güçlü dayanak',
      MEDIUM: 'Kısmi dayanak',
      LOW: 'Zayıf dayanak',
      NONE: 'Dayanak yok',
    },
    position: {
      BELOW: 'Beklenen aralığın altında',
      WITHIN: 'Beklenen aralık içinde',
      ABOVE: 'Beklenen aralığın üstünde',
    },
    positionShort: { BELOW: 'Altında', WITHIN: 'İçinde', ABOVE: 'Üstünde' },
    registry: {
      MATCHED: 'Eşleşti',
      PARTIAL: 'Kısmi eşleşme',
      UNREGISTERED: 'Sicilde kayıtlı değil',
    },
    sector: {
      beverage: 'İçecek',
      food: 'Ambalajlı gıda',
      cosmetics: 'Kozmetik ve kişisel bakım',
      cleaning: 'Deterjan ve temizlik',
      pharma: 'İlaç',
      electronics: 'Elektrik ve elektronik',
      textile: 'Tekstil ve hazır giyim',
      chemicals: 'Kimya ve sanayi',
      agriculture: 'Tarım ve taze ürün',
      construction: 'Yapı malzemeleri',
    },
    material: {
      plastic: 'Plastik',
      paper: 'Kâğıt ve karton',
      glass: 'Cam',
      metal: 'Metal',
      composite: 'Kompozit',
      wood: 'Ahşap',
    },
    field: {
      production: 'Üretim miktarı',
      import: 'İthalat miktarı',
      history: 'Beyan geçmişi',
      gtip: 'GTİP gümrük kalemleri',
      field: 'Saha denetim kayıtları',
      registry: 'Sicil eşleşmesi',
    },
    fieldShort: {
      production: 'Üre',
      import: 'İth',
      history: 'Geç',
      gtip: 'GTİP',
      field: 'Saha',
      registry: 'Sicil',
    },
    signal: {
      E1: 'Geçmişe göre eksik beyan',
      E2: 'Yapısal eksik beyan',
      E3: 'Emsalden sapma',
      E4: 'Üretim ile beyan uyumsuzluğu',
      E5: 'Dönemler arası tutarsızlık',
      E6: 'Sayısal örüntü',
      E7: 'Saha çelişkisi',
      E8: 'Gümrük tarife kanıtı',
    },
  },
};

function vocab(group, code) {
  if (code === null || code === undefined) return '--';
  return VOCAB[lang]?.[group]?.[code] ?? VOCAB.en[group]?.[code] ?? code;
}

export const levelLabel = (code) => vocab('level', code);
export const statusLabel = (code) => vocab('status', code);
export const sizeLabel = (code) => vocab('size', code);
export const signalStateLabel = (code) => vocab('signalState', code);
export const fieldStateLabel = (code) => vocab('fieldState', code);
export const confidenceLabel = (code) => vocab('confidence', code);
export const positionLabel = (code) => vocab('position', code);
export const positionShort = (code) => vocab('positionShort', code);
export const registryLabel = (code) => vocab('registry', code);
export const sectorLabel = (code) => vocab('sector', code);
export const materialLabel = (code) => vocab('material', code);
export const fieldLabel = (code) => vocab('field', code);
export const fieldShort = (code) => vocab('fieldShort', code);
export const signalName = (code) => vocab('signal', code);

export function qualityTone(score) {
  if (score >= 75) return 'ok';
  if (score >= 50) return 'warn';
  return 'stop';
}
