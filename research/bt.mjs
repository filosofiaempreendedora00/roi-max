import { load, fit, scoreMatrix, markets, devig } from "./proto.mjs";

const COMM = 0.065;
const all = load("fd");

// cobertura das colunas de exchange por temporada
const bySeason = {};
for (const m of all) {
  const s = m.date.getUTCMonth() >= 6 ? m.date.getUTCFullYear() : m.date.getUTCFullYear() - 1;
  bySeason[s] ??= { n: 0, bfe: 0 };
  bySeason[s].n++;
  if (m.bfeH) bySeason[s].bfe++;
}
console.log("cobertura de preço de exchange por temporada:");
for (const [s, v] of Object.entries(bySeason))
  console.log(`  ${s}/${(+s + 1) % 100}: ${String(v.n).padStart(5)} jogos, ${String(v.bfe).padStart(5)} com BFE`);

/** Walk-forward: só usa jogos anteriores à data da aposta. */
function backtest({ blend, minEv, usePrice }) {
  const bets = [];
  const leagues = [...new Set(all.map((m) => m.league))];

  for (const lg of leagues) {
    const ms = all.filter((m) => m.league === lg);
    let model = null, fittedAt = null;

    for (let i = 0; i < ms.length; i++) {
      const m = ms[i];
      const past = ms.slice(0, i);
      if (past.length < 250) continue;

      // refit a cada 30 dias, só com o passado
      if (!model || (m.date - fittedAt) / 86400000 > 30) {
        model = fit(past, { xi: 0.0018, iters: 300, refDate: m.date });
        fittedAt = m.date;
      }
      if (!model) continue;
      const M = scoreMatrix(model, m.home, m.away);
      if (!M) continue;
      const mk = markets(M);

      // --- mercado 1X2 ---
      const mkt = devig([m.avgH, m.avgD, m.avgA]);
      if (mkt) {
        const modelP = [mk.H, mk.D, mk.A];
        const price = usePrice === "bfe"
          ? [m.bfeH, m.bfeD, m.bfeA] : [m.avgH, m.avgD, m.avgA];
        const close = [m.bfeCH, m.bfeCD, m.bfeCA];
        const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;

        for (let k = 0; k < 3; k++) {
          const o = price[k];
          if (!o) continue;
          const p = blend * modelP[k] + (1 - blend) * mkt[k];
          const ev = p * (o - 1) * (1 - COMM) - (1 - p);
          if (ev < minEv) continue;
          const won = res === k;
          bets.push({
            market: "1X2", league: lg, odds: o, p, ev,
            pnl: won ? (o - 1) * (1 - COMM) : -1,
            clv: close[k] ? (o / close[k] - 1) * 100 : null,
          });
        }
      }

      // --- mercado Over/Under 2.5 ---
      const mktOU = devig([m.avgO, m.avgU]);
      if (mktOU) {
        const modelOU = [mk.O, mk.U];
        const price = usePrice === "bfe" ? [m.bfeO, m.bfeU] : [m.avgO, m.avgU];
        const close = [m.bfeCO, m.bfeCU];
        const over = m.hg + m.ag > 2.5;
        for (let k = 0; k < 2; k++) {
          const o = price[k];
          if (!o) continue;
          const p = blend * modelOU[k] + (1 - blend) * mktOU[k];
          const ev = p * (o - 1) * (1 - COMM) - (1 - p);
          if (ev < minEv) continue;
          const won = k === 0 ? over : !over;
          bets.push({
            market: "O/U 2.5", league: lg, odds: o, p, ev,
            pnl: won ? (o - 1) * (1 - COMM) : -1,
            clv: close[k] ? (o / close[k] - 1) * 100 : null,
          });
        }
      }
    }
  }
  return bets;
}

function summary(bets, label) {
  if (!bets.length) return console.log(`${label}: nenhuma aposta`);
  const pnl = bets.reduce((a, b) => a + b.pnl, 0);
  const roi = (pnl / bets.length) * 100;
  const wins = bets.filter((b) => b.pnl > 0).length;
  const clvs = bets.map((b) => b.clv).filter((x) => x !== null);
  const clv = clvs.length ? clvs.reduce((a, b) => a + b, 0) / clvs.length : NaN;
  const beat = clvs.length ? (clvs.filter((x) => x > 0).length / clvs.length) * 100 : NaN;
  // erro padrão do ROI: sem isto, ROI positivo em amostra pequena não diz nada
  const mean = pnl / bets.length;
  const sd = Math.sqrt(bets.reduce((a, b) => a + (b.pnl - mean) ** 2, 0) / bets.length);
  const se = (sd / Math.sqrt(bets.length)) * 100;
  console.log(
    `${label.padEnd(26)} n=${String(bets.length).padStart(5)}  ` +
    `ROI=${roi >= 0 ? "+" : ""}${roi.toFixed(2)}% ±${se.toFixed(2)}  ` +
    `acerto=${((wins / bets.length) * 100).toFixed(1)}%  ` +
    `CLV=${isNaN(clv) ? "n/d" : (clv >= 0 ? "+" : "") + clv.toFixed(2) + "%"}  ` +
    `bateu=${isNaN(beat) ? "n/d" : beat.toFixed(1) + "%"}`
  );
}

console.log("\n=== varredura do peso do modelo (preço = média do mercado, EV>3%) ===");
console.log("blend 0 = só mercado · blend 1 = só modelo\n");
for (const blend of [0, 0.2, 0.35, 0.5, 0.75, 1.0]) {
  summary(backtest({ blend, minEv: 0.03, usePrice: "avg" }), `blend=${blend.toFixed(2)}`);
}
