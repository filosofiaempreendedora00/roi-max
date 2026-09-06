/* A hipótese alternativa: em vez de tentar prever melhor que o mercado,
   procurar o preço fora de linha DENTRO do mercado. */
import { load, devig } from "./proto.mjs";
const COMM = 0.065;
const all = load("fd");

function report(bets, label) {
  if (bets.length < 5) return console.log(`${label.padEnd(30)} n=${bets.length} (amostra insuficiente)`);
  const pnl = bets.reduce((a, b) => a + b.pnl, 0);
  const mean = pnl / bets.length;
  const sd = Math.sqrt(bets.reduce((a, b) => a + (b.pnl - mean) ** 2, 0) / bets.length);
  const se = (sd / Math.sqrt(bets.length)) * 100;
  const clvs = bets.map((b) => b.clv).filter((x) => x !== null && Number.isFinite(x));
  const clv = clvs.length ? clvs.reduce((a, b) => a + b, 0) / clvs.length : NaN;
  const beat = clvs.length ? (clvs.filter((x) => x > 0).length / clvs.length) * 100 : NaN;
  console.log(
    `${label.padEnd(30)} n=${String(bets.length).padStart(5)}  ` +
    `ROI=${mean * 100 >= 0 ? "+" : ""}${(mean * 100).toFixed(2)}% ±${se.toFixed(2)}  ` +
    `CLV=${isNaN(clv) ? " n/d " : (clv >= 0 ? "+" : "") + clv.toFixed(2) + "%"}  ` +
    `bateu=${isNaN(beat) ? "n/d" : beat.toFixed(1) + "%"}`
  );
}

// ---- Teste A: exchange (abertura) fora de linha com o consenso das casas ----
console.log("\n=== A. Betfair Exchange vs consenso das casas (1X2) ===");
console.log("   preço de entrada = BFE abertura · CLV medido contra BFEC fechamento\n");
for (const edge of [0.02, 0.04, 0.06, 0.10]) {
  const bets = [];
  for (const m of all) {
    if (!m.bfeH || !m.avgH) continue;
    const cons = devig([m.avgH, m.avgD, m.avgA]);
    if (!cons) continue;
    const px = [m.bfeH, m.bfeD, m.bfeA], close = [m.bfeCH, m.bfeCD, m.bfeCA];
    const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
    for (let k = 0; k < 3; k++) {
      const fair = 1 / cons[k];
      if (px[k] / fair - 1 < edge) continue;
      bets.push({
        pnl: res === k ? (px[k] - 1) * (1 - COMM) : -1,
        clv: close[k] ? (px[k] / close[k] - 1) * 100 : null,
      });
    }
  }
  report(bets, `divergência >= ${(edge * 100).toFixed(0)}%`);
}

// ---- Teste B: mesma ideia no Over/Under 2.5 ----
console.log("\n=== B. Mesma regra no Over/Under 2.5 ===\n");
for (const edge of [0.02, 0.04, 0.06]) {
  const bets = [];
  for (const m of all) {
    if (!m.bfeO || !m.avgO) continue;
    const cons = devig([m.avgO, m.avgU]);
    if (!cons) continue;
    const px = [m.bfeO, m.bfeU], close = [m.bfeCO, m.bfeCU];
    const over = m.hg + m.ag > 2.5;
    for (let k = 0; k < 2; k++) {
      const fair = 1 / cons[k];
      if (px[k] / fair - 1 < edge) continue;
      const won = k === 0 ? over : !over;
      bets.push({
        pnl: won ? (px[k] - 1) * (1 - COMM) : -1,
        clv: close[k] ? (px[k] / close[k] - 1) * 100 : null,
      });
    }
  }
  report(bets, `divergência >= ${(edge * 100).toFixed(0)}%`);
}

// ---- Teste C: controle. A exchange bate o consenso sem filtro nenhum? ----
console.log("\n=== C. Controle: apostar TUDO no preço da exchange ===\n");
for (const which of [0, 1, 2]) {
  const bets = [];
  for (const m of all) {
    if (!m.bfeH) continue;
    const px = [m.bfeH, m.bfeD, m.bfeA], close = [m.bfeCH, m.bfeCD, m.bfeCA];
    const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
    if (!px[which]) continue;
    bets.push({
      pnl: res === which ? (px[which] - 1) * (1 - COMM) : -1,
      clv: close[which] ? (px[which] / close[which] - 1) * 100 : null,
    });
  }
  report(bets, `sempre ${["casa", "empate", "fora"][which]}`);
}
