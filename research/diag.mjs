import { load, fit, scoreMatrix, markets, devig } from "./proto.mjs";
const all = load("fd");

/** Log-loss: mede a qualidade da previsão em si, sem passar por aposta. */
function diagnose(iters, xi) {
  const leagues = [...new Set(all.map((m) => m.league))];
  let llModel = 0, llMarket = 0, llBase = 0, n = 0;
  let brierM = 0, brierK = 0;
  const base = [0.44, 0.26, 0.30]; // taxas históricas casa/empate/fora

  for (const lg of leagues) {
    const ms = all.filter((m) => m.league === lg);
    let model = null, at = null;
    for (let i = 0; i < ms.length; i++) {
      const m = ms[i];
      if (i < 250) continue;
      if (!model || (m.date - at) / 86400000 > 30) {
        model = fit(ms.slice(0, i), { xi, iters, refDate: m.date });
        at = m.date;
      }
      if (!model) continue;
      const M = scoreMatrix(model, m.home, m.away);
      if (!M) continue;
      const mk = markets(M);
      const mkt = devig([m.avgH, m.avgD, m.avgA]);
      if (!mkt) continue;

      const res = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
      const pm = [mk.H, mk.D, mk.A];
      llModel -= Math.log(Math.max(pm[res], 1e-9));
      llMarket -= Math.log(Math.max(mkt[res], 1e-9));
      llBase -= Math.log(base[res]);
      for (let k = 0; k < 3; k++) {
        const y = k === res ? 1 : 0;
        brierM += (pm[k] - y) ** 2;
        brierK += (mkt[k] - y) ** 2;
      }
      n++;
    }
  }
  return {
    n, iters, xi,
    llModel: llModel / n, llMarket: llMarket / n, llBase: llBase / n,
    brierModel: brierM / n, brierMarket: brierK / n,
  };
}

console.log("Log-loss 1X2 (menor = melhor). Referência: mercado é o teto prático.\n");
for (const [it, xi] of [[300, 0.0018], [900, 0.0018], [900, 0.0030], [900, 0.0008]]) {
  const d = diagnose(it, xi);
  console.log(
    `iters=${String(d.iters).padStart(4)} xi=${d.xi.toFixed(4)}  n=${d.n}  ` +
    `modelo=${d.llModel.toFixed(4)}  mercado=${d.llMarket.toFixed(4)}  ` +
    `base=${d.llBase.toFixed(4)}  |  Brier modelo=${d.brierModel.toFixed(4)} mercado=${d.brierMarket.toFixed(4)}`
  );
}
