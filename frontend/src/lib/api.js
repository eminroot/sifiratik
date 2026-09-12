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

/**
 * Fired when the service says the session is gone — it expired, or the
 * service restarted without a fixed signing secret. Every request funnels
 * through `parse`, so one listener in App puts the sign-in form back up
 * instead of each page inventing its own way to fail.
 */
export const SESSION_LOST = 'gus:session-lost';

// The sign-in endpoints answer 401 as part of their normal work; announcing a
// lost session there would fight with the form the viewer is already using.
const AUTH_PATHS = '/auth/';

async function parse(response, path = '') {
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // A proxy error page is HTML, not JSON; report the status, not a parse failure.
  }
  if (!response.ok) {
    if (response.status === 401 && !path.includes(AUTH_PATHS)) {
      window.dispatchEvent(new CustomEvent(SESSION_LOST));
    }
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

// The session cookie is same-origin, which is what fetch sends by default;
// saying so keeps it from depending on that default.
const WITH_SESSION = { credentials: 'same-origin' };

export function get(path, signal) {
  return fetch(`${BASE}${path}`, { ...WITH_SESSION, signal }).then((response) =>
    parse(response, path),
  );
}

export function post(path, body) {
  return fetch(`${BASE}${path}`, {
    ...WITH_SESSION,
    method: 'POST',
    headers: writeHeaders(),
    body: JSON.stringify(body ?? {}),
  }).then((response) => parse(response, path));
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
