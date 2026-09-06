/* Mesma lógica de divergência, amostra completa: "melhor preço do mercado"
   (Max, ~20 casas) contra o consenso (Avg). Sem comissão: são casas, não
   exchange. CLV medido contra o melhor preço de fechamento (MaxC). */
import fs from "node:fs"; import path from "node:path";

const num = (v) => { const f = parseFloat(v); return Number.isFinite(f) && f > 1 ? f : null; };
function rows(dir) {
  const out = [];
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".csv"))) {
    const txt = fs.readFileSync(path.join(dir, f), "latin1").split(/\r?\n/).filter((l) => l.trim());
    const head = txt[0].split(",");
    for (const line of txt.slice(1)) {
      const c = line.split(","); const r = {}; head.forEach((h, i) => (r[h] = c[i]));
      const hg = +r.FTHG, ag = +r.FTAG;
      if (!Number.isFinite(hg) || !Number.isFinite(ag)) continue;
      out.push({
        league: f.split("_")[0], hg, ag,
        maxH: num(r.MaxH), maxD: num(r.MaxD), maxA: num(r.MaxA),
        avgH: num(r.AvgH), avgD: num(r.AvgD), avgA: num(r.AvgA),
        mcH: num(r.MaxCH), mcD: num(r.MaxCD), mcA: num(r.MaxCA),
        acH: num(r.AvgCH), acD: num(r.AvgCD), acA: num(r.AvgCA),
        maxO: num(r["Max>2.5"]), maxU: num(r["Max<2.5"]),
        avgO: num(r["Avg>2.5"]), avgU: num(r["Avg<2.5"]),
        mcO: num(r["MaxC>2.5"]), mcU: num(r["MaxC<2.5"]),
      });
    }
  }
  return out;
}
function devig(odds) {
  const raw = odds.map((o) => 1 / o);
  let lo = 0.2, hi = 5;
  for (let i = 0; i < 100; i++) {
    const k = (lo + hi) / 2;
    raw.reduce((a, x) => a + Math.pow(x, k), 0) > 1 ? (lo = k) : (hi = k);
  }
  const k = (lo + hi) / 2, o = raw.map((x) => Math.pow(x, k));
  const s = o.reduce((a, b) => a + b, 0);
  return o.map((x) => x / s);
}
function report(bets, label) {
  if (bets.length < 20) return console.log(`${label.padEnd(24)} n=${bets.length} (insuficiente)`);
  const pnl = bets.reduce((a, b) => a + b.pnl, 0), mean = pnl / bets.length;
  const sd = Math.sqrt(bets.reduce((a, b) => a + (b.pnl - mean) ** 2, 0) / bets.length);
  const se = (sd / Math.sqrt(bets.length)) * 100;
  const clvs = bets.map((b) => b.clv).filter(Number.isFinite);
  const clv = clvs.reduce((a, b) => a + b, 0) / (clvs.length || 1);
  const beat = (clvs.filter((x) => x > 0).length / (clvs.length || 1)) * 100;
  const t = mean / (sd / Math.sqrt(bets.length));
  console.log(
    `${label.padEnd(24)} n=${String(bets.length).padStart(6)}  ` +
    `ROI=${mean * 100 >= 0 ? "+" : ""}${(mean * 100).toFixed(2)}% ±${se.toFixed(2)}  ` +
    `t=${t.toFixed(2)}  CLV=${clv >= 0 ? "+" : ""}${clv.toFixed(2)}%  bateu=${beat.toFixed(1)}%`
  );
}

const R = rows("fd");
console.log(`\namostra: ${R.length} jogos\n`);
console.log("=== Melhor preço vs consenso — 1X2 (sem comissão, casas tradicionais) ===\n");
for (const edge of [0.02, 0.04, 0.06, 0.08, 0.12]) {
  const bets = [];
  for (const m of R) {
    if (!m.maxH || !m.avgH || !m.avgD || !m.avgA) continue;
    const cons = devig([m.avgH, m.avgD, m.avgA]);
    const px = [m.maxH, m.maxD, m.maxA], close = [m.mcH, m.mcD, m.mcA];
    const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
    for (let k = 0; k < 3; k++) {
      if (!px[k]) continue;
      if (px[k] * cons[k] - 1 < edge) continue;
      bets.push({ pnl: res === k ? px[k] - 1 : -1,
                  clv: close[k] ? (px[k] / close[k] - 1) * 100 : null });
    }
  }
  report(bets, `divergência >= ${(edge * 100).toFixed(0)}%`);
}
console.log("\n=== Mesmo teste — Over/Under 2.5 ===\n");
for (const edge of [0.02, 0.04, 0.06, 0.08]) {
  const bets = [];
  for (const m of R) {
    if (!m.maxO || !m.avgO || !m.avgU) continue;
    const cons = devig([m.avgO, m.avgU]);
    const px = [m.maxO, m.maxU], close = [m.mcO, m.mcU];
    const over = m.hg + m.ag > 2.5;
    for (let k = 0; k < 2; k++) {
      if (!px[k] || px[k] * cons[k] - 1 < edge) continue;
      bets.push({ pnl: (k === 0 ? over : !over) ? px[k] - 1 : -1,
                  clv: close[k] ? (px[k] / close[k] - 1) * 100 : null });
    }
  }
  report(bets, `divergência >= ${(edge * 100).toFixed(0)}%`);
}
console.log("\n=== Controle: apostar em TODO favorito no melhor preço ===\n");
{
  const bets = [];
  for (const m of R) {
    if (!m.maxH || !m.maxD || !m.maxA) continue;
    const px = [m.maxH, m.maxD, m.maxA];
    const k = px.indexOf(Math.min(...px));
    const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
    bets.push({ pnl: res === k ? px[k] - 1 : -1, clv: null });
  }
  report(bets, "favorito, melhor preço");
}
