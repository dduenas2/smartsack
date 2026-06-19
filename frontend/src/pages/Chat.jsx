/**
 * Chat — asistente conversacional sobre la planta.
 *
 * UI:
 *  · Burbujas alineadas (usuario derecha en azul SK, asistente izquierda en blanco).
 *  · Indicador del modo activo (LLM real o fallback por keywords) en cabecera.
 *  · Sugerencias de prompts para arrancar la conversación.
 *  · Chips bajo cada respuesta del asistente con las tools que se ejecutaron.
 *  · Auto-scroll al último mensaje, Enter para enviar (Shift+Enter = salto).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import Card from '../components/common/Card.jsx';
import Spinner from '../components/common/Spinner.jsx';
import { getStatus, sendMessage } from '../api/chat.js';

const SUGGESTIONS = [
  '¿Cuántos sacos se produjeron ayer?',
  '¿Qué máquina tiene más paradas hoy?',
  '¿Cuál es el OEE de la planta?',
  '¿Qué alertas de retraso hay?',
  '¿Cuál es el OEE de TUB-01 en la última semana?',
];

const TOOL_LABEL = {
  get_production_stats: 'producción',
  get_machine_status: 'estado máquina',
  get_order_info: 'orden',
  get_oee_data: 'OEE',
  get_alerts: 'alertas ML',
};

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus({ llm_available: false }));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  async function send(text) {
    const trimmed = (text || '').trim();
    if (!trimmed || busy) return;

    const newUser = { role: 'user', content: trimmed };
    const history = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, newUser]);
    setInput('');
    setBusy(true);
    try {
      const resp = await sendMessage({ message: trimmed, history });
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.reply,
          toolCalls: resp.tool_calls || [],
          mode: resp.mode,
          error: resp.error,
        },
      ]);
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Error de red';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `❌ ${detail}`, error: detail, mode: 'fallback', toolCalls: [] },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const modePill = useMemo(() => {
    if (!status) return null;
    return status.llm_available ? (
      <span className="mono text-[10px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-state-running/10 text-state-running">
        LLM · {status.model}
      </span>
    ) : (
      <span className="mono text-[10px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-state-maintenance/10 text-state-maintenance">
        modo fallback (sin API key)
      </span>
    );
  }, [status]);

  return (
    <div className="space-y-4 animate-fade-in-up h-[calc(100vh-200px)] flex flex-col">
      <header className="flex items-end justify-between gap-3">
        <div>
          <p className="label-eyebrow">AI assistant</p>
          <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
            Asistente <span className="text-accent">·</span>{' '}
            <span className="text-ink-mid">Pregunta sobre la planta</span>
          </h1>
        </div>
        {modePill}
      </header>

      <Card className="flex-1 flex flex-col overflow-hidden p-0" accent="brand">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && <Welcome onPick={(s) => send(s)} suggestions={SUGGESTIONS} />}
          {messages.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}
          {busy && (
            <div className="flex items-center gap-2 pl-1">
              <Spinner size="sm" />
              <span className="mono text-[11px] uppercase tracking-widest2 text-ink-low">
                pensando...
              </span>
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="border-t border-bg-softline p-3 flex items-end gap-2"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            placeholder="Pregúntame sobre producción, OEE, máquinas, alertas..."
            className="flex-1 resize-none rounded-md border border-bg-line bg-white px-3 py-2 text-sm text-ink-high placeholder:text-ink-mute focus:border-accent focus:outline-none"
            style={{ maxHeight: 120 }}
          />
          <button
            type="submit"
            disabled={!input.trim() || busy}
            className="px-4 py-2 rounded-md bg-ink-high text-white text-sm font-medium hover:bg-brand-deep disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Enviar
          </button>
        </form>
      </Card>
    </div>
  );
}

function Welcome({ onPick, suggestions }) {
  return (
    <div className="flex flex-col items-center text-center gap-4 pt-10 pb-4">
      <div className="h-12 w-12 rounded-full bg-accent/10 flex items-center justify-center">
        <svg viewBox="0 0 24 24" className="h-6 w-6 text-accent" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M21 12a8 8 0 11-3.2-6.4L21 4l-1 4.2A8 8 0 0121 12z" strokeLinejoin="round" />
          <path d="M8 11h8M8 14h5" strokeLinecap="round" />
        </svg>
      </div>
      <div>
        <p className="text-ink-high text-base font-medium">¿En qué te ayudo?</p>
        <p className="text-ink-mid text-sm mt-1">
          Pregunta en lenguaje natural sobre producción, OEE, paradas, alertas o detalles de órdenes.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2 max-w-2xl">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="px-3 py-1.5 rounded-full border border-bg-line bg-white text-xs text-ink-mid hover:border-accent hover:text-accent transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ message }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? 'bg-ink-high text-white rounded-tr-sm'
            : 'bg-bg-base text-ink-high rounded-tl-sm border border-bg-softline'
        }`}
      >
        <p className="whitespace-pre-wrap">{renderMarkdownLite(message.content)}</p>
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-bg-softline">
            {message.toolCalls.map((tc, i) => (
              <span
                key={i}
                title={JSON.stringify(tc.arguments)}
                className="mono text-[9px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-accent/10 text-accent"
              >
                {TOOL_LABEL[tc.name] || tc.name}
              </span>
            ))}
            {message.error && (
              <span className="mono text-[9px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-state-stopped/10 text-state-stopped">
                err: {message.error}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Renderiza **bold** y saltos de línea sin meternos a un parser markdown completo.
 * Suficiente para el formato que devuelven el LLM y el fallback.
 */
function renderMarkdownLite(text) {
  if (!text) return null;
  const nodes = [];
  let buffer = '';
  let i = 0;
  let key = 0;
  while (i < text.length) {
    if (text.startsWith('**', i)) {
      const end = text.indexOf('**', i + 2);
      if (end > -1) {
        if (buffer) {
          nodes.push(buffer);
          buffer = '';
        }
        nodes.push(
          <strong key={`b-${key++}`} className="font-semibold">
            {text.slice(i + 2, end)}
          </strong>
        );
        i = end + 2;
        continue;
      }
    }
    buffer += text[i];
    i += 1;
  }
  if (buffer) nodes.push(buffer);
  return nodes;
}
