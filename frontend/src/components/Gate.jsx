import { useCallback, useEffect, useState } from 'react';

import SignIn from './SignIn.jsx';
import { SESSION_LOST, get } from '../lib/api.js';

/**
 * Decides whether to draw the interface or the sign-in form.
 *
 * The answer comes from the service, not from anything kept in the browser: a
 * flag in localStorage saying "signed in" would be a flag anybody can set, and
 * it would be wrong anyway the moment a session expired. `/auth/status` is the
 * only thing that knows, and it is cheap.
 *
 * On a checkout with no credentials configured the service reports the gate
 * as off and this renders the interface immediately, so local work is
 * unchanged by any of it.
 */
export default function Gate({ children }) {
  const [session, setSession] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    get('/auth/status')
      .then((data) => {
        setSession(data);
        setFailed(false);
      })
      .catch(() => setFailed(true));
  }, []);

  useEffect(load, [load]);

  // A session that ends while the tab is open — expired, or the service
  // restarted without a fixed signing secret — puts the form back rather than
  // leaving every panel showing an error the viewer cannot act on.
  useEffect(() => {
    const lost = () =>
      setSession((current) => (current ? { ...current, authenticated: false } : current));
    window.addEventListener(SESSION_LOST, lost);
    return () => window.removeEventListener(SESSION_LOST, lost);
  }, []);

  // Nothing is drawn until the answer arrives. A flash of the interface before
  // the form would be a flash of whatever the last render had in it.
  if (!session && !failed) return null;

  // The status endpoint is reachable without a session, so a failure here is
  // the service being unreachable. Offering the form is the useful answer:
  // signing in is what the viewer came to do, and it will fail visibly.
  if (failed || (session.enabled && !session.authenticated)) {
    return <SignIn onSignedIn={setSession} />;
  }

  return children;
}
