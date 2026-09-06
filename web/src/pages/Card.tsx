import { useState } from "react";
import { api } from "../lib/api";
import { num, odds as fmtOdds, outcomeTeam, pct } from "../lib/format";
import type { CardEntry, ClvStats, DailyCard } from "../lib/types";

export function CardPage({
  card, clv, liveOdds, onRebuild,
}: {
  card: DailyCard | null;
  clv: ClvStats;
  liveOdds: boolean;
  onRebuild: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  async function rebuild() {
    setBusy(true);
    try { await onRebuild(); } finally { setBusy(false); }
  }

  // Sem chave de API não existe carta possível, e dizer "nenhuma entrada hoje"
  // faria parecer que o motor olhou o mercado e não achou nada. São coisas
  // muito diferentes: uma é resultado, a outra é falta de configuração.
  if (!liveOdds) {
    return (
      <div className="page">
        <section className="panel setup">
          <h3>Falta conectar uma fonte de odds</h3>
          <p className="muted">
            O app está no ar e o motor funciona, mas não há de onde ler preços.
            Sem isso não existe carta — nem hoje nem em nenhum dia.
          </p>
          <ol className="steps">
            <li>
              Crie uma chave gratuita em{" "}
              <a href="https://the-odds-api.com" target="_blank" rel="noreferrer">
                the-odds-api.com
              </a>{" "}
              (500 créditos por mês, sem cartão)
            </li>
            <li>Cole em <code>ODDS_API_KEY</code> no arquivo <code>.env</code></li>
            <li>Reinicie o servidor</li>
          </ol>
          <p className="muted">
            Enquanto isso, a aba <b>Backtest</b> funciona por completo — ela usa
            o histórico gratuito e não depende de chave nenhuma.
          </p>
        </section>
        <ClvPanel clv={clv} />
      </div>
    );
  }

  return (
    <div className="page">
      {!card || card.entries.length === 0 ? (
        <div className="panel empty">
          <h3>Sem entradas hoje</h3>
          <p className="muted">{card?.note ?? "A carta ainda não foi montada."}</p>
          <button className="btn primary wide" onClick={rebuild} disabled={busy}>
            {busy ? "Montando…" : "Montar carta agora"}
          </button>
        </div>
      ) : (
        <>
          <div className="card-head panel">
            <div>
              <h3>Carta de {card.date}</h3>
              <p className="muted">
                {card.entries.length} entradas · R$ {num(card.total_stake)} no total ·
                de {card.scanned_events} jogos varridos
              </p>
            </div>
            <button className="btn small" onClick={rebuild} disabled={busy}>
              Remontar
            </button>
          </div>

          {card.entries.map((e) => <Entry key={e.signal.id} entry={e} />)}

          <p className="reading">
            Todas as entradas são pré-jogo e liquidam no fim da partida. Não há
            nada para acompanhar depois de confirmar.
          </p>
        </>
      )}

      <ClvPanel clv={clv} />
    </div>
  );
}

function Entry({ entry }: { entry: CardEntry }) {
  const s = entry.signal;
  const isBack = s.side === "back";
  const [done, setDone] = useState(false);

  return (
    <article className={`panel entry ${s.side} ${done ? "done" : ""}`}>
      <header className="entry-head">
        <span className="rank">#{entry.rank}</span>
        <span className={`badge side-${s.side}`}>{s.side.toUpperCase()}</span>
        <span className="league">{s.league || "—"}</span>
      </header>

      <h3 className="match">{s.event_label}</h3>
      <p className="pick-on">
        {isBack ? "a favor de" : "contra"}{" "}
        <b>{outcomeTeam(s.event_label, s.outcome)}</b>
      </p>

      <div className="entry-grid">
        <div className="big">
          <span>Entre a</span>
          <b>{fmtOdds(s.market_odds)}</b>
        </div>
        <div className="big limit">
          <span>{isBack ? "Não abaixo de" : "Não acima de"}</span>
          <b>{fmtOdds(entry.limit_price)}</b>
        </div>
        <div className="big">
          <span>{isBack ? "Stake" : "Stake (lay)"}</span>
          <b>R$ {num(entry.stake, 0)}</b>
        </div>
      </div>

      <p className="muted small">
        {entry.reason} EV {num(s.ev, 3)} · confiança {Math.round(s.confidence * 100)}%
      </p>

      <div className="actions">
        <a className="btn primary" href={s.deeplink} target="_blank" rel="noreferrer">
          Abrir na Betfair ↗
        </a>
        <button
          className={`btn ${done ? "" : "ghost"}`}
          onClick={() => { setDone(true); api.markPlaced(s.id).catch(() => {}); }}
        >
          {done ? "✓ Feita" : "Marcar feita"}
        </button>
      </div>
    </article>
  );
}

function ClvPanel({ clv }: { clv: ClvStats }) {
  const good = clv.n_with_closing >= 20 && clv.mean_clv > 0;
  const bad = clv.n_with_closing >= 20 && clv.mean_clv <= 0;

  return (
    <section className={`panel clv ${good ? "ok" : bad ? "bad" : ""}`}>
      <h3>Seu CLV real</h3>
      <div className="stats">
        <div className="stat">
          <span className="stat-label">CLV médio</span>
          <b className={`stat-value ${clv.mean_clv > 0 ? "pos" : clv.mean_clv < 0 ? "neg" : ""}`}>
            {clv.n_with_closing ? pct(clv.mean_clv, 2) : "—"}
          </b>
        </div>
        <div className="stat">
          <span className="stat-label">Bateu o fecho</span>
          <b className={`stat-value ${clv.beat_rate >= 52 ? "pos" : clv.beat_rate ? "neg" : ""}`}>
            {clv.n_with_closing ? `${num(clv.beat_rate, 1)}%` : "—"}
          </b>
        </div>
        <div className="stat">
          <span className="stat-label">Palpites</span>
          <b className="stat-value">{clv.n}</b>
          <span className="stat-sub">{clv.n_with_closing} com fechamento</span>
        </div>
        <div className="stat">
          <span className="stat-label">Odd média</span>
          <b className="stat-value">{clv.mean_odds ? num(clv.mean_odds) : "—"}</b>
        </div>
      </div>
      <p className="muted">{clv.veredito}</p>
      <p className="reading">
        O CLV mede se você pegou preço melhor que o fechamento. Ele dá sinal em
        dezenas de apostas, enquanto o ROI precisa de milhares — é por isso que
        ele, e não o lucro, é o painel de controle. Acima de 52% sustenta lucro
        no longo prazo.
      </p>
    </section>
  );
}
