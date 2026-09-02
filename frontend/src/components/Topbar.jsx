import { Link } from 'react-router-dom';

/**
 * Identity, and nothing else. Navigation is in the dock, and the period is
 * whatever the API reports as current.
 */
export default function Topbar() {
  return (
    <header className="topbar">
      <Link className="brand" to="/">
        <span>
          <span className="brand-mark">GÜS-DEDEKTİV</span>
          <span className="brand-sub">Inspection prioritisation</span>
        </span>
      </Link>
    </header>
  );
}
