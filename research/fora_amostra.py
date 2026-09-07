"""O teste que decide: o que brilhou em 2024/25 sobrevive em 2025/26?

Escolher liga olhando o resultado e depois reportar esse mesmo resultado é
garimpagem de dados — com 12 ligas, alguma sempre parece ótima por sorte.
A única defesa honesta é escolher num período e medir noutro.

Também mede o que a estatística esconde: sequências de perdas. Uma
estratégia que perde 71% das vezes produz sequências longas, e é aí que se
abandona um método que funcionava.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065
TETO = 1.50


def stats(x):
    n = len(x)
    if n < 2: return n, 0.0, float("inf"), 0.0
    m = sum(x)/n
    v = sum((a-m)**2 for a in x)/(n-1)
    se = math.sqrt(v/n)
    return n, m*100, se*100, (m/se if se else 0.0)


partidas = []
for d in MAIN_DIVS:
    partidas.extend(load_main(d, ["2425","2526","2627"]))
partidas.sort(key=lambda m: m.date)

def temporada(m): return m.date.year if m.date.month >= 7 else m.date.year-1

entradas = []   # (temporada, liga, pnl, data)
for m in partidas:
    exch = m.odds_open.get("betfair_ex")
    if not exch: continue
    res = {"H":0,"D":1,"A":2}[m.result]
    for i,k in enumerate("HDA"):
        o = exch.get(k)
        if not o or o > TETO or o < 1.05: continue
        entradas.append((temporada(m), m.league,
                         -(o-1) if res == i else (1-COMISSAO), m.date))

treino = [e for e in entradas if e[0] == 2024]
teste  = [e for e in entradas if e[0] >= 2025]

por_liga_treino = defaultdict(list)
for _,lg,p,_ in treino: por_liga_treino[lg].append(p)

# escolhe SÓ com o treino: ligas com t > 2 e pelo menos 80 entradas
escolhidas = []
for lg, xs in por_liga_treino.items():
    n, roi, se, t = stats(xs)
    if n >= 80 and t > 2.0:
        escolhidas.append((lg, n, roi, t))

print("="*76)
print("PASSO 1 — escolha feita SÓ com 2024/25 (t > 2 e n >= 80)")
print("="*76)
print(f"  {'liga':<26}{'n':>6}{'ROI':>10}{'t':>7}")
for lg,n,roi,t in sorted(escolhidas, key=lambda x:-x[3]):
    print(f"  {lg:<26}{n:>6}{roi:>9.2f}%{t:>7.2f}")
if not escolhidas:
    print("  (nenhuma liga passou no critério)")

nomes = {lg for lg,_,_,_ in escolhidas}
print("\n" + "="*76)
print("PASSO 2 — mesmas ligas, medidas SÓ em 2025/26 em diante")
print("="*76)
sel_teste = [p for _,lg,p,_ in teste if lg in nomes]
n, roi, se, t = stats(sel_teste)
print(f"  {'seleção do treino':<26}{n:>6}{roi:>9.2f}%  ±{se:>5.2f}{t:>7.2f}")
resto = [p for _,lg,p,_ in teste if lg not in nomes]
n2, roi2, se2, t2 = stats(resto)
print(f"  {'ligas descartadas':<26}{n2:>6}{roi2:>9.2f}%  ±{se2:>5.2f}{t2:>7.2f}")
todas = [p for _,_,p,_ in teste]
n3, roi3, se3, t3 = stats(todas)
print(f"  {'todas as ligas':<26}{n3:>6}{roi3:>9.2f}%  ±{se3:>5.2f}{t3:>7.2f}")

print("\n" + "="*76)
print("PASSO 3 — o que a média esconde: sequências de perda")
print("="*76)
serie = sorted(entradas, key=lambda e: e[3])
pior = atual = 0
eq = 0.0; pico = 0.0; dd = 0.0
for _,_,p,_ in serie:
    if p < 0:
        atual += 1; pior = max(pior, atual)
    else:
        atual = 0
    eq += p; pico = max(pico, eq); dd = min(dd, eq - pico)
perdas = sum(1 for e in serie if e[2] < 0)
print(f"  entradas: {len(serie)} · perdedoras: {perdas} ({perdas/len(serie)*100:.1f}%)")
print(f"  maior sequência de perdas seguidas: {pior}")
print(f"  pior queda acumulada: {dd:.1f} unidades de stake")
print(f"  lucro final: {eq:+.1f} unidades")
print(f"\n  Traduzindo com stake de R$ 100 por entrada:")
print(f"    você veria {pior} perdas seguidas em algum momento")
print(f"    e uma queda de R$ {abs(dd)*100:.0f} do topo antes de recuperar")
