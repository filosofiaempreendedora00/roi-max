/* Protótipo Dixon-Coles + backtest walk-forward.
   Objetivo: descobrir se existe edge ANTES de escrever o backend definitivo. */
import fs from "node:fs";
import path from "node:path";

// ----------------------------------------------------------------- dados
function parseCSV(txt) {
  const lines = txt.split(/\r?\n/).filter((l) => l.trim());
  const head = lines[0].split(",");
  return lines.slice(1).map((l) => {
    // os arquivos não têm vírgula dentro de campo; split simples basta
    const cells = l.split(",");
    const o = {};
    head.forEach((h, i) => (o[h] = cells[i]));
    return o;
  });
}
const num = (v) => {
  const f = parseFloat(v);
  return Number.isFinite(f) && f > 1.0 ? f : null;
};
function parseDate(s) {
  if (!s) return null;
  const [d, m, y] = s.split("/");
  if (!d) return null;
  const yr = y.length === 2 ? 2000 + +y : +y;
  return new Date(Date.UTC(yr, +m - 1, +d));
}

function load(dir) {
  const out = [];
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".csv"))) {
    const league = f.split("_")[0];
    for (const r of parseCSV(fs.readFileSync(path.join(dir, f), "latin1"))) {
      const date = parseDate(r.Date);
      const hg = parseInt(r.FTHG, 10), ag = parseInt(r.FTAG, 10);
      if (!date || !Number.isFinite(hg) || !Number.isFinite(ag)) continue;
      if (!r.HomeTeam || !r.AwayTeam) continue;
      out.push({
        league, date, home: r.HomeTeam, away: r.AwayTeam, hg, ag,
        // preço de ABERTURA na exchange (entrada) e de FECHAMENTO (CLV)
        bfeH: num(r.BFEH), bfeD: num(r.BFED), bfeA: num(r.BFEA),
        bfeCH: num(r.BFECH), bfeCD: num(r.BFECD), bfeCA: num(r.BFECA),
        bfeO: num(r["BFE>2.5"]), bfeU: num(r["BFE<2.5"]),
        bfeCO: num(r["BFEC>2.5"]), bfeCU: num(r["BFEC<2.5"]),
        // consenso do mercado (média das casas), para ancorar o modelo
        avgH: num(r.AvgH), avgD: num(r.AvgD), avgA: num(r.AvgA),
        avgO: num(r["Avg>2.5"]), avgU: num(r["Avg<2.5"]),
      });
    }
  }
  out.sort((a, b) => a.date - b.date);
  return out;
}

// ------------------------------------------------------------ Dixon-Coles
const MAXG = 10;

function tau(x, y, l, m, rho) {
  if (x === 0 && y === 0) return 1 - l * m * rho;
  if (x === 0 && y === 1) return 1 + l * rho;
  if (x === 1 && y === 0) return 1 + m * rho;
  if (x === 1 && y === 1) return 1 - rho;
  return 1;
}

