"""Onde está a assimetria? Estudo por segmento, com validação fora da amostra.

A pergunta: existe algum recorte de mercado onde o edge é grande o bastante
para ser validado em dezenas de apostas, e não em milhares?

Método:
  - Sinal: preço da Betfair Exchange fora de linha com o consenso das casas.
  - Treino: temporada 2024/25. Teste: 2025/26 em diante. O teste nunca é
    usado para escolher nada — é só para ver se o que apareceu no treino
    sobrevive.
  - Toda estatística vem com erro padrão. Sem isso, ROI é adivinhação.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, "backend")

from roimax.engine.math import fair_probs_power, to_prob  # noqa: E402
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065
SEASONS = ["2425", "2526", "2627"]

# casas tradicionais de verdade, sem agregados (Max e Avg são derivados)
LIVROS_1X2 = ["bet365", "betwin", "interwetten", "pinnacle", "williamhill", "betvictor"]


@dataclass
class Aposta:
    mercado: str
    liga: str
    odd: float
    diverg: float          # quanto acima do justo, em %
    pnl: float
    clv: float | None
    temporada: int


@dataclass
class Resumo:
    n: int = 0
    pnl: float = 0.0
    pnls: list = field(default_factory=list)
    clvs: list = field(default_factory=list)

    def add(self, a: Aposta):
        self.n += 1
        self.pnl += a.pnl
        self.pnls.append(a.pnl)
        if a.clv is not None:
            self.clvs.append(a.clv)

    @property
    def roi(self) -> float:
        return self.pnl / self.n * 100 if self.n else 0.0

    @property
    def se(self) -> float:
        if self.n < 2:
            return float("inf")
        m = self.pnl / self.n
        var = sum((x - m) ** 2 for x in self.pnls) / (self.n - 1)
        return math.sqrt(var / self.n) * 100

    @property
    def t(self) -> float:
        return self.roi / self.se if self.se and math.isfinite(self.se) else 0.0

    @property
    def clv(self) -> float:
        return sum(self.clvs) / len(self.clvs) if self.clvs else float("nan")

    @property
    def bateu(self) -> float:
        return sum(c > 0 for c in self.clvs) / len(self.clvs) * 100 if self.clvs else float("nan")

    @property
    def n_para_provar(self) -> float:
        """Quantas apostas seriam precisas para este ROI virar t=2."""
        if self.n < 2 or self.roi <= 0:
            return float("inf")
        m = self.pnl / self.n
        var = sum((x - m) ** 2 for x in self.pnls) / (self.n - 1)
        return (2 * math.sqrt(var) / m) ** 2


def temporada(m) -> int:
    return m.date.year if m.date.month >= 7 else m.date.year - 1


def consenso_1x2(m) -> list[float] | None:
    """Média das probabilidades sem margem, casa a casa."""
    por_livro = []
    for livro in LIVROS_1X2:
        t = m.odds_open.get(livro)
        if t and all(k in t for k in "HDA"):
            por_livro.append(fair_probs_power([t["H"], t["D"], t["A"]]))
    if len(por_livro) < 3:
        return None
    return [sum(p[i] for p in por_livro) / len(por_livro) for i in range(3)]


def consenso_par(abertura: dict, chaves: tuple[str, str]) -> list[float] | None:
    """Consenso de um mercado de duas pontas, usando a média do mercado."""
    t = abertura.get("market_avg")
    if not t or not all(k in t for k in chaves):
        return None
    return fair_probs_power([t[chaves[0]], t[chaves[1]]])


def coletar(min_diverg: float) -> list[Aposta]:
    partidas = []
    for div in MAIN_DIVS:
        partidas.extend(load_main(div, SEASONS))
    partidas.sort(key=lambda m: m.date)

    apostas: list[Aposta] = []
    for m in partidas:
        s = temporada(m)

        # ---------------- 1X2 ----------------
        exch = m.odds_open.get("betfair_ex")
        cons = consenso_1x2(m)
        if exch and cons:
            fech = m.odds_close.get("betfair_ex", {})
            res = {"H": 0, "D": 1, "A": 2}[m.result]
            for i, k in enumerate("HDA"):
                o = exch.get(k)
                if not o:
                    continue
                justo = 1 / cons[i]
                d = (o / justo - 1) * 100
                if d < min_diverg:
                    continue
                c = fech.get(k)
                apostas.append(Aposta(
                    "1X2", m.league, o, d,
                    (o - 1) * (1 - COMISSAO) if res == i else -1,
                    (o / c - 1) * 100 if c else None, s))

        # ------------- Over/Under 2.5 -------------
        exch = m.ou_open.get("betfair_ex")
        cons = consenso_par(m.ou_open, ("O", "U"))
        if exch and cons:
            fech = m.ou_close.get("betfair_ex", {})
            over = (m.goals_home or 0) + (m.goals_away or 0) > 2.5
            for i, k in enumerate(("O", "U")):
                o = exch.get(k)
                if not o:
                    continue
                justo = 1 / cons[i]
                d = (o / justo - 1) * 100
                if d < min_diverg:
                    continue
                ganhou = over if k == "O" else not over
                c = fech.get(k)
                apostas.append(Aposta(
                    "O/U 2.5", m.league, o, d,
                    (o - 1) * (1 - COMISSAO) if ganhou else -1,
                    (o / c - 1) * 100 if c else None, s))

    return apostas


def tabela(titulo: str, grupos: dict[str, Resumo], min_n: int = 30) -> None:
    print(f"\n{titulo}")
    print(f"  {'segmento':<26}{'n':>6}{'ROI':>9}{'±':>7}{'t':>6}{'CLV':>8}{'bateu':>7}{'n p/ provar':>13}")
    print("  " + "-" * 82)
    for nome, r in sorted(grupos.items(), key=lambda kv: -kv[1].roi):
        if r.n < min_n:
            continue
        npp = r.n_para_provar
        npp_s = "—" if not math.isfinite(npp) else f"{npp:,.0f}".replace(",", ".")
        clv_s = "—" if math.isnan(r.clv) else f"{r.clv:+.2f}%"
        bat_s = "—" if math.isnan(r.bateu) else f"{r.bateu:.0f}%"
        print(f"  {nome[:26]:<26}{r.n:>6}{r.roi:>8.2f}%{r.se:>7.2f}{r.t:>6.2f}"
              f"{clv_s:>8}{bat_s:>7}{npp_s:>13}")


if __name__ == "__main__":
    MIN_DIV = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    apostas = coletar(MIN_DIV)
    treino = [a for a in apostas if a.temporada == 2024]
    teste = [a for a in apostas if a.temporada >= 2025]
    print(f"Divergência mínima: {MIN_DIV}%")
    print(f"Apostas candidatas: {len(apostas)}  "
          f"(treino 2024/25: {len(treino)} · teste 2025/26+: {len(teste)})")

    def agrupa(conj, chave):
        g = defaultdict(Resumo)
        for a in conj:
            g[chave(a)].add(a)
        return g

    def faixa_odd(o):
        for lim, rot in [(1.5, "1.30-1.50"), (2.0, "1.50-2.00"), (3.0, "2.00-3.00"),
                         (5.0, "3.00-5.00"), (10.0, "5.00-10.0")]:
            if o < lim:
                return rot
        return "10.0+"

    def faixa_div(d):
        for lim, rot in [(4, "2-4%"), (6, "4-6%"), (10, "6-10%"), (20, "10-20%")]:
            if d < lim:
                return rot
        return "20%+"

    print("\n" + "=" * 90)
    print("TREINO — 2024/25. É aqui que se procura, e só aqui.")
    print("=" * 90)
    tabela("Por mercado:", agrupa(treino, lambda a: a.mercado))
    tabela("Por faixa de odd:", agrupa(treino, lambda a: faixa_odd(a.odd)))
    tabela("Por tamanho da divergência:", agrupa(treino, lambda a: faixa_div(a.diverg)))
    tabela("Por liga:", agrupa(treino, lambda a: a.liga), min_n=25)
