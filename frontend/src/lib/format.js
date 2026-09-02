const number = new Intl.NumberFormat('en-GB');
const oneDecimal = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return new Intl.NumberFormat('en-GB', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Tonnes, with a decimal only where it carries information. */
export function tonnes(value, { unit = true } = {}) {
  if (value === null || value === undefined) return unit ? 'No filing' : '--';
  const body = Math.abs(value) >= 100 ? number.format(Math.round(value)) : oneDecimal.format(value);
  return unit ? `${body} t` : body;
}

/** Turkish lira, abbreviated once the figure stops being readable in full. */
export function lira(value, { compact = true } = {}) {
  if (value === null || value === undefined) return '--';
  if (!compact) return `${number.format(Math.round(value))} TL`;
  if (Math.abs(value) >= 1_000_000_000) return `${oneDecimal.format(value / 1_000_000_000)}B TL`;
  if (Math.abs(value) >= 1_000_000) return `${oneDecimal.format(value / 1_000_000)}M TL`;
  if (Math.abs(value) >= 10_000) return `${number.format(Math.round(value / 1000))}K TL`;
  return `${number.format(Math.round(value))} TL`;
}

export function percent(value, digits = 0) {
  if (value === null || value === undefined) return '--';
  return `${num(value, digits)}%`;
}

export function date(value, { time = false } = {}) {
  if (!value) return '--';
  const parsed = new Date(value);
  const options = { day: '2-digit', month: 'short', year: 'numeric' };
  if (time) {
    options.hour = '2-digit';
    options.minute = '2-digit';
  }
  return new Intl.DateTimeFormat('en-GB', options).format(parsed);
}

export function relativeDays(days) {
  if (days === null || days === undefined) return '--';
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  if (days < 60) return 'last month';
  return `${Math.round(days / 30)} months ago`;
}

export function shortHash(value, length = 10) {
  if (!value) return '--';
  return `${value.slice(0, length)}…${value.slice(-4)}`;
}

// --------------------------------------------------------------------------
// Domain vocabulary
// --------------------------------------------------------------------------

export const LEVEL_TONE = {
  CRITICAL: 'stop',
  HIGH: 'warn',
  MEDIUM: 'cool',
  LOW: 'ok',
};

export const LEVEL_LABEL = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

export const STATUS_LABEL = {
  AWAITING_REVIEW: 'Awaiting review',
  MARKED_FOR_INSPECTION: 'Marked for inspection',
  UNDER_REVIEW: 'Under review',
  INFORMATION_REQUESTED: 'Information requested',
  INSPECTION_COMPLETED: 'Inspection completed',
  NO_ACTION_REQUIRED: 'No action required',
};

export const STATUS_TONE = {
  AWAITING_REVIEW: 'mute',
  MARKED_FOR_INSPECTION: 'warn',
  UNDER_REVIEW: 'cool',
  INFORMATION_REQUESTED: 'cool',
  INSPECTION_COMPLETED: 'ok',
  NO_ACTION_REQUIRED: 'ok',
};

export const SIZE_LABEL = {
  MICRO: 'Micro',
  SMALL: 'Small',
  MEDIUM: 'Medium',
  LARGE: 'Large',
};

export const SIGNAL_STATE_TONE = {
  ACTIVE: 'stop',
  CLEAR: 'ok',
  UNAVAILABLE: 'mute',
  DISABLED: 'mute',
};

export const SIGNAL_STATE_LABEL = {
  ACTIVE: 'Firing',
  CLEAR: 'Quiet',
  UNAVAILABLE: 'Unavailable',
  DISABLED: 'Switched off',
};

export const FIELD_STATE_TONE = {
  AVAILABLE: 'ok',
  PARTIAL: 'warn',
  MISSING: 'stop',
};

export const FIELD_STATE_LABEL = {
  AVAILABLE: 'Available',
  PARTIAL: 'Partial',
  MISSING: 'Missing',
};

export const CONFIDENCE_LABEL = {
  HIGH: 'Well evidenced',
  MEDIUM: 'Partly evidenced',
  LOW: 'Thin evidence',
  NONE: 'No evidence',
};

export const POSITION_LABEL = {
  BELOW: 'Below the expected range',
  WITHIN: 'Within the expected range',
  ABOVE: 'Above the expected range',
};

export const REGISTRY_LABEL = {
  MATCHED: 'Matched',
  PARTIAL: 'Partial match',
  UNREGISTERED: 'Not in the register',
};

export function qualityTone(score) {
  if (score >= 75) return 'ok';
  if (score >= 50) return 'warn';
  return 'stop';
}
