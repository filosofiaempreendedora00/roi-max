"""O sinal está invertido?

Hipótese: a Betfair Exchange é o mercado mais afiado. Quando o preço dela
diverge do consenso das casas, quem está errado são as casas. Se for isso, a
regra "back quando a exchange paga acima do justo" está apostando contra o
melhor estimador disponível — e a regra oposta deveria funcionar.

Testa as duas direções, no mesmo conjunto, com erro padrão.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
sys.path.insert(0, "research")

from segmentos import consenso_1x2  # noqa: E402
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065
SEASONS = ["2425", "2526", "2627"]


def carregar():
    p = []
    for d in MAIN_DIVS:
        p.extend(load_main(d, SEASONS))
    p.sort(key=lambda m: m.date)
    return p


class Bag:
    def __init__(self): self.pnls, self.clvs = [], []
    def add(self, pnl, clv):
        self.pnls.append(pnl)
        if clv is not None: self.clvs.append(clv)
    @property
    def n(self): return len(self.pnls)
    @property
    def roi(self): return sum(self.pnls)/self.n*100 if self.n else 0
    @property
    def se(self):
        if self.n < 2: return float("inf")
        m = sum(self.pnls)/self.n
        v = sum((x-m)**2 for x in self.pnls)/(self.n-1)
        return math.sqrt(v/self.n)*100
    @property
    def t(self): return self.roi/self.se if math.isfinite(self.se) and self.se else 0
    @property
    def clv(self): return sum(self.clvs)/len(self.clvs) if self.clvs else float("nan")
    @property
    def bateu(self): return sum(c>0 for c in self.clvs)/len(self.clvs)*100 if self.clvs else float("nan")


def linha(nome, b):
    clv = "—" if math.isnan(b.clv) else f"{b.clv:+.2f}%"
    bat = "—" if math.isnan(b.bateu) else f"{b.bateu:.0f}%"
    print(f"  {nome:<40}{b.n:>6}{b.roi:>9.2f}%{b.se:>7.2f}{b.t:>7.2f}{clv:>9}{bat:>7}")


if __name__ == "__main__":
    partidas = carregar()
    LIM = 2.0

    # back quando a exchange paga ACIMA do justo (a regra atual)
    back_acima = Bag()
    # back quando a exchange paga ABAIXO do justo (a regra invertida)
    back_abaixo = Bag()
    # lay quando a exchange cobra ABAIXO do justo (regra atual de lay)
    lay_abaixo = Bag()
    # lay quando a exchange cobra ACIMA do justo (lay invertido)
    lay_acima = Bag()

    for m in partidas:
        exch = m.odds_open.get("betfair_ex")
        cons = consenso_1x2(m)
        if not exch or not cons:
            continue
        fech = m.odds_close.get("betfair_ex", {})
        res = {"H": 0, "D": 1, "A": 2}[m.result]
        for i, k in enumerate("HDA"):
            o = exch.get(k)
            if not o or not (1.3 <= o <= 10):
                continue
            justo = 1/cons[i]
            d = (o/justo - 1)*100
            c = fech.get(k)
            clv_back = (o/c - 1)*100 if c else None
            clv_lay = (c/o - 1)*100 if c else None
            ganhou = res == i
            pnl_back = (o-1)*(1-COMISSAO) if ganhou else -1
            # lay com stake 1: ganha 1*(1-com) se NÃO ocorre, perde (o-1) se ocorre
            pnl_lay = -(o-1) if ganhou else (1-COMISSAO)

            if d >= LIM:
                back_acima.add(pnl_back, clv_back)
                lay_acima.add(pnl_lay, clv_lay)
            elif d <= -LIM:
                back_abaixo.add(pnl_back, clv_back)
                lay_abaixo.add(pnl_lay, clv_lay)

    print(f"Mercado 1X2, odds entre 1.30 e 10.00, divergência mínima {LIM}%")
    print(f"Comissão de {COMISSAO*100:.1f}% aplicada. Amostra: 2024/25 a 2026/27.\n")
    print(f"  {'estratégia':<40}{'n':>6}{'ROI':>10}{'±':>7}{'t':>7}{'CLV':>9}{'bateu':>7}")
    print("  " + "-" * 86)
    linha("BACK onde a exchange paga ACIMA (atual)", back_acima)
    linha("BACK onde a exchange paga ABAIXO", back_abaixo)
    print()
    linha("LAY onde a exchange cobra ABAIXO (atual)", lay_abaixo)
    linha("LAY onde a exchange cobra ACIMA", lay_acima)
