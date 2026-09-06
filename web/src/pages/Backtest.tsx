import { useState } from "react";
import { Sparkline } from "../components/Sparkline";
import { api } from "../lib/api";
import { num } from "../lib/format";
import type { BacktestResponse } from "../lib/types";

const DIVS: Record<string, string> = {
  E0: "Premier League", E1: "Championship", SP1: "La Liga", I1: "Serie A",
  D1: "Bundesliga", F1: "Ligue 1", N1: "Eredivisie", P1: "Primeira Liga",
  B1: "Jupiler", T1: "Super Lig", SC0: "Escócia",
};
const SEASONS = ["2122", "2223", "2324", "2425", "2526"];

export function BacktestPage() {
  const [divs, setDivs] = useState<string[]>(["E0", "SP1", "I1", "D1", "F1"]);
  const [seasons, setSeasons] = useState<string[]>(["2223", "2324", "2425", "2526"]);
  const [minEdge, setMinEdge] = useState(4);
  const [minEv, setMinEv] = useState(0.02);
  const [minBooks, setMinBooks] = useState(3);
  const [running, setRunning] = useState(false);
  const [res, setRes] = useState<BacktestResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (arr: string[], set: (v: string[]) => void, v: string) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  async function run() {
    setRunning(true);
    setErr(null);
    try {
      setRes(await api.backtest({
        divisions: divs, seasons, min_edge_pct: minEdge,
        min_ev: minEv, min_books: minBooks,
      }));
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  }

  const s = res?.resumo;

  return (
    <div className="page">
      <div className="notice">
        Dados gratuitos do football-data.co.uk, com as odds reais de abertura e
        fechamento da Betfair Exchange. Não consome nenhum crédito de API.
      </div>

      <section className="panel">
        <h3>Ligas</h3>
        <div className="chips wrap">
          {Object.entries(DIVS).map(([k, label]) => (
            <button key={k} className={`chip ${divs.includes(k) ? "on" : ""}`}
                    onClick={() => toggle(divs, setDivs, k)}>{label}</button>
          ))}
        </div>

        <h3>Temporadas</h3>
        <div className="chips wrap">
          {SEASONS.map((k) => (
            <button key={k} className={`chip ${seasons.includes(k) ? "on" : ""}`}
                    onClick={() => toggle(seasons, setSeasons, k)}>
              {`20${k.slice(0, 2)}/${k.slice(2)}`}
            </button>
          ))}
        </div>

        <h3>Gatilhos</h3>
        <div className="grid3">
          <label>Edge mínimo (%)
            <input type="number" step={0.5} value={minEdge}
                   onChange={(e) => setMinEdge(+e.target.value)} /></label>
          <label>EV mínimo
            <input type="number" step={0.01} value={minEv}
                   onChange={(e) => setMinEv(+e.target.value)} /></label>
          <label>Casas mínimas
            <input type="number" step={1} value={minBooks}
                   onChange={(e) => setMinBooks(+e.target.value)} /></label>
        </div>

        <button className="btn primary wide" onClick={run} disabled={running || !divs.length}>
          {running ? "Rodando… (baixa os CSVs na primeira vez)" : "Rodar backtest"}
        </button>
      </section>

      {err && <div className="notice err">{err}</div>}
      {res?.erro && <div className="notice err">{res.erro}</div>}

      {s && (
        <section className="panel">
          <h3>Resultado</h3>
          <div className="stats">
            <Stat label="Apostas" value={String(s.apostas)} sub={`de ${s.partidas_analisadas} jogos`} />
            <Stat label="ROI" value={`${num(s.roi_pct)}%`} tone={s.roi_pct >= 0 ? "pos" : "neg"} />
            <Stat label="Lucro" value={`${num(s.lucro_unidades)}u`} tone={s.lucro_unidades >= 0 ? "pos" : "neg"} />
            <Stat label="Acerto" value={`${num(s.acerto_pct)}%`} sub={`odd média ${num(s.odd_media)}`} />
            <Stat label="CLV médio" value={`${num(s.clv_medio_pct, 2)}%`}
                  tone={s.clv_medio_pct >= 0 ? "pos" : "neg"} sub="vs fechamento" />
            <Stat label="Bateu o fecho" value={`${num(s.clv_positivo_pct)}%`}
                  tone={s.clv_positivo_pct >= 52 ? "pos" : "neg"} sub="das apostas" />
            <Stat label="Drawdown" value={`${num(s.drawdown_max_unidades)}u`} tone="neg" />
            <Stat label="Seleção" value={`${num(s.taxa_de_selecao_pct)}%`} sub="dos jogos" />
          </div>

          <p className="reading">
            Leia o <b>CLV</b> antes do ROI. Bater o preço de fechamento em mais de ~52%
            das entradas é o que separa edge de sorte — ROI positivo com CLV negativo
            em amostra pequena costuma ser variância, e evapora.
          </p>

          {res.curva && <Sparkline data={res.curva} />}

          {res.controle_favorito && (
            <p className="muted">
              Controle (back cego no favorito): {res.controle_favorito.apostas} apostas,
              ROI {num(res.controle_favorito.roi_pct)}%. Sua estratégia precisa bater isto com folga.
            </p>
          )}

          <h4>Por liga</h4>
          <table className="tbl">
            <thead><tr><th>Liga</th><th>n</th><th>ROI</th><th>P&L</th></tr></thead>
            <tbody>
              {Object.entries(s.por_liga).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td><td>{v.n}</td>
                  <td className={v.roi_pct >= 0 ? "pos" : "neg"}>{num(v.roi_pct)}%</td>
                  <td className={v.pnl >= 0 ? "pos" : "neg"}>{num(v.pnl)}u</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "pos" | "neg";
}) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <b className={`stat-value ${tone ?? ""}`}>{value}</b>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}
