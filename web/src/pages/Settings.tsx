import { useState } from "react";
import { BudgetBar } from "../components/BudgetBar";
import { api, getToken, setToken } from "../lib/api";
import { enablePush } from "../lib/push";
import type { ScanConfig, Snapshot } from "../lib/types";

const SPORTS: Record<string, string> = {
  soccer_brazil_campeonato: "Brasileirão A",
  soccer_brazil_serie_b: "Brasileirão B",
  soccer_epl: "Premier League",
  soccer_spain_la_liga: "La Liga",
  soccer_italy_serie_a: "Serie A",
  soccer_germany_bundesliga: "Bundesliga",
  soccer_france_ligue_one: "Ligue 1",
  soccer_portugal_primeira_liga: "Primeira Liga",
  soccer_uefa_champs_league: "Champions League",
  soccer_conmebol_copa_libertadores: "Libertadores",
};

export function SettingsPage({
  snapshot, bankroll, setBankroll,
}: {
  snapshot: Snapshot;
  bankroll: number;
  setBankroll: (v: number) => void;
}) {
  const [cfg, setCfg] = useState<ScanConfig>(snapshot.config);
  const [saved, setSaved] = useState(false);
  const [pushMsg, setPushMsg] = useState<string | null>(null);
  const [tokenDraft, setTokenDraft] = useState(getToken());

  async function save(patch: Partial<ScanConfig>) {
    const next = { ...cfg, ...patch };
    setCfg(next);
    await api.patchConfig(patch);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function doPush() {
    const r = await enablePush();
    setPushMsg(r.ok ? "Push ativado neste dispositivo." : r.reason);
  }

  const toggleSport = (k: string) =>
    save({ sports: cfg.sports.includes(k) ? cfg.sports.filter((s) => s !== k) : [...cfg.sports, k] });

  return (
    <div className="page">
      <section className="panel">
        <h3>Orçamento de API</h3>
        <BudgetBar budget={snapshot.budget} />
        <p className="muted">
          Cada varredura custa 2 créditos por campeonato (mercado back + lay). Menos
          campeonatos selecionados significa varreduras mais frequentes.
        </p>
      </section>

      <section className="panel">
        <h3>Janela de operação</h3>
        <p className="muted">
          Fora desta faixa o motor não gasta crédito nenhum. Horário de Brasília.
        </p>
        <div className="grid2">
          <label>Início
            <input type="time" value={cfg.window_start}
                   onChange={(e) => save({ window_start: e.target.value })} /></label>
          <label>Fim
            <input type="time" value={cfg.window_end}
                   onChange={(e) => save({ window_end: e.target.value })} /></label>
        </div>
        <label className="switch big">
          <input type="checkbox" checked={cfg.enabled}
                 onChange={(e) => save({ enabled: e.target.checked })} />
          <span>Varredura automática ligada</span>
        </label>
      </section>

      <section className="panel">
        <h3>Campeonatos</h3>
        <div className="chips wrap">
          {Object.entries(SPORTS).map(([k, label]) => (
            <button key={k} className={`chip ${cfg.sports.includes(k) ? "on" : ""}`}
                    onClick={() => toggleSport(k)}>{label}</button>
          ))}
        </div>
      </section>

      <section className="panel">
        <h3>Notificações</h3>
        <label className="switch big">
          <input type="checkbox" checked={cfg.push_enabled}
                 onChange={(e) => save({ push_enabled: e.target.checked })} />
          <span>Enviar push dos sinais</span>
        </label>
        <label>EV mínimo para notificar
          <input type="number" step={0.01} value={cfg.min_ev_to_push}
                 onChange={(e) => save({ min_ev_to_push: +e.target.value })} /></label>
        <div className="row">
          <button className="btn" onClick={doPush}>Ativar neste dispositivo</button>
          <button className="btn ghost" onClick={() => api.pushTest().then(
            (r) => setPushMsg(`Enviado para ${r.sent} dispositivo(s).`))}>
            Testar
          </button>
        </div>
        {pushMsg && <p className="muted">{pushMsg}</p>}
        <p className="muted">
          No iPhone: abra no Safari, toque em Compartilhar → Adicionar à Tela de Início,
          e ative o push de dentro do app instalado. O Safari comum não recebe push.
        </p>
      </section>

      <section className="panel">
        <h3>Banca</h3>
        <label>Valor de referência para a calculadora (R$)
          <input type="number" step={50} value={bankroll}
                 onChange={(e) => setBankroll(+e.target.value)} /></label>
        <p className="muted">
          Fica só neste dispositivo. É usada para sugerir stake por Kelly fracionário (¼).
        </p>
      </section>

      <section className="panel">
        <h3>Acesso</h3>
        <label>Token do servidor
          <input type="password" value={tokenDraft}
                 onChange={(e) => setTokenDraft(e.target.value)} /></label>
        <button className="btn" onClick={() => { setToken(tokenDraft); location.reload(); }}>
          Salvar e reconectar
        </button>
        <p className="muted">O mesmo token do <code>.env</code>. Use no desktop e no celular.</p>
      </section>

      {saved && <div className="toast">Salvo</div>}
    </div>
  );
}
