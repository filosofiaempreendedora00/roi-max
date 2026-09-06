"""Detectores de assimetria.

A ideia central: a Betfair Exchange é o mercado mais eficiente que existe em
futebol, então na maior parte do tempo ela ESTÁ certa. O sinal aparece quando
o preço da exchange diverge do consenso das casas tradicionais além do que a
margem delas explica — ou quando o próprio book da exchange fica fino ou se
move rápido demais.

Cada detector é independente e devolve zero ou mais Signals.
"""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from ..config import settings
from ..deeplink import market_url
from ..models import MarketBook, Outcome, Quote, Signal, SignalKind, utcnow
from .math import (
    edge_pct,
    ev_back,
    ev_lay,
    fair_probs_power,
    kelly_back,
    kelly_lay,
    mid_prob,
    spread_pct,
    to_odds,
    to_prob,
)

ORDER = [Outcome.HOME, Outcome.DRAW, Outcome.AWAY]

# Colunas derivadas do histórico (média e máxima do mercado) não são opiniões
# independentes: são agregados das mesmas casas que já estão na lista. A máxima,
# em particular, tem overround artificialmente baixo — entra no consenso como
# se fosse uma casa generosa e inventa valor que não existe.
AGGREGATE_BOOKS = {"market_max", "market_avg"}


@dataclass
class Thresholds:
    """Todos os gatilhos em um lugar só, para você calibrar depois do backtest."""

    min_edge_pct: float = 4.0       # divergência mínima vs consenso
    min_ev: float = 0.02            # EV mínimo por unidade arriscada
    min_books: int = 3              # casas necessárias para um consenso confiável
    max_book_stdev: float = 0.05    # desacordo máximo entre casas (em prob.)
    max_spread_pct: float = 8.0     # acima disso o book é fino demais p/ confiar
    wide_spread_pct: float = 12.0   # a partir daqui vira sinal de market making
    steam_pct: float = 6.0          # movimento de preço p/ disparar STEAM
    steam_window_min: int = 10
    arb_margin: float = 0.005       # folga exigida na arbitragem (0.5%)
    signal_ttl_min: int = 15


@dataclass
class Context:
    thresholds: Thresholds = field(default_factory=Thresholds)
    commission: float = field(default_factory=lambda: settings.betfair_commission)
    history: dict[tuple[str, str, str], list[Quote]] = field(default_factory=dict)


# --------------------------------------------------------------- consenso

@dataclass
class Consensus:
    """Probabilidade justa estimada a partir das casas tradicionais."""

    probs: dict[Outcome, float]
    n_books: int
    stdev: float
    books: list[str]

    @property
    def reliable(self) -> bool:
        return self.n_books >= 1 and self.stdev < 1.0


def build_consensus(book: MarketBook, exclude_prefix: str = "betfair") -> Consensus | None:
    """Média das probabilidades sem margem de cada casa tradicional.

    Cada casa tem a margem removida separadamente (método da potência) ANTES
    da média. Fazer o contrário — média das odds cruas — embute a margem no
    resultado e inventa valor que não existe.
    """
    per_book: list[list[float]] = []
    names: list[str] = []
    for bk in book.bookmakers:
        if bk.startswith(exclude_prefix) or bk in AGGREGATE_BOOKS:
            continue
        quotes = book.by_bookmaker(bk)
        odds = [quotes[o].back for o in ORDER if o in quotes and quotes[o].back]
        if len(odds) != 3:
            continue
        per_book.append(fair_probs_power(odds))
        names.append(bk)

    if not per_book:
        return None

    probs = {}
    devs = []
    for i, oc in enumerate(ORDER):
        col = [p[i] for p in per_book]
        probs[oc] = statistics.fmean(col)
        devs.append(statistics.pstdev(col) if len(col) > 1 else 0.0)

    return Consensus(probs=probs, n_books=len(per_book),
                     stdev=statistics.fmean(devs), books=names)


