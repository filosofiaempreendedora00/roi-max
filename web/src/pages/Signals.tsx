import { useMemo, useState } from "react";
import { SignalCard } from "../components/SignalCard";
import { KIND_PT } from "../lib/format";
import type { Signal, Snapshot } from "../lib/types";

const FILTERS = ["todos", "VALUE_BACK", "VALUE_LAY", "ARBITRAGE", "STEAM", "WIDE_SPREAD"] as const;

export function SignalsPage({
  snapshot, bankroll, onAct, onScan, scanning,
}: {
  snapshot: Snapshot;
  bankroll: number;
  onAct: (id: string) => void;
  onScan: () => void;
  scanning: boolean;
}) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("todos");
  const [onlyLive, setOnlyLive] = useState(true);

  const visible = useMemo(() => {
    const now = Date.now();
    return snapshot.signals.filter((s: Signal) => {
      if (filter !== "todos" && s.kind !== filter) return false;
      if (onlyLive && s.expires_at && new Date(s.expires_at).getTime() < now) return false;
      return true;
    });
  }, [snapshot.signals, filter, onlyLive]);

  return (
    <>
      <div className="toolbar">
        <div className="chips">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`chip ${filter === f ? "on" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "todos" ? "Todos" : KIND_PT[f]}
            </button>
          ))}
        </div>
        <label className="switch">
          <input type="checkbox" checked={onlyLive} onChange={(e) => setOnlyLive(e.target.checked)} />
          <span>só válidos</span>
        </label>
      </div>

      {!snapshot.live_odds_enabled && (
        <div className="notice">
          <b>Modo replay.</b> Sem <code>ODDS_API_KEY</code> no <code>.env</code>, o motor
          não busca odds ao vivo. O backtest funciona normalmente — e é por onde começar.
        </div>
      )}

      {snapshot.last_error && <div className="notice err">{snapshot.last_error}</div>}

      {visible.length === 0 ? (
        <div className="empty">
          <p>Nenhum sinal {onlyLive ? "válido " : ""}no momento.</p>
          <p className="muted">
            Silêncio é o estado normal. O mercado da Betfair é eficiente na maior parte
            do tempo — sinal a toda hora seria sintoma de gatilho frouxo, não de
            oportunidade.
          </p>
          <button className="btn primary" onClick={onScan} disabled={scanning}>
            {scanning ? "Varrendo…" : "Varrer agora (gasta crédito)"}
          </button>
        </div>
      ) : (
        <div className="feed">
          {visible.map((s) => (
            <SignalCard
              key={s.id}
              signal={s}
              commission={snapshot.commission}
              bankroll={bankroll}
              onAct={onAct}
            />
          ))}
        </div>
      )}
    </>
  );
}
