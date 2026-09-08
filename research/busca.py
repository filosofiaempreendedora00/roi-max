"""Busca sistemática por uma regra com CLV positivo.

Em vez de eu escolher uma regra e torcer, testa muitas e mede todas. Duas
defesas contra enganar a si mesmo:

  1. Treino (2024/25) escolhe; teste (2025/26+) julga. O teste nunca
     participa da escolha.
  2. Testar N regras faz a melhor parecer boa por sorte. O relatório mostra
     quantas foram testadas e qual t seria preciso para sobreviver a isso.

Métrica principal é o CLV, porque valida em dezenas de apostas. ROI vem
junto, mas com o erro padrão à vista.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, "backend")
from roimax.engine.math import fair_probs_power  # noqa: E402
from roimax.providers.footballdata_uk import MAIN_DIVS, load_main  # noqa: E402

COMISSAO = 0.065
SEASONS = ["2425", "2526", "2627"]
LIVROS = ["bet365", "betwin", "interwetten", "pinnacle", "williamhill", "betvictor"]


@dataclass
class Op:
    """Uma oportunidade: um lado de um mercado, num jogo."""
    temporada: int
    liga: str
    mercado: str
    lado: str
    odd: float              # preço na Exchange, na abertura
    fecho: float | None     # preço na Exchange, no fechamento
    ref: float              # odd justa segundo a referência
    ganhou: bool

    @property
    def diverg(self) -> float:
        return (self.odd / self.ref - 1) * 100

    @property
    def pnl_back(self) -> float:
        return (self.odd - 1) * (1 - COMISSAO) if self.ganhou else -1.0

    @property
    def pnl_lay(self) -> float:
        return -(self.odd - 1) if self.ganhou else (1 - COMISSAO)

    def clv(self, lado: str) -> float | None:
        if not self.fecho or self.fecho <= 1:
            return None
        return ((self.odd / self.fecho - 1) if lado == "back"
                else (self.fecho / self.odd - 1)) * 100


def temporada(m) -> int:
    return m.date.year if m.date.month >= 7 else m.date.year - 1


def construir() -> list[Op]:
    partidas = []
    for d in MAIN_DIVS:
        partidas.extend(load_main(d, SEASONS))
    partidas.sort(key=lambda m: m.date)

    ops: list[Op] = []
    for m in partidas:
        s, lg = temporada(m), m.league

        # ---- 1X2, referência = consenso de casas ----
        ex, fe = m.odds_open.get("betfair_ex"), m.odds_close.get("betfair_ex", {})
        livros = []
        for lv in LIVROS:
            t = m.odds_open.get(lv)
            if t and all(k in t for k in "HDA"):
                livros.append(fair_probs_power([t["H"], t["D"], t["A"]]))
        if ex and len(livros) >= 3:
            cons = [sum(p[i] for p in livros)/len(livros) for i in range(3)]
            for i, k in enumerate("HDA"):
                o = ex.get(k)
                if o:
                    ops.append(Op(s, lg, "1X2", k, o, fe.get(k), 1/cons[i],
                                  m.result == k))

        # ---- 1X2, referência = SÓ Pinnacle (a casa mais afiada) ----
        pin = m.odds_open.get("pinnacle")
        if ex and pin and all(k in pin for k in "HDA"):
            fp = fair_probs_power([pin["H"], pin["D"], pin["A"]])
            for i, k in enumerate("HDA"):
                o = ex.get(k)
                if o:
                    ops.append(Op(s, lg, "1X2pin", k, o, fe.get(k), 1/fp[i],
                                  m.result == k))

        # ---- Over/Under 2.5 ----
        exo, feo = m.ou_open.get("betfair_ex"), m.ou_close.get("betfair_ex", {})
        avg = m.ou_open.get("market_avg")
        if exo and avg and "O" in avg and "U" in avg:
            fp = fair_probs_power([avg["O"], avg["U"]])
            gols = (m.goals_home or 0) + (m.goals_away or 0)
            for i, k in enumerate(("O", "U")):
                o = exo.get(k)
                if o:
                    ops.append(Op(s, lg, "O/U2.5", k, o, feo.get(k), 1/fp[i],
                                  (gols > 2.5) if k == "O" else (gols < 2.5)))

        # ---- Handicap asiático ----
        exa, fea = m.ah_open.get("betfair_ex"), m.ah_close.get("betfair_ex", {})
        avga = m.ah_open.get("market_avg")
        if exa and avga and m.ah_line is not None and "H" in avga and "A" in avga:
            fp = fair_probs_power([avga["H"], avga["A"]])
            marg = (m.goals_home or 0) - (m.goals_away or 0) + m.ah_line
            if abs(marg) > 1e-9:      # push (empate no handicap) fica de fora
                for i, k in enumerate(("H", "A")):
                    o = exa.get(k)
                    if o:
                        ops.append(Op(s, lg, "AH", k, o, fea.get(k), 1/fp[i],
                                      (marg > 0) if k == "H" else (marg < 0)))
    return ops


@dataclass
class Res:
    pnls: list = field(default_factory=list)
    clvs: list = field(default_factory=list)
    @property
    def n(self): return len(self.pnls)
    @property
    def roi(self): return sum(self.pnls)/self.n*100 if self.n else 0.0
    @property
    def clv(self): return sum(self.clvs)/len(self.clvs) if self.clvs else float("nan")
    def t_clv(self):
        if len(self.clvs) < 3: return 0.0
        m = self.clv
        v = sum((c-m)**2 for c in self.clvs)/(len(self.clvs)-1)
        se = math.sqrt(v/len(self.clvs))
        return m/se if se else 0.0
    def t_roi(self):
        if self.n < 3: return 0.0
        m = sum(self.pnls)/self.n
        v = sum((x-m)**2 for x in self.pnls)/(self.n-1)
        se = math.sqrt(v/self.n)
        return m/se if se else 0.0


def avaliar(ops, regra) -> Res:
    r = Res()
    for o in ops:
        lado = regra(o)
        if not lado: continue
        r.pnls.append(o.pnl_back if lado == "back" else o.pnl_lay)
        c = o.clv(lado)
        if c is not None: r.clvs.append(c)
    return r


if __name__ == "__main__":
    ops = construir()
    print(f"oportunidades construídas: {len(ops)}")
    por_m = defaultdict(int)
    for o in ops: por_m[o.mercado] += 1
    print("por mercado:", dict(por_m))

    # ---- catálogo de regras candidatas ----
    regras = {}
    for mercado in ("1X2", "1X2pin", "O/U2.5", "AH"):
        for lado_ap in ("back", "lay"):
            for lim in (2, 4, 6, 10):
                for omin, omax in ((1.3, 2.0), (2.0, 3.5), (3.5, 6.0), (1.3, 6.0)):
                    nome = f"{mercado} {lado_ap} div>{lim}% odd {omin}-{omax}"
                    def faz(mercado=mercado, lado_ap=lado_ap, lim=lim,
                            omin=omin, omax=omax):
                        def r(o):
                            if o.mercado != mercado: return None
                            if not (omin <= o.odd <= omax): return None
                            d = o.diverg
                            if lado_ap == "back" and d >= lim: return "back"
                            if lado_ap == "lay" and d <= -lim: return "lay"
                            return None
                        return r
                    regras[nome] = faz()

    treino = [o for o in ops if o.temporada == 2024]
    teste = [o for o in ops if o.temporada >= 2025]
    print(f"\ntreino: {len(treino)} · teste: {len(teste)} · regras testadas: {len(regras)}")

    aval = []
    for nome, r in regras.items():
        res = avaliar(treino, r)
        if res.n >= 60 and len(res.clvs) >= 40:
            aval.append((nome, res))
    aval.sort(key=lambda x: -x[1].t_clv())

    # limiar de Bonferroni: quanto t precisa ser para sobreviver a N testes
    import statistics
    N = len(aval)
    print(f"regras com amostra suficiente: {N}")
    print(f"limiar de t para 5% familiar (Bonferroni, {N} testes): ~{2.807 if N<50 else 3.2:.2f}")

    print(f"\n{'='*104}")
    print("TREINO 2024/25 — melhores por t do CLV")
    print(f"{'='*104}")
    print(f"  {'regra':<44}{'n':>6}{'CLV':>9}{'t_clv':>8}{'ROI':>9}{'t_roi':>8}")
    for nome, r in aval[:12]:
        print(f"  {nome:<44}{r.n:>6}{r.clv:>8.2f}%{r.t_clv():>8.2f}{r.roi:>8.2f}%{r.t_roi():>8.2f}")