def _confidence(c: Consensus, t: Thresholds) -> float:
    """0..1. Cresce com o número de casas, cai com o desacordo entre elas."""
    depth = min(1.0, c.n_books / max(t.min_books, 1))
    agree = max(0.0, 1.0 - (c.stdev / t.max_book_stdev)) if t.max_book_stdev > 0 else 0.0
    return round(min(1.0, depth * 0.5 + min(1.0, agree) * 0.5), 3)


def _new_signal(book: MarketBook, oc: Outcome, **kw) -> Signal:
    t = kw.pop("ttl_min", 15)
    return Signal(
        id=uuid.uuid4().hex[:12],
        event_id=book.event.id,
        event_label=book.event.label,
        league=book.event.league,
        outcome=oc,
        deeplink=market_url(book.event),
        expires_at=utcnow() + timedelta(minutes=t),
        **kw,
    )


# --------------------------------------------------------------- detectores

def detect_value(book: MarketBook, ctx: Context) -> list[Signal]:
    """Exchange fora de linha com o consenso das casas.

    BACK quando a exchange paga mais do que o justo.
    LAY quando a exchange cobra menos do que o justo.
    """
    t = ctx.thresholds
    exch = book.exchange_book()
    if not exch:
        return []
    cons = build_consensus(book)
    if cons is None or cons.n_books < t.min_books or cons.stdev > t.max_book_stdev:
        return []

    conf = _confidence(cons, t)
    out: list[Signal] = []
    bk_name = next((b for b in book.bookmakers if b.startswith("betfair_ex")), "betfair_ex")

    for oc in ORDER:
        q = exch.get(oc)
        if not q or not q.back:
            continue
        # book fino: o preço não é confiável nem executável. Só dá para medir
        # quando os dois lados são conhecidos (no histórico, o lay não existe).
        if q.lay and spread_pct(q.back, q.lay) > t.max_spread_pct:
            continue

        p_fair = cons.probs[oc]
        fair = to_odds(p_fair)

        # BACK: quero receber MAIS do que o justo
        e = edge_pct(fair, q.back)
        ev = ev_back(p_fair, q.back, ctx.commission)
        if e >= t.min_edge_pct and ev >= t.min_ev:
            out.append(_new_signal(
                book, oc, kind=SignalKind.VALUE_BACK, side="back",
                market_odds=q.back, fair_odds=round(fair, 3), edge_pct=round(e, 2),
                ev=round(ev, 4), kelly=round(kelly_back(p_fair, q.back, ctx.commission), 4),
                confidence=conf, bookmaker=bk_name,
                reference=f"consenso de {cons.n_books} casas",
                ttl_min=t.signal_ttl_min,
                notes=f"Exchange paga {q.back:.2f}, justo {fair:.2f}.",
            ))
            continue

        # LAY: quero pagar MENOS do que o justo
        if not q.lay:
            continue
        e_lay = -edge_pct(fair, q.lay)
        ev_l = ev_lay(p_fair, q.lay, ctx.commission)
        if e_lay >= t.min_edge_pct and ev_l >= t.min_ev:
            out.append(_new_signal(
                book, oc, kind=SignalKind.VALUE_LAY, side="lay",
                market_odds=q.lay, fair_odds=round(fair, 3), edge_pct=round(e_lay, 2),
                ev=round(ev_l, 4), kelly=round(kelly_lay(p_fair, q.lay, ctx.commission), 4),
                confidence=conf, bookmaker=bk_name,
                reference=f"consenso de {cons.n_books} casas",
                ttl_min=t.signal_ttl_min,
                notes=f"Exchange cobra {q.lay:.2f} para lay, justo {fair:.2f}.",
            ))

    return out


