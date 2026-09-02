import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle, ArrowUp, MessageSquare, RotateCcw, X } from 'lucide-react';

import { useApp } from '../App.jsx';
import { post, query, useApi } from '../lib/api.js';
import { useI18n } from '../lib/i18n.jsx';

/** Turns worth sending back as context. Older ones fall off the front. */
const HISTORY_DEPTH = 10;

/**
 * The assistant, docked at the foot of the window on the opposite side to the
 * navigation. It answers from a briefing the API assembles out of the current
 * period, so a figure it quotes is the same figure the page is showing.
 */
export default function Assistant() {
  const { period } = useApp();
  const { lang, t } = useI18n();
  const location = useLocation();

  const status = useApi(`/assistant/status${query({ period })}`, [period]);
  // Suggestions are written by the API, so the language belongs in the request
  // rather than in a lookup here.
  const suggestions = useApi(`/assistant/suggestions${query({ period, lang })}`, [period, lang]);

  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState('');
  const [thinking, setThinking] = useState(false);

  const scroller = useRef(null);
  const field = useRef(null);

  // The company being looked at, so "why is this one ranked first" has an
  // antecedent. Read off the path: the panel sits outside the router's routes.
  const companyMatch = location.pathname.match(/^\/companies\/(\d+)/);
  const companyId = companyMatch ? Number(companyMatch[1]) : null;

  useEffect(() => {
    if (!open) return;
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [turns, thinking, open]);

  useEffect(() => {
    if (open) field.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => event.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);

  const send = async (text) => {
    const message = text.trim();
    if (!message || thinking) return;

    const history = turns
      .filter((turn) => !turn.failed)
      .slice(-HISTORY_DEPTH)
      .map((turn) => ({ role: turn.role, content: turn.content }));

    setTurns((current) => [...current, { role: 'user', content: message }]);
    setDraft('');
    setThinking(true);

    try {
      const result = await post(`/assistant/chat${query({ period, lang })}`, {
        message,
        history,
        company_id: companyId,
      });
      setTurns((current) => [...current, { role: 'assistant', content: result.reply }]);
    } catch (error) {
      setTurns((current) => [
        ...current,
        { role: 'assistant', content: error.message, failed: true },
      ]);
    } finally {
      setThinking(false);
    }
  };

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send(draft);
    }
  };

  const ready = status.data?.enabled !== false;
  const openers = suggestions.data ?? [];

  return (
    <>
      <button
        type="button"
        className={`assistant-launcher${open ? ' open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={t(open ? 'assistant.close' : 'assistant.open')}
      >
        {open ? <X size={18} strokeWidth={2} /> : <MessageSquare size={18} strokeWidth={1.9} />}
      </button>

      {open && (
        <aside className="assistant" role="dialog" aria-label={t('assistant.title')}>
          <header className="assistant-head">
            <div className="grow">
              <div className="assistant-title">{t('assistant.title')}</div>
              <div className="assistant-sub">
                {ready
                  ? t('assistant.reading', { period: period ?? '' })
                  : t('assistant.notConfigured')}
              </div>
            </div>
            {turns.length > 0 && (
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setTurns([])}
                title={t('assistant.restart')}
              >
                <RotateCcw size={13} strokeWidth={1.9} />
              </button>
            )}
          </header>

          <div className="assistant-log" ref={scroller}>
            {!ready && (
              <div className="notice warn" style={{ margin: 0 }}>
                <AlertTriangle size={15} strokeWidth={1.9} />
                <div>
                  <div className="notice-title">{t('assistant.noKeyTitle')}</div>
                  {status.data?.detail}
                </div>
              </div>
            )}

            {ready && turns.length === 0 && (
              <div className="assistant-intro">
                <p>{t('assistant.intro')}</p>
                <div className="assistant-openers">
                  {openers.map((question) => (
                    <button
                      key={question}
                      type="button"
                      className="assistant-opener"
                      onClick={() => send(question)}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn, index) => (
              <div
                key={index}
                className={`assistant-turn ${turn.role}${turn.failed ? ' failed' : ''}`}
              >
                {turn.role === 'assistant' ? <Prose text={turn.content} /> : turn.content}
              </div>
            ))}

            {thinking && (
              <div className="assistant-turn assistant thinking" aria-live="polite">
                <span />
                <span />
                <span />
              </div>
            )}
          </div>

          <div className="assistant-composer">
            <textarea
              ref={field}
              rows={1}
              value={draft}
              disabled={!ready}
              placeholder={t(ready ? 'assistant.placeholder' : 'assistant.disabledPlaceholder')}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              aria-label={t('assistant.message')}
            />
            <button
              type="button"
              className="assistant-send"
              onClick={() => send(draft)}
              disabled={!ready || thinking || !draft.trim()}
              aria-label={t('assistant.send')}
            >
              <ArrowUp size={15} strokeWidth={2.2} />
            </button>
          </div>

          <footer className="assistant-foot">{t('assistant.foot')}</footer>
        </aside>
      )}
    </>
  );
}

/**
 * The model is told to answer in plain prose, so this only has to hold the
 * shape it does use: paragraphs, and the occasional short list.
 */
function Prose({ text }) {
  const blocks = text
    .replace(/\*\*/g, '')
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, index) => {
    const lines = block.split('\n');
    const bullets = lines.filter((line) => /^[-*•]\s+/.test(line.trim()));

    if (bullets.length === lines.length && bullets.length > 0) {
      return (
        <ul key={index}>
          {lines.map((line, item) => (
            <li key={item}>{line.trim().replace(/^[-*•]\s+/, '')}</li>
          ))}
        </ul>
      );
    }

    return <p key={index}>{block}</p>;
  });
}
