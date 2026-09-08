"""Busca com desconto da linha de base.

A primeira busca deu t=32 em regras de lay. Isso é artefato: as odds se
alongam da abertura ao fechamento, então TODO lay na abertura bate o
fechamento. O sinal não é o CLV da regra — é o quanto ela supera o CLV de
apostar sem filtro nenhum no mesmo mercado e lado.

Mede CLV EXCEDENTE = CLV da regra menos CLV da linha de base, com teste de
diferença entre médias. E valida fora da amostra.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
sys.path.insert(0, "research")
from busca import Op, avaliar, construir  # noqa: E402


def media_dp(xs):
    n = len(xs)
    if n < 2: return 0.0, 0.0, n
    m = sum(xs)/n
    v = sum((x-m)**2 for x in xs)/(n-1)
    return m, math.sqrt(v), n


def t_diferenca(a, b):
    """t de Welch entre duas médias independentes."""
    ma, sa, na = media_dp(a); mb, sb, nb = media_dp(b)
    if na < 3 or nb < 3: return 0.0, 0.0
    se = math.sqrt(sa*sa/na + sb*sb/nb)
    return (ma - mb), ((ma-mb)/se if se else 0.0)


ops = construir()
treino = [o for o in ops if o.temporada == 2024]
teste = [o for o in ops if o.temporada >= 2025]

# linha de base: TODAS as oportunidades do mercado/lado, sem filtro
def base_clvs(conj, mercado, lado, omin, omax):
    out = []
    for o in conj:
        if o.mercado != mercado or not (omin <= o.odd <= omax): continue
        c = o.clv(lado)
        if c is not None: out.append(c)
    return out

def regra_clvs(conj, mercado, lado, lim, omin, omax):
    out, pnls = [], []
    for o in conj:
        if o.mercado != mercado or not (omin <= o.odd <= omax): continue
        d = o.diverg
        if lado == "back" and d < lim: continue
        if lado == "lay" and d > -lim: continue
        c = o.clv(lado)
        if c is not None: out.append(c)
        pnls.append(o.pnl_back if lado == "back" else o.pnl_lay)
    return out, pnls

print("LINHA DE BASE — CLV de apostar sem filtro nenhum (odds 1.3 a 6.0)")
print(f"  {'mercado':<12}{'lado':<6}{'n':>7}{'CLV base':>11}")
for mercado in ("1X2", "1X2pin", "O/U2.5", "AH"):
    for lado in ("back", "lay"):
        b = base_clvs(treino, mercado, lado, 1.3, 6.0)
        if len(b) >= 50:
            m,_,n = media_dp(b)
            print(f"  {mercado:<12}{lado:<6}{n:>7}{m:>10.2f}%")

print("\nÉ isto que precisa ser descontado. Um lay com CLV de +6% num mercado")
print("cuja base já é +5% tem apenas +1% de sinal de verdade.\n")

cands = []
for mercado in ("1X2", "1X2pin", "O/U2.5", "AH"):
    for lado in ("back", "lay"):
        for lim in (2, 4, 6, 10):
            for omin, omax in ((1.3, 2.0), (2.0, 3.5), (3.5, 6.0), (1.3, 6.0)):
                rc, pnls = regra_clvs(treino, mercado, lado, lim, omin, omax)
                if len(rc) < 40: continue
                bc = base_clvs(treino, mercado, lado, omin, omax)
                dif, t = t_diferenca(rc, bc)
                mroi,_,n = media_dp(pnls)
                cands.append({"nome": f"{mercado} {lado} div>{lim}% odd {omin}-{omax}",
                              "m": mercado, "l": lado, "lim": lim,
                              "omin": omin, "omax": omax,
                              "n": len(pnls), "clv_exc": dif, "t": t,
                              "roi": mroi*100})
cands.sort(key=lambda c: -c["t"])
N = len(cands)
lim_bonf = 3.4 if N > 100 else 3.2
print(f"{'='*100}")
print(f"TREINO — CLV EXCEDENTE sobre a linha de base ({N} regras testadas)")
print(f"Para sobreviver a {N} testes simultâneos, t precisa passar de ~{lim_bonf}")
print(f"{'='*100}")
print(f"  {'regra':<44}{'n':>6}{'CLV exc':>10}{'t':>8}{'ROI':>9}")
for c in cands[:12]:
    marca = "  <-- passa" if c["t"] > lim_bonf else ""
    print(f"  {c['nome']:<44}{c['n']:>6}{c['clv_exc']:>9.2f}%{c['t']:>8.2f}{c['roi']:>8.2f}%{marca}")

print(f"\n{'='*100}")
print("TESTE 2025/26+ — as 5 melhores do treino, medidas onde não escolheram nada")
print(f"{'='*100}")
print(f"  {'regra':<44}{'n':>6}{'CLV exc':>10}{'t':>8}{'ROI':>9}")
for c in cands[:5]:
    rc, pnls = regra_clvs(teste, c["m"], c["l"], c["lim"], c["omin"], c["omax"])
    bc = base_clvs(teste, c["m"], c["l"], c["omin"], c["omax"])
    if len(rc) < 20:
        print(f"  {c['nome']:<44}{len(pnls):>6}   (amostra insuficiente)"); continue
    dif, t = t_diferenca(rc, bc)
    mroi,_,_ = media_dp(pnls)
    print(f"  {c['nome']:<44}{len(pnls):>6}{dif:>9.2f}%{t:>8.2f}{mroi*100:>8.2f}%")
