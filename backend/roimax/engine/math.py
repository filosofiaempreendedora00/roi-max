"""Matemática de precificação de apostas.

Convenções em todo o projeto:
  - `odds` são sempre decimais europeias (2.50 = 150% de lucro sobre o stake).
  - `prob` é probabilidade implícita em [0, 1].
  - `commission` é a comissão da exchange sobre o LUCRO LÍQUIDO do mercado.
"""
from __future__ import annotations

import math
from typing import Sequence

EPS = 1e-9


def to_prob(odds: float) -> float:
    """Odds decimais -> probabilidade implícita bruta (com margem embutida)."""
    if odds <= 1.0:
        return 1.0
    return 1.0 / odds


def to_odds(prob: float) -> float:
    """Probabilidade -> odds decimais."""
    if prob <= EPS:
        return float("inf")
    return 1.0 / prob


def overround(odds: Sequence[float]) -> float:
    """Soma das probabilidades implícitas. >1 = margem da casa; <1 = arbitragem."""
    return sum(to_prob(o) for o in odds)


def fair_probs_proportional(odds: Sequence[float]) -> list[float]:
    """Remove a margem dividindo proporcionalmente.

    Simples e rápido, mas tende a subestimar favoritos e superestimar azarões
    (o clássico favourite-longshot bias). Bom o bastante para triagem.
    """
    probs = [to_prob(o) for o in odds]
    total = sum(probs)
    if total <= EPS:
        return probs
    return [p / total for p in probs]


def fair_probs_power(odds: Sequence[float], tol: float = 1e-10) -> list[float]:
    """Remove a margem pelo método da potência: p_fair = p_bruta ** k.

    Encontra k tal que a soma feche em 1. Corrige melhor o viés
    favorito/azarão que o método proporcional, ao custo de uma busca binária.
    """
    probs = [to_prob(o) for o in odds]
    if sum(probs) <= EPS:
        return probs
    lo, hi = 0.2, 5.0
    for _ in range(200):
        k = (lo + hi) / 2
        s = sum(p**k for p in probs)
        if abs(s - 1.0) < tol:
            break
        # k maior -> probabilidades menores -> soma menor
        if s > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    out = [p**k for p in probs]
    total = sum(out)
    return [p / total for p in out]


def ev_back(prob: float, odds: float, commission: float = 0.0) -> float:
    """Valor esperado de um BACK de 1 unidade.

    Ganha (odds-1) líquido de comissão com probabilidade `prob`; perde 1 caso contrário.
    """
    win = (odds - 1.0) * (1.0 - commission)
    return prob * win - (1.0 - prob) * 1.0


def ev_lay(prob: float, odds: float, commission: float = 0.0) -> float:
    """Valor esperado de um LAY com 1 unidade de stake (backer's stake).

    Ganha o stake (líquido de comissão) se o evento NÃO ocorre;
    paga a liability (odds-1) se ocorre.
    """
    win = 1.0 * (1.0 - commission)
    return (1.0 - prob) * win - prob * (odds - 1.0)


def kelly_back(prob: float, odds: float, commission: float = 0.0) -> float:
    """Fração de Kelly para um BACK. Retorna 0 quando não há valor."""
    b = (odds - 1.0) * (1.0 - commission)
    if b <= EPS:
        return 0.0
    f = (prob * b - (1.0 - prob)) / b
    return max(0.0, f)


def kelly_lay(prob: float, odds: float, commission: float = 0.0) -> float:
    """Fração de Kelly para um LAY, expressa como fração da banca em LIABILITY."""
    liability = odds - 1.0
    if liability <= EPS:
        return 0.0
    q = 1.0 - prob
    win = 1.0 * (1.0 - commission)
    # aposta na não-ocorrência: odds efetivas = 1 + win/liability
    b = win / liability
    f = (q * b - prob) / b
    return max(0.0, f)


def edge_pct(fair_odds: float, market_odds: float) -> float:
    """Quanto o preço de mercado está acima do justo, em %.

    Positivo = o mercado paga mais do que deveria (bom para BACK).
    """
    if fair_odds <= EPS or math.isinf(fair_odds):
        return 0.0
    return (market_odds / fair_odds - 1.0) * 100.0


def spread_pct(back: float, lay: float) -> float:
    """Spread back/lay em % sobre o ponto médio (em espaço de probabilidade)."""
    if back <= 1.0 or lay <= 1.0:
        return float("inf")
    pb, pl = to_prob(back), to_prob(lay)
    mid = (pb + pl) / 2
    if mid <= EPS:
        return float("inf")
    return abs(pb - pl) / mid * 100.0


def mid_prob(back: float, lay: float) -> float:
    """Melhor estimativa da probabilidade real a partir do book da exchange.

    O ponto médio entre back e lay em espaço de probabilidade é o consenso
    do dinheiro, já livre da margem (numa exchange a margem é a comissão,
    não o overround).
    """
    return (to_prob(back) + to_prob(lay)) / 2.0
