import { useCallback, useEffect, useRef, useState } from 'react';

const BASE = '/api';

// The key lives for this tab only. A credential that outlives the tab is one
// the next person at the desk inherits.
const KEY_STORAGE = 'gus.apiKey';
let memoryKey = '';

export function getApiKey() {
  try {
    return sessionStorage.getItem(KEY_STORAGE) ?? memoryKey;
  } catch {
    return memoryKey;
  }
}

export function setApiKey(value) {
  memoryKey = value || '';
  try {
    if (memoryKey) sessionStorage.setItem(KEY_STORAGE, memoryKey);
    else sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    // No storage: the key is held in memory until the page is closed.
  }
}

class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
  }
}

async function parse(response) {
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // A proxy error page is HTML, not JSON; report the status, not a parse failure.
  }
  if (!response.ok) {
    const detail = body?.detail;
    throw new ApiError(
      response.status,
      typeof detail === 'string' ? detail : `Request failed with ${response.status}`,
    );
  }
  return body;
}

/** Writing requests carry the key when one has been entered; reading ones never do. */
function writeHeaders() {
  const key = getApiKey();
  return key
    ? { 'Content-Type': 'application/json', 'X-API-Key': key }
    : { 'Content-Type': 'application/json' };
}

export function query(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      if (!value.length) return;
      search.set(key, value.join(','));
      return;
    }
    search.set(key, value);
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export function get(path, signal) {
  return fetch(`${BASE}${path}`, { signal }).then(parse);
}

export function post(path, body) {
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: writeHeaders(),
    body: JSON.stringify(body ?? {}),
  }).then(parse);
}

/**
 * Fetch a path and keep the previous payload on screen while the next one
 * loads, so changing a filter never blanks the table underneath the operator.
 */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [nonce, setNonce] = useState(0);
  const live = useRef(true);

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true, error: null }));

    get(path, controller.signal)
      .then((data) => {
        if (live.current) setState({ data, error: null, loading: false });
      })
      .catch((error) => {
        if (error.name === 'AbortError' || !live.current) return;
        setState({ data: null, error, loading: false });
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce, ...deps]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  return { ...state, reload };
}

export { ApiError };
