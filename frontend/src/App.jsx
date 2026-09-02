import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  ClipboardList,
  Gauge,
  LayoutGrid,
  Leaf,
  Moon,
  Scale,
  ScrollText,
  Sun,
  Target,
} from 'lucide-react';

import Assistant from './components/Assistant.jsx';
import { Dock, DockIcon, DockItem, DockLabel } from './components/Dock.jsx';
import Topbar from './components/Topbar.jsx';
import { Toasts } from './components/ui.jsx';
import { useApi } from './lib/api.js';

import Overview from './pages/Overview.jsx';
import Queue from './pages/Queue.jsx';
import Company from './pages/Company.jsx';
import CompanyHistory from './pages/CompanyHistory.jsx';
import Quality from './pages/Quality.jsx';
import Impact from './pages/Impact.jsx';
import Pilot from './pages/Pilot.jsx';
import Trail from './pages/Trail.jsx';
import Transparency from './pages/Transparency.jsx';

const DESTINATIONS = [
  { to: '/', label: 'Overview', icon: LayoutGrid },
  { to: '/queue', label: 'Inspection queue', icon: ClipboardList },
  { to: '/data-quality', label: 'Data quality', icon: Gauge },
  { to: '/impact', label: 'Climate impact', icon: Leaf },
  { to: '/pilot', label: 'Antalya pilot', icon: Target },
  { to: '/audit-trail', label: 'Audit trail', icon: ScrollText },
  { to: '/transparency', label: 'How this works', icon: Scale },
];

const AppContext = createContext(null);

export function useApp() {
  return useContext(AppContext);
}

function readTheme() {
  if (typeof document === 'undefined') return 'light';
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();

  const [theme, setTheme] = useState(readTheme);
  const [period, setPeriod] = useState(null);
  const [toasts, setToasts] = useState([]);

  const reference = useApi('/meta/reference');

  useEffect(() => {
    if (!period && reference.data?.period) setPeriod(reference.data.period);
  }, [period, reference.data]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('gus.theme', theme);
    } catch {
      // A browser that refuses storage still gets the theme for this session.
    }
  }, [theme]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  const toast = useCallback((message, tone = 'ok') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(() => setToasts((current) => current.filter((item) => item.id !== id)), 3600);
  }, []);

  const value = useMemo(
    () => ({ period, reference: reference.data, toast }),
    [period, reference.data, toast],
  );

  // Modified clicks keep working, so a destination can open in a new tab.
  const follow = (to) => (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate(to);
  };

  const isLive = (to) =>
    to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);

  return (
    <AppContext.Provider value={value}>
      <div className="shell">
        <Topbar />
        <main className="main">
          <div className="route" key={location.pathname}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/queue" element={<Queue />} />
              <Route path="/companies/:companyId" element={<Company />} />
              <Route path="/companies/:companyId/history" element={<CompanyHistory />} />
              <Route path="/data-quality" element={<Quality />} />
              <Route path="/impact" element={<Impact />} />
              <Route path="/pilot" element={<Pilot />} />
              <Route path="/audit-trail" element={<Trail />} />
              <Route path="/transparency" element={<Transparency />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>
        </main>

        <Dock>
          {DESTINATIONS.map(({ to, label, icon: Icon }) => (
            <DockItem key={to} href={to} onClick={follow(to)} active={isLive(to)}>
              <DockLabel>{label}</DockLabel>
              <DockIcon>
                <Icon strokeWidth={1.75} />
              </DockIcon>
            </DockItem>
          ))}

          <span className="dock-sep" aria-hidden="true" />

          <DockItem
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label="Switch theme"
          >
            <DockLabel>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</DockLabel>
            <DockIcon>
              {theme === 'dark' ? <Sun strokeWidth={1.75} /> : <Moon strokeWidth={1.75} />}
            </DockIcon>
          </DockItem>
        </Dock>

        <Assistant />
        <Toasts items={toasts} />
      </div>
    </AppContext.Provider>
  );
}

function NotFound() {
  return (
    <div className="page">
      <div className="empty" style={{ marginTop: 60 }}>
        <div className="empty-glyph">
          <Scale size={19} strokeWidth={1.6} />
        </div>
        <div className="empty-title">No such page</div>
        <p className="empty-note">The address does not match anything in the platform.</p>
        <div style={{ marginTop: 18 }}>
          <Link className="btn btn-ghost" to="/">
            Back to overview
          </Link>
        </div>
      </div>
    </div>
  );
}
