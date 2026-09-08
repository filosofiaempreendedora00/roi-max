"""Tentativa de derrubar a regra do Over/Under.

Se ela é real, sobrevive a: separação por temporada, por liga, por lado
(over vs under), e produz sequência de perdas suportável. Se é sorte,
alguma dessas fatias entrega.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend"); sys.path.insert(0, "research")
from busca import construir  # noqa: E402


def stats(x):
    n = len(x)
    if n < 3: return n, 0.0, float("inf"), 0.0
    m = sum(x)/n
    v = sum((a-m)**2 for a in x)/(n-1)
    se = math.sqrt(v/n)
    return n, m*100, se*100, (m/se if se else 0.0)


LIM = 6.0
ops = [o for o in construir() if o.mercado == "O/U2.5" and 1.3 <= o.odd <= 6.0]
sel = [o for o in ops if o.diverg <= -LIM]
print(f"universo O/U 2.5: {len(ops)} · selecionadas (lay, div<=-{LIM:.0f}%): {len(sel)}\n")

def linha(rot, conj, larg=26):
    p = [o.pnl_lay for o in conj]
    n, roi, se, t = stats(p)
    c = [o.clv("lay") for o in conj if o.clv("lay") is not None]
    cm = sum(c)/len(c) if c else float("nan")
    if n < 20:
        print(f"  {rot[:larg]:<{larg}}{n:>6}   (insuficiente)"); return
    print(f"  {rot[:larg]:<{larg}}{n:>6}{roi:>9.2f}%{se:>7.2f}{t:>7.2f}{cm:>9.2f}%")

print(f"  {'recorte':<26}{'n':>6}{'ROI':>10}{'±':>7}{'t':>7}{'CLV':>10}")
print("  " + "-"*66)
linha("TUDO", sel)
print()
for s in sorted({o.temporada for o in sel}):
    linha(f"temporada {s}/{(s+1)%100:02d}", [o for o in sel if o.temporada == s])
print()
for lado in ("O", "U"):
    linha(f"lado {'Over' if lado=='O' else 'Under'}", [o for o in sel if o.lado == lado])
print()
por_liga = defaultdict(list)
for o in sel: por_liga[o.liga].append(o)
for lg in sorted(por_liga, key=lambda k: -len(por_liga[k])):
    linha(lg, por_liga[lg])

print("\n" + "="*66)
print("SEQUÊNCIAS E RISCO")
print("="*66)
pnls = [o.pnl_lay for o in sel]
pior = atual = 0; eq = pico = 0.0; dd = 0.0
for p in pnls:
    if p < 0: atual += 1; pior = max(pior, atual)
    else: atual = 0
    eq += p; pico = max(pico, eq); dd = min(dd, eq - pico)
perdas = sum(1 for p in pnls if p < 0)
odd_med = sum(o.odd for o in sel)/len(sel)
print(f"  entradas: {len(pnls)} · perdedoras: {perdas} ({perdas/len(pnls)*100:.1f}%)")
print(f"  odd média: {odd_med:.2f} -> liability de {odd_med-1:.2f} por 1 de stake")
print(f"  maior sequência de perdas: {pior}")
print(f"  pior queda: {dd:.1f} unidades · lucro final: {eq:+.1f} unidades")

print("\n" + "="*66)
print("FREQUÊNCIA")
print("="*66)
dias = len({(o.temporada, i) for i, o in enumerate(sel)})
temporadas = len({o.temporada for o in sel})
print(f"  {len(sel)} entradas em ~{temporadas} temporadas de 12 ligas")
print(f"  aproximadamente {len(sel)/(temporadas*270):.2f} por dia de calendário")

print("\n" + "="*66)
print("SENSIBILIDADE AO LIMIAR")
print("="*66)
print(f"  {'limiar':<10}{'n':>7}{'ROI':>10}{'±':>7}{'t':>7}{'CLV':>10}")
for lim in (2, 4, 6, 8, 10, 15):
    s2 = [o for o in ops if o.diverg <= -lim]
    if len(s2) < 20: continue
    p = [o.pnl_lay for o in s2]
    n, roi, se, t = stats(p)
    c = [o.clv("lay") for o in s2 if o.clv("lay") is not None]
    cm = sum(c)/len(c) if c else float("nan")
    print(f"  div<=-{lim:<4}{n:>7}{roi:>9.2f}%{se:>7.2f}{t:>7.2f}{cm:>9.2f}%")
