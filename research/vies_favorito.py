"""Viés favorito-azarão na Betfair Exchange.

A assimetria mais documentada em mercados de aposta: azarões são
sistematicamente caros e favoritos, baratos. Se ela existe na Betfair, não
precisa de sinal nenhum — é estrutural, aparece em todo jogo, e dá para
medir com precisão porque a amostra é a base inteira.

Mede o retorno de apostar em TODA seleção de cada faixa de odd, ao preço de
FECHAMENTO da exchange (o mais eficiente que existe). Se o mercado fosse
perfeito, todo ROI seria igual a menos a comissão.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065
FAIXAS = [(1.01,1.5),(1.5,2.0),(2.0,2.6),(2.6,3.3),(3.3,4.5),
          (4.5,6.0),(6.0,9.0),(9.0,15.0),(15.0,1000.0)]


class Bag:
    def __init__(self): self.x = []
    def add(self, v): self.x.append(v)
    @property
    def n(self): return len(self.x)
    @property
    def m(self): return sum(self.x)/self.n if self.n else 0
    @property
    def se(self):
        if self.n < 2: return float("inf")
        v = sum((a-self.m)**2 for a in self.x)/(self.n-1)
        return math.sqrt(v/self.n)
    @property
    def t(self): return self.m/self.se if math.isfinite(self.se) and self.se else 0


def faixa(o):
    for lo, hi in FAIXAS:
        if lo <= o < hi: return f"{lo:>5.2f}–{hi:<6.2f}"
    return None


def rodar(usar_fechamento: bool):
    partidas = []
    for d in MAIN_DIVS:
        partidas.extend(load_main(d, ["2425","2526","2627"]))

    back = defaultdict(Bag); lay = defaultdict(Bag); acerto = defaultdict(Bag)
    for m in partidas:
        src = m.odds_close if usar_fechamento else m.odds_open
        exch = src.get("betfair_ex")
        if not exch: continue
        res = {"H":0,"D":1,"A":2}[m.result]
        for i,k in enumerate("HDA"):
            o = exch.get(k)
            if not o: continue
            f = faixa(o)
            if not f: continue
            ganhou = res == i
            back[f].add((o-1)*(1-COMISSAO) if ganhou else -1)
            lay[f].add(-(o-1) if ganhou else (1-COMISSAO))
            acerto[f].add(1.0 if ganhou else 0.0)
    return back, lay, acerto


for usar_fech in (True, False):
    back, lay, acerto = rodar(usar_fech)
    rot = "FECHAMENTO" if usar_fech else "ABERTURA"
    print(f"\n{'='*88}\nPreço de {rot} da Betfair Exchange — comissão de 6,5% aplicada\n{'='*88}")
    print(f"{'faixa de odd':<16}{'n':>7}{'acerto':>9}{'implícita':>11}"
          f"{'ROI back':>11}{'±':>7}{'t':>7}{'ROI lay':>10}{'t':>7}")
    print("-"*88)
    for lo,hi in FAIXAS:
        f = f"{lo:>5.2f}–{hi:<6.2f}"
        b = back.get(f)
        if not b or b.n < 60: continue
        a = acerto[f]; l = lay[f]
        odd_med = sum(1/x if x else 0 for x in [1])  # placeholder
        implicita = a.n and (sum(1.0 for _ in range(0)) )
        # probabilidade implícita média da faixa (ponto médio)
        pm = 1/((lo+min(hi,20))/2)
        print(f"{f:<16}{b.n:>7}{a.m*100:>8.1f}%{pm*100:>10.1f}%"
              f"{b.m*100:>10.2f}%{b.se*100:>7.2f}{b.t:>7.2f}"
              f"{l.m*100:>9.2f}%{l.t:>7.2f}")