/** Ajusta ataque/defesa por time, vantagem de casa e a correção rho. */
function fit(matches, { xi = 0.0018, iters = 350, refDate }) {
  const teams = [...new Set(matches.flatMap((m) => [m.home, m.away]))];
  const idx = new Map(teams.map((t, i) => [t, i]));
  const n = teams.length;
  if (n < 6 || matches.length < 60) return null;

  // parâmetros: [atk(n), def(n), gamma, rho]
  const p = new Float64Array(2 * n + 2);
  p[2 * n] = 0.25;      // vantagem de casa
  p[2 * n + 1] = -0.05; // rho

  const w = matches.map((m) =>
    Math.exp(-xi * ((refDate - m.date) / 86400000))
  );

  const g = new Float64Array(p.length);
  const mAdam = new Float64Array(p.length);
  const vAdam = new Float64Array(p.length);
  const lr = 0.05, b1 = 0.9, b2 = 0.999, eps = 1e-8;

  for (let it = 1; it <= iters; it++) {
    g.fill(0);
    const gamma = p[2 * n], rho = Math.max(-0.2, Math.min(0.2, p[2 * n + 1]));

    for (let k = 0; k < matches.length; k++) {
      const m = matches[k], wk = w[k];
      const h = idx.get(m.home), a = idx.get(m.away);
      const l = Math.exp(p[h] - p[n + a] + gamma);
      const mu = Math.exp(p[a] - p[n + h]);
      const x = Math.min(m.hg, MAXG), y = Math.min(m.ag, MAXG);

      // parte Poisson
      let dL = x - l;       // dLL/d(log lambda)
      let dM = y - mu;      // dLL/d(log mu)

      // correção de baixo placar
      const t = tau(x, y, l, mu, rho);
      if (t > 1e-6 && (x <= 1 && y <= 1)) {
        let dtl = 0, dtm = 0, dtr = 0;
        if (x === 0 && y === 0) { dtl = -mu * rho; dtm = -l * rho; dtr = -l * mu; }
        else if (x === 0 && y === 1) { dtl = rho; dtr = l; }
        else if (x === 1 && y === 0) { dtm = rho; dtr = mu; }
        else { dtr = -1; }
        dL += (dtl * l) / t;   // cadeia: d/d(log lambda) = l * d/d lambda
        dM += (dtm * mu) / t;
        g[2 * n + 1] += (wk * dtr) / t;
      }

      g[h] += wk * dL;
      g[n + a] -= wk * dL;
      g[2 * n] += wk * dL;
      g[a] += wk * dM;
      g[n + h] -= wk * dM;
    }

    for (let i = 0; i < p.length; i++) {
      mAdam[i] = b1 * mAdam[i] + (1 - b1) * g[i];
      vAdam[i] = b2 * vAdam[i] + (1 - b2) * g[i] * g[i];
      const mh = mAdam[i] / (1 - Math.pow(b1, it));
      const vh = vAdam[i] / (1 - Math.pow(b2, it));
      p[i] += (lr * mh) / (Math.sqrt(vh) + eps);
    }
    // identificabilidade: ataque médio fixado em zero
    let s = 0;
    for (let i = 0; i < n; i++) s += p[i];
    s /= n;
    for (let i = 0; i < n; i++) p[i] -= s;
    p[2 * n + 1] = Math.max(-0.2, Math.min(0.2, p[2 * n + 1]));
  }

  return { idx, p, n };
}

/** Matriz de placares -> probabilidades de qualquer mercado derivado. */
function scoreMatrix(model, home, away) {
  const { idx, p, n } = model;
  const h = idx.get(home), a = idx.get(away);
  if (h === undefined || a === undefined) return null;
  const l = Math.exp(p[h] - p[n + a] + p[2 * n]);
  const mu = Math.exp(p[a] - p[n + h]);
  const rho = p[2 * n + 1];

  const pois = (k, lam) => {
    let lp = -lam + k * Math.log(lam);
    for (let i = 2; i <= k; i++) lp -= Math.log(i);
    return Math.exp(lp);
  };
  const M = [];
  let tot = 0;
  for (let x = 0; x <= MAXG; x++) {
    M[x] = [];
    for (let y = 0; y <= MAXG; y++) {
      const v = pois(x, l) * pois(y, mu) * tau(x, y, l, mu, rho);
      M[x][y] = Math.max(v, 0);
      tot += M[x][y];
    }
  }
  for (let x = 0; x <= MAXG; x++) for (let y = 0; y <= MAXG; y++) M[x][y] /= tot;
  return M;
}

function markets(M) {
  let H = 0, D = 0, A = 0, O = 0;
  for (let x = 0; x <= MAXG; x++)
    for (let y = 0; y <= MAXG; y++) {
      const v = M[x][y];
      if (x > y) H += v; else if (x === y) D += v; else A += v;
      if (x + y > 2.5) O += v;
    }
  return { H, D, A, O, U: 1 - O };
}

// -------------------------------------------------------------- utilidades
const toProb = (o) => (o ? 1 / o : null);
function devig(odds) {                    // método da potência
  const raw = odds.map(toProb);
  if (raw.some((x) => !x)) return null;
  let lo = 0.2, hi = 5;
  for (let i = 0; i < 100; i++) {
    const k = (lo + hi) / 2;
    const s = raw.reduce((a, x) => a + Math.pow(x, k), 0);
    if (s > 1) lo = k; else hi = k;
  }
  const k = (lo + hi) / 2;
  const out = raw.map((x) => Math.pow(x, k));
  const s = out.reduce((a, b) => a + b, 0);
  return out.map((x) => x / s);
}

export { load, fit, scoreMatrix, markets, devig, toProb };
