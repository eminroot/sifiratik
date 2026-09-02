import { createContext, useContext, useEffect } from 'react';
import { AlertTriangle, Check, Inbox, X } from 'lucide-react';

export function PageHead({ eyebrow, icon: Icon, title, lede, note, children }) {
  return (
    <header className="page-head">
      <div>
        {eyebrow && (
          <div className="page-eyebrow">
            {Icon && <Icon size={14} strokeWidth={1.9} />}
            <span className="label">{eyebrow}</span>
          </div>
        )}
        <h1 className="display page-title">{title}</h1>
        {lede && <p className="page-lede">{lede}</p>}
        {note && <div className="lede-note">{note}</div>}
      </div>
      {children && <div className="row">{children}</div>}
    </header>
  );
}

export function Section({ icon: Icon, title, actions, children, first = false }) {
  return (
    <section className="section" style={first ? { marginTop: 0 } : undefined}>
      <div className="section-head">
        <h2 className="section-title">
          {Icon && <Icon size={15} strokeWidth={1.9} />}
          {title}
        </h2>
        {actions && <div className="row">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, warm = false, className = '', ...rest }) {
  return (
    <div className={`panel${warm ? ' panel-warm' : ''} ${className}`.trim()} {...rest}>
      <div className="panel-body">{children}</div>
    </div>
  );
}

export function Pill({ tone = 'mute', children }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

const FiguresContext = createContext(false);

/**
 * A run of figures reading as one instrument, not as a row of cards floating
 * apart from each other. The 1px grid gap draws the dividers, so the cells
 * stay separated however the row wraps.
 */
export function Figures({ columns = 3, rows = false, children, className = '' }) {
  const shape = rows ? 'rows' : `cols-${columns}`;
  return (
    <FiguresContext.Provider value>
      <div className={`figures ${shape} ${className}`.trim()}>{children}</div>
    </FiguresContext.Provider>
  );
}

/**
 * One figure. Inside <Figures> it is a cell of the strip; on its own it keeps
 * its own surface, so the component can still be dropped anywhere.
 */
export function Stat({ icon: Icon, label, value, unit, note, tone, children, large = false }) {
  const joined = useContext(FiguresContext);

  const body = (
    <>
      <div className="figure-head">
        <span className="label">{label}</span>
        {Icon && <Icon size={13} strokeWidth={1.9} />}
      </div>
      <div className={`figure-value${large ? ' lg' : ''}`}>
        <span>{value}</span>
        {unit && <span className="figure-unit">{unit}</span>}
      </div>
      {note && <div className={`figure-note${tone ? ` ${tone}` : ''}`}>{note}</div>}
      {children}
    </>
  );

  if (joined) return <div className="figure">{body}</div>;
  return <div className="figure figure-solo">{body}</div>;
}

export function Meter({ value, tone }) {
  return (
    <span className="meter" aria-hidden="true">
      <i className={tone} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </span>
  );
}

export function Empty({ icon: Icon = Inbox, title, note, action }) {
  return (
    <div className="empty">
      <div className="empty-glyph">
        <Icon size={19} strokeWidth={1.6} />
      </div>
      <div className="empty-title">{title}</div>
      {note && <p className="empty-note">{note}</p>}
      {action && <div style={{ marginTop: 18 }}>{action}</div>}
    </div>
  );
}

export function Loading({ rows = 3 }) {
  return (
    <div className="loading-page" aria-busy="true" aria-label="Loading">
      <div className="skeleton" style={{ height: 84 }} />
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton" style={{ height: index === 0 ? 168 : 116 }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <Empty
      icon={AlertTriangle}
      title="The service did not answer"
      note={error?.message ?? 'Check that the API is running, then try again.'}
      action={
        onRetry && (
          <button type="button" className="btn btn-ghost" onClick={onRetry}>
            Try again
          </button>
        )
      }
    />
  );
}

/**
 * One place decides what a page does while it waits, so no screen invents its
 * own loading or error treatment.
 */
export function Resource({ state, children, rows = 3 }) {
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading rows={rows} />;
  return children(state.data);
}

export function Toasts({ items }) {
  return (
    <div className="toast-dock" role="status" aria-live="polite">
      {items.map((item) => (
        <div key={item.id} className={`toast${item.tone === 'bad' ? ' bad' : ''}`}>
          {item.tone === 'bad' ? <AlertTriangle size={14} /> : <Check size={14} />}
          {item.message}
        </div>
      ))}
    </div>
  );
}

export function Sheet({ open, title, lede, onClose, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="scrim"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <aside className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-head spread">
          <div>
            <h2 className="sheet-title">{title}</h2>
            {lede && <p className="sheet-lede">{lede}</p>}
          </div>
          <button type="button" className="btn btn-quiet" onClick={onClose} aria-label="Close">
            <X size={16} strokeWidth={1.9} />
          </button>
        </div>
        {children}
        {footer && <div className="sheet-foot">{footer}</div>}
      </aside>
    </div>
  );
}
