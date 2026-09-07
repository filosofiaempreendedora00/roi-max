"""Validação do achado: lay em favoritos curtos ao preço de abertura.

Um t=6.94 que aparece depois de varrer várias faixas merece desconfiança.
Aqui a ideia é tentar derrubar o resultado:

  1. Ele sobrevive fora da amostra? (2024/25 acha, 2025/26+ confirma)
  2. Está em todas as ligas ou é uma só puxando?
  3. Some quando se usa o preço de fechamento? (se sim, é efeito de deriva
     do preço, e a pergunta vira se dá para pegar a abertura de verdade)
  4. Qual a liability real, e quanto ela cresce?
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065


class Bag:
    def __init__(self): self.x = []; self.odds = []
    def add(self, v, o=None):
        self.x.append(v)
        if o: self.odds.append(o)
    @property
    def n(self): return len(self.x)
    @property
    def m(self): return sum(self.x)/self.n if self.n else 0.0
    @property
    def se(self):
        if self.n < 2: return float("inf")
        v = sum((a-self.m)**2 for a in self.x)/(self.n-1)
        return math.sqrt(v/self.n)
    @property
    def t(self): return self.m/self.se if math.isfinite(self.se) and self.se else 0.0
    @property
    def odd_media(self): return sum(self.odds)/len(self.odds) if self.odds else 0.0


def carregar():
    p = []
    for d in MAIN_DIVS:
        p.extend(load_main(d, ["2425","2526","2627"]))
    return p


def temporada(m):
    return m.date.year if m.date.month >= 7 else m.date.year-1


def coletar(partidas, teto, usar_fechamento=False):
    """Lay de 1 unidade de stake em toda seleção com odd <= teto."""
    por_temp = defaultdict(Bag); por_liga = defaultdict(Bag); geral = Bag()
    for m in partidas:
        src = m.odds_close if usar_fechamento else m.odds_open
        exch = src.get("betfair_ex")
        if not exch: continue
        res = {"H":0,"D":1,"A":2}[m.result]
        for i,k in enumerate("HDA"):
            o = exch.get(k)
            if not o or o > teto or o < 1.05: continue
            pnl = -(o-1) if res == i else (1-COMISSAO)
            geral.add(pnl, o); por_temp[temporada(m)].add(pnl, o); por_liga[m.league].add(pnl, o)
    return geral, por_temp, por_liga


def linha(nome, b, largura=30):
    if b.n < 20:
        print(f"  {nome[:largura]:<{largura}}{b.n:>6}   (amostra insuficiente)"); return
    print(f"  {nome[:largura]:<{largura}}{b.n:>6}{b.m*100:>10.2f}%{b.se*100:>7.2f}"
          f"{b.t:>7.2f}{b.odd_media:>9.2f}")


partidas = carregar()
TETO = 1.50

print(f"LAY em toda seleção com odd <= {TETO} na abertura da Betfair Exchange")
print(f"Stake de 1 unidade, comissão de {COMISSAO*100:.1f}%\n")

for rot, fech in [("ABERTURA", False), ("FECHAMENTO", True)]:
    geral, por_temp, por_liga = coletar(partidas, TETO, fech)
    print(f"{'='*70}\nPreço de {rot}\n{'='*70}")
    print(f"  {'recorte':<30}{'n':>6}{'ROI':>11}{'±':>7}{'t':>7}{'odd med':>9}")
    print("  " + "-"*66)
    linha("TUDO", geral)
    print()
    for t in sorted(por_temp):
        linha(f"temporada {t}/{(t+1)%100:02d}", por_temp[t])
    print()
    for lg in sorted(por_liga, key=lambda k: -por_liga[k].n):
        linha(lg, por_liga[lg])
    print()

# quanto custa a liability
geral, _, _ = coletar(partidas, TETO, False)
print(f"{'='*70}\nRisco por entrada\n{'='*70}")
print(f"  odd média: {geral.odd_media:.3f}  ->  liability de "
      f"{(geral.odd_media-1):.2f} por 1 de stake")
print(f"  ou seja: para ganhar R$ 100 você arrisca R$ {(geral.odd_media-1)*100:.0f}")
perdas = [x for x in geral.x if x < 0]
print(f"  entradas perdedoras: {len(perdas)}/{geral.n} ({len(perdas)/geral.n*100:.1f}%)")
