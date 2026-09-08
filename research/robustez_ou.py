"""Últimos testes: a regra depende de uma liga só? Sobrevive fora da amostra
no limiar operacional? E qual a frequência real por dia?"""
from __future__ import annotations

import math, sys
from collections import defaultdict
sys.path.insert(0, "backend"); sys.path.insert(0, "research")
from busca import construir  # noqa: E402

def st(x):
    n=len(x)
    if n<3: return n,0.0,float("inf"),0.0
    m=sum(x)/n; v=sum((a-m)**2 for a in x)/(n-1); se=math.sqrt(v/n)
    return n, m*100, se*100, (m/se if se else 0.0)

ops=[o for o in construir() if o.mercado=="O/U2.5" and 1.3<=o.odd<=6.0]

print("1. JACKKNIFE POR LIGA — remove uma liga por vez (limiar -8%)")
print("   Se uma só estiver sustentando tudo, a remoção dela derruba.\n")
sel=[o for o in ops if o.diverg<=-8]
ligas=sorted({o.liga for o in sel})
n,roi,se,t=st([o.pnl_lay for o in sel])
print(f"   {'removendo':<26}{'n':>6}{'ROI':>10}{'t':>7}")
print(f"   {'(nenhuma)':<26}{n:>6}{roi:>9.2f}%{t:>7.2f}")
for lg in ligas:
    sub=[o for o in sel if o.liga!=lg]
    n2,roi2,se2,t2=st([o.pnl_lay for o in sub])
    if n2<50: continue
    print(f"   {lg[:26]:<26}{n2:>6}{roi2:>9.2f}%{t2:>7.2f}")

print("\n2. FORA DA AMOSTRA no limiar operacional (-8%)")
print("   Treino escolhe o limiar; teste julga.\n")
for lim in (6,8,10):
    tr=[o for o in ops if o.diverg<=-lim and o.temporada==2024]
    te=[o for o in ops if o.diverg<=-lim and o.temporada>=2025]
    if len(te)<30: continue
    n1,r1,_,t1=st([o.pnl_lay for o in tr])
    n2,r2,s2,t2=st([o.pnl_lay for o in te])
    print(f"   limiar -{lim}%:  treino n={n1:>5} ROI={r1:>7.2f}% t={t1:>5.2f}   "
          f"|  TESTE n={n2:>5} ROI={r2:>7.2f}% ±{s2:.2f} t={t2:>5.2f}")

print("\n3. FREQUÊNCIA REAL (dias de calendário distintos com jogo)")
import datetime
partidas_por_dia=defaultdict(int)
for o in ops: partidas_por_dia[o.temporada]+=1
for lim in (6,8,10,15):
    s=[o for o in ops if o.diverg<=-lim]
    # 3 temporadas ~ 800 dias de calendário com jogos nas 12 ligas
    print(f"   limiar -{lim:>2}%: {len(s):>5} entradas -> ~{len(s)/800:.2f}/dia "
          f"· ~{len(s)/800*7:.1f}/semana")

print("\n4. QUANTAS APOSTAS PARA PROVAR CADA LIMIAR (t=2)")
for lim in (6,8,10,15):
    s=[o for o in ops if o.diverg<=-lim]
    p=[o.pnl_lay for o in s]
    n,roi,se,t=st(p)
    if roi<=0: continue
    m=roi/100; v=sum((a-m)**2 for a in p)/(len(p)-1); sd=math.sqrt(v)
    need=(2*sd/m)**2
    print(f"   limiar -{lim:>2}%: ROI {roi:>6.2f}% · precisa de ~{need:>5.0f} apostas "
          f"· você tem {n:>5}  {'JÁ PROVADO' if n>=need else ''}")