def detect_arbitrage(book: MarketBook, ctx: Context) -> list[Signal]:
    """Melhor back de cada resultado, em casas diferentes, somando < 1."""
    t = ctx.thresholds
    best: dict[Outcome, tuple[float, str]] = {}
    for q in book.quotes:
        if not q.back or q.bookmaker in AGGREGATE_BOOKS:
            continue  # a máxima do mercado somaria < 1 sempre: arb fantasma
        cur = best.get(q.outcome)
        if cur is None or q.back > cur[0]:
            best[q.outcome] = (q.back, q.bookmaker)

    if len(best) != 3:
        return []
    total = sum(to_prob(best[oc][0]) for oc in ORDER)
    if total >= 1.0 - t.arb_margin:
        return []

    profit = (1.0 / total - 1.0) * 100.0
    legs = ", ".join(f"{oc.value} {best[oc][0]:.2f}@{best[oc][1]}" for oc in ORDER)
    return [_new_signal(
        book, Outcome.HOME, kind=SignalKind.ARBITRAGE, side="back",
        market_odds=best[Outcome.HOME][0], fair_odds=round(to_odds(total / 3), 3),
        edge_pct=round(profit, 2), ev=round(profit / 100.0, 4), kelly=0.0,
        confidence=1.0, bookmaker="multi", reference="melhor preço por resultado",
        ttl_min=5,
        notes=f"Overround {total:.4f} -> lucro travado {profit:.2f}%. Pernas: {legs}",
    )]


def detect_wide_spread(book: MarketBook, ctx: Context) -> list[Signal]:
    """Book fino na exchange: espaço para entrar na frente da fila."""
    t = ctx.thresholds
    exch = book.exchange_book()
    out: list[Signal] = []
    for oc in ORDER:
        q = exch.get(oc)
        if not q or not q.back or not q.lay:
            continue
        sp = spread_pct(q.back, q.lay)
        if sp < t.wide_spread_pct or sp == float("inf"):
            continue
        p = mid_prob(q.back, q.lay)
        out.append(_new_signal(
            book, oc, kind=SignalKind.WIDE_SPREAD, side="back",
            market_odds=q.back, fair_odds=round(to_odds(p), 3),
            edge_pct=round(sp, 2), ev=0.0, kelly=0.0,
            confidence=0.4, bookmaker=q.bookmaker, reference="book da exchange",
            ttl_min=10,
            notes=f"Spread de {sp:.1f}% entre back {q.back:.2f} e lay {q.lay:.2f}. "
                  f"Liquidez baixa: confirme o volume antes de entrar.",
        ))
    return out


def detect_steam(book: MarketBook, ctx: Context) -> list[Signal]:
    """Movimento rápido de preço na exchange dentro da janela recente.

    Steam costuma indicar informação nova entrando no mercado (escalação,
    lesão, dinheiro grande). Não é valor por si só — é aviso de que o preço
    de referência envelheceu.
    """
    t = ctx.thresholds
    exch = book.exchange_book()
    out: list[Signal] = []
    cutoff = utcnow() - timedelta(minutes=t.steam_window_min)

    for oc in ORDER:
        q = exch.get(oc)
        if not q or not q.back:
            continue
        hist = ctx.history.get((book.event.id, q.bookmaker, oc.value), [])
        past = [h for h in hist if h.ts >= cutoff and h.back]
        if len(past) < 2:
            continue
        oldest = min(past, key=lambda h: h.ts)
        if not oldest.back:
            continue
        move = (q.back / oldest.back - 1.0) * 100.0
        if abs(move) < t.steam_pct:
            continue
        direction = "afastou" if move > 0 else "encurtou"
        out.append(_new_signal(
            book, oc, kind=SignalKind.STEAM, side="back" if move > 0 else "lay",
            market_odds=q.back, fair_odds=oldest.back,
            edge_pct=round(move, 2), ev=0.0, kelly=0.0,
            confidence=0.5, bookmaker=q.bookmaker, reference="preço próprio",
            ttl_min=8,
            notes=f"Preço {direction} {abs(move):.1f}% em {t.steam_window_min} min "
                  f"({oldest.back:.2f} -> {q.back:.2f}).",
        ))
    return out


ALL_DETECTORS = [detect_value, detect_arbitrage, detect_wide_spread, detect_steam]


def run_all(book: MarketBook, ctx: Context | None = None) -> list[Signal]:
    ctx = ctx or Context()
    signals: list[Signal] = []
    for det in ALL_DETECTORS:
        try:
            signals.extend(det(book, ctx))
        except Exception:  # um detector quebrado não pode derrubar os outros
            continue
    signals.sort(key=lambda s: (s.ev, s.confidence), reverse=True)
    return signals
