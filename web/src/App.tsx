import { useCallback, useEffect, useRef, useState } from "react";
import { api, connect, getToken, setToken, type WsEvent } from "./lib/api";
import { registerServiceWorker } from "./lib/push";
import { BacktestPage } from "./pages/Backtest";
import { CardPage } from "./pages/Card";
import { SettingsPage } from "./pages/Settings";
import { SignalsPage } from "./pages/Signals";
import type { Signal, Snapshot } from "./lib/types";

type Tab = "carta" | "sinais" | "backtest" | "config";
const BANKROLL_KEY = "roimax.bankroll";

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  // a carta é a tela principal: é o que ele abre uma vez por dia
  const [tab, setTab] = useState<Tab>("carta");
  const [scanning, setScanning] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);
  const [bankroll, setBankrollState] = useState(
    () => Number(localStorage.getItem(BANKROLL_KEY)) || 1000
  );
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const setBankroll = (v: number) => {
    setBankrollState(v);
    localStorage.setItem(BANKROLL_KEY, String(v));
  };

  const onEvent = useCallback((e: WsEvent) => {
    if (e.type === "snapshot") {
      setSnapshot(e.payload);
      return;
    }
    setSnapshot((prev) => {
      if (!prev) return prev;
      switch (e.type) {
        case "signals": {
          const incoming = e.payload as Signal[];
          const ids = new Set(incoming.map((s) => s.id));
          if (incoming.length) audioRef.current?.play().catch(() => {});
          return { ...prev, signals: [...incoming, ...prev.signals.filter((s) => !ids.has(s.id))] };
        }
        case "status": {
          const p = e.payload as Partial<Snapshot> & { status?: string };
          return { ...prev, ...p, status: p.status ?? prev.status };
        }
        case "config":
          return { ...prev, config: e.payload };
        case "card":
          return { ...prev, card: e.payload };
        default:
          return prev;
      }
    });
  }, []);

  useEffect(() => {
    registerServiceWorker();
    if (!getToken()) {
      setFatal("Configure o token para conectar.");
      return;
    }
    const refresh = () => api.state().then(setSnapshot).catch(() => {});
    refresh();

    // O WebSocket é um bônus: em hospedagem serverless ele não existe. A
    // busca periódica é o que garante que a carta apareça nos dois lugares —
    // e para uma carta por dia, 90 segundos é de sobra.
    const poll = setInterval(refresh, 90_000);
    const onFocus = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onFocus);

    const stop = connect(onEvent, setConnected);
    return () => {
      clearInterval(poll);
      document.removeEventListener("visibilitychange", onFocus);
      stop();
    };
  }, [onEvent]);

  async function scan() {
    setScanning(true);
    try {
      await api.scan();
    } catch (e) {
      setFatal(String(e));
    } finally {
      setScanning(false);
    }
  }

  if (fatal && !snapshot) return <TokenGate message={fatal} />;
  if (!snapshot) return <div className="boot">Conectando…</div>;

  return (
    <div className="app">
      <div className="shell">
      <header className="appbar">
        <div className="brand">
          <span className={`pulse ${connected ? "on" : "idle"}`}
                title={connected ? "tempo real" : "atualizando a cada 90s"} />
          <h1>ROI Max</h1>
        </div>
        <div className="appbar-right">
          {snapshot.status === "scanning" && <span className="scanning">varrendo…</span>}
          <span className="credits">{snapshot.budget.remaining}c</span>
          <button className="btn small" onClick={scan} disabled={scanning || !snapshot.live_odds_enabled}>
            Varrer
          </button>
        </div>
      </header>

      <main className="content">
        {tab === "carta" && (
          <CardPage
            card={snapshot.card}
            clv={snapshot.clv}
            liveOdds={snapshot.live_odds_enabled}
            onRebuild={async () => {
              const c = await api.buildCard();
              setSnapshot((p) => (p ? { ...p, card: c } : p));
            }}
          />
        )}
        {tab === "sinais" && (
          <SignalsPage
            snapshot={snapshot}
            bankroll={bankroll}
            scanning={scanning}
            onScan={scan}
            onAct={(id) => api.act(id).catch(() => {})}
          />
        )}
        {tab === "backtest" && <BacktestPage />}
        {tab === "config" && (
          <SettingsPage snapshot={snapshot} bankroll={bankroll} setBankroll={setBankroll} />
        )}
      </main>
      </div>

      {/* Uma barra só, que o CSS coloca embaixo no celular e na lateral no
          desktop. Abas de celular esticadas numa tela de 27" desperdiçam a
          tela inteira e escondem o que importa atrás de um clique. */}
      <nav className="tabbar">
        {(["carta", "sinais", "backtest", "config"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            <span className="tab-icon" aria-hidden="true">
              {t === "carta" ? "◆" : t === "sinais" ? "◈" : t === "backtest" ? "◫" : "⚙"}
            </span>
            <span className="tab-label">
              {t === "carta" ? "Carta" : t === "sinais" ? "Sinais"
                : t === "backtest" ? "Backtest" : "Config"}
            </span>
          </button>
        ))}
      </nav>

      {/* bipe curto ao chegar sinal; silencioso se o navegador bloquear */}
      <audio ref={audioRef} preload="auto" src="data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=" />
    </div>
  );
}

function TokenGate({ message }: { message: string }) {
  const [t, setT] = useState("");
  const recusado = message.includes("401");

  const entrar = () => {
    if (!t.trim()) return;
    setToken(t);
    location.reload();
  };

  return (
    <div className="gate">
      <h1>ROI Max</h1>
      <p className="muted">
        {recusado
          ? "Token recusado pelo servidor. Confira se copiou inteiro."
          : "Digite o token para conectar."}
      </p>
      <input
        type="password"
        placeholder="token do servidor"
        value={t}
        autoFocus
        onChange={(e) => setT(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && entrar()}
      />
      <button className="btn primary" onClick={entrar} disabled={!t.trim()}>
        Entrar
      </button>
      <p className="hint">
        É o <code>ROIMAX_TOKEN</code> do seu <code>.env</code>, o mesmo que está
        nas variáveis da Vercel. Fica salvo neste aparelho.
      </p>
    </div>
  );
}
