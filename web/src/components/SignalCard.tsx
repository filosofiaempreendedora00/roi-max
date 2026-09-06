import { useState } from "react";
import { KIND_PT, ago, num, odds as fmtOdds, outcomeTeam, pct, until } from "../lib/format";
import type { Signal } from "../lib/types";
import { StakeCalc } from "./StakeCalc";

export function SignalCard({
  signal, commission, bankroll, onAct,
}: {
  signal: Signal;
  commission: number;
  bankroll: number;
  onAct: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [acted, setActed] = useState(false);
  const ttl = until(signal.expires_at);
  const expired = signal.expires_at !== null && ttl === null;

  return (
    <article className={`card ${signal.side} ${expired ? "expired" : ""}`}>
      <header className="card-top">
        <div className="badges">
          <span className={`badge side-${signal.side}`}>{signal.side.toUpperCase()}</span>
          <span className="badge kind">{KIND_PT[signal.kind] ?? signal.kind}</span>
        </div>
        <div className="timing">
          {ttl ? <span className="ttl">expira em {ttl}</span> : <span className="ttl dead">expirado</span>}
          <span className="dot">·</span>
          <span>{ago(signal.ts)} atrás</span>
        </div>
      </header>

      <h3 className="match">{signal.event_label}</h3>
      <p className="league">{signal.league || "—"}</p>

      <div className="price-row">
        <div className="price-main">
          <span className="price-label">{outcomeTeam(signal.event_label, signal.outcome)}</span>
          <span className="price-odds">{fmtOdds(signal.market_odds)}</span>
        </div>
        <div className="price-meta">
          <div>
            <span>justo</span>
            <b>{fmtOdds(signal.fair_odds)}</b>
          </div>
          <div>
            <span>edge</span>
            <b className={signal.edge_pct > 0 ? "pos" : "neg"}>{pct(signal.edge_pct)}</b>
          </div>
          <div>
            <span>EV</span>
            {/* Steam e book fino não carregam EV: são avisos, não valor
                calculado. Mostrar 0,000 em vermelho leria como EV ruim. */}
            {signal.ev === 0 ? (
              <b className="na">—</b>
            ) : (
              <b className={signal.ev > 0 ? "pos" : "neg"}>{num(signal.ev, 3)}</b>
            )}
          </div>
        </div>
      </div>

      <div className="confidence">
        <div className="conf-bar" style={{ width: `${Math.round(signal.confidence * 100)}%` }} />
        <span className="conf-text">
          confiança {Math.round(signal.confidence * 100)}% · {signal.reference}
        </span>
      </div>

      <div className="actions">
        <a
          className="btn primary"
          href={signal.deeplink}
          target="_blank"
          rel="noreferrer"
          onClick={() => { setActed(true); onAct(signal.id); }}
        >
          Abrir na Betfair ↗
        </a>
        <button className="btn ghost" onClick={() => setOpen((v) => !v)}>
          {open ? "Fechar" : "Calcular"}
        </button>
      </div>

      {open && (
        <StakeCalc
          side={signal.side}
          odds={signal.market_odds}
          commission={commission}
          kelly={signal.kelly}
          bankroll={bankroll}
        />
      )}

      {signal.notes && <p className="notes">{signal.notes}</p>}
      {acted && <p className="acted">Marcado como aberto neste dispositivo.</p>}
    </article>
  );
}
