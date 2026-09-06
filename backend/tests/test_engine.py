"""Testes do núcleo matemático e dos detectores."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from roimax.engine import math as m
from roimax.engine.detectors import Context, Thresholds, build_consensus, run_all
from roimax.models import Event, MarketBook, Outcome, Quote, SignalKind


def test_prob_odds_roundtrip():
    assert m.to_odds(m.to_prob(3.4)) == pytest.approx(3.4)


def test_overround_detecta_margem():
    assert m.overround([2.0, 2.0]) == pytest.approx(1.0)
    assert m.overround([1.9, 1.9]) > 1.0


def test_fair_probs_somam_um():
    for fn in (m.fair_probs_proportional, m.fair_probs_power):
        probs = fn([2.10, 3.40, 3.80])
        assert sum(probs) == pytest.approx(1.0, abs=1e-6)
        assert all(0 < p < 1 for p in probs)


def test_power_corrige_mais_que_proporcional_no_azarao():
    odds = [1.30, 5.50, 12.0]
    prop = m.fair_probs_proportional(odds)
    pw = m.fair_probs_power(odds)
    # o método da potência puxa o azarão para baixo
    assert pw[-1] < prop[-1]


def test_ev_back_zero_no_preco_justo():
    p = 0.5
    assert m.ev_back(p, 2.0, commission=0.0) == pytest.approx(0.0)


def test_ev_back_positivo_acima_do_justo():
    assert m.ev_back(0.5, 2.2, commission=0.0) > 0


def test_comissao_reduz_ev():
    assert m.ev_back(0.5, 2.2, 0.065) < m.ev_back(0.5, 2.2, 0.0)


def test_ev_lay_espelha_back():
    # lay a 2.0 com prob real 0.5 e sem comissão é neutro
    assert m.ev_lay(0.5, 2.0, commission=0.0) == pytest.approx(0.0)


def test_kelly_zero_sem_valor():
    assert m.kelly_back(0.4, 2.0) == 0.0
    assert m.kelly_back(0.6, 2.0) > 0.0


def test_spread_pct():
    assert m.spread_pct(2.00, 2.02) < m.spread_pct(2.00, 2.40)


# ------------------------------------------------------------- fixtures

def _book(exch: dict, softs: dict[str, dict]) -> MarketBook:
    ev = Event(id="e1", home="Flamengo", away="Palmeiras",
               commence_time=datetime.now(timezone.utc) + timedelta(hours=2),
               league="Brasileirão")
    quotes = []
    for oc, (b, l) in exch.items():
        quotes.append(Quote(event_id="e1", bookmaker="betfair_ex_uk",
                            outcome=oc, back=b, lay=l))
    for name, trio in softs.items():
        for oc, price in trio.items():
            quotes.append(Quote(event_id="e1", bookmaker=name, outcome=oc, back=price))
    return MarketBook(event=ev, quotes=quotes)


BALANCED = {
    "pinnacle": {Outcome.HOME: 2.05, Outcome.DRAW: 3.40, Outcome.AWAY: 3.75},
    "bet365": {Outcome.HOME: 2.00, Outcome.DRAW: 3.40, Outcome.AWAY: 3.70},
    "williamhill": {Outcome.HOME: 2.02, Outcome.DRAW: 3.35, Outcome.AWAY: 3.80},
    "betvictor": {Outcome.HOME: 2.05, Outcome.DRAW: 3.30, Outcome.AWAY: 3.75},
}


def test_consenso_ignora_exchange():
    book = _book({Outcome.HOME: (2.10, 2.14)}, BALANCED)
    cons = build_consensus(book)
    assert cons is not None
    assert "betfair_ex_uk" not in cons.books
    assert cons.n_books == 4
    assert sum(cons.probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_sem_sinal_quando_exchange_alinhada():
    """Exchange no mesmo preço do consenso: nada deve disparar."""
    exch = {Outcome.HOME: (2.12, 2.16), Outcome.DRAW: (3.60, 3.70),
            Outcome.AWAY: (3.95, 4.05)}
    sigs = run_all(_book(exch, BALANCED), Context())
    assert not [s for s in sigs if s.kind in
                (SignalKind.VALUE_BACK, SignalKind.VALUE_LAY)]


def test_value_back_quando_exchange_paga_demais():
    exch = {Outcome.HOME: (2.60, 2.66), Outcome.DRAW: (3.60, 3.70),
            Outcome.AWAY: (3.95, 4.05)}
    sigs = run_all(_book(exch, BALANCED), Context())
    backs = [s for s in sigs if s.kind == SignalKind.VALUE_BACK]
    assert backs, "deveria detectar back de valor"
    s = backs[0]
    assert s.outcome == Outcome.HOME and s.side == "back"
    assert s.ev > 0 and s.edge_pct > 0 and s.kelly > 0


def test_value_lay_quando_exchange_cobra_de_menos():
    exch = {Outcome.HOME: (1.70, 1.74), Outcome.DRAW: (3.60, 3.70),
            Outcome.AWAY: (3.95, 4.05)}
    sigs = run_all(_book(exch, BALANCED), Context())
    lays = [s for s in sigs if s.kind == SignalKind.VALUE_LAY]
    assert lays, "deveria detectar lay de valor"
    assert lays[0].side == "lay" and lays[0].ev > 0


def test_book_fino_e_descartado():
    """Spread largo demais invalida o sinal de valor: preço não é executável."""
    exch = {Outcome.HOME: (2.60, 3.40), Outcome.DRAW: (3.60, 3.70),
            Outcome.AWAY: (3.95, 4.05)}
    sigs = run_all(_book(exch, BALANCED), Context())
    assert not [s for s in sigs if s.kind == SignalKind.VALUE_BACK]
    assert [s for s in sigs if s.kind == SignalKind.WIDE_SPREAD]


def test_consenso_raso_nao_gera_sinal():
    softs = {"pinnacle": BALANCED["pinnacle"]}
    exch = {Outcome.HOME: (2.60, 2.66), Outcome.DRAW: (3.60, 3.70),
            Outcome.AWAY: (3.95, 4.05)}
    sigs = run_all(_book(exch, softs), Context(thresholds=Thresholds(min_books=3)))
    assert not [s for s in sigs if s.kind == SignalKind.VALUE_BACK]


def test_arbitragem():
    softs = {
        "pinnacle": {Outcome.HOME: 3.60, Outcome.DRAW: 3.40, Outcome.AWAY: 3.75},
        "bet365": {Outcome.HOME: 2.00, Outcome.DRAW: 4.40, Outcome.AWAY: 3.70},
        "williamhill": {Outcome.HOME: 2.02, Outcome.DRAW: 3.35, Outcome.AWAY: 5.20},
    }
    sigs = run_all(_book({}, softs), Context())
    assert [s for s in sigs if s.kind == SignalKind.ARBITRAGE]


def test_steam_detecta_movimento():
    exch = {Outcome.HOME: (2.60, 2.66)}
    book = _book(exch, BALANCED)
    hist = [Quote(event_id="e1", bookmaker="betfair_ex_uk", outcome=Outcome.HOME,
                  back=2.20, lay=2.24,
                  ts=datetime.now(timezone.utc) - timedelta(minutes=5))]
    ctx = Context(history={("e1", "betfair_ex_uk", "HOME"): hist})
    sigs = run_all(book, ctx)
    steam = [s for s in sigs if s.kind == SignalKind.STEAM]
    assert steam and steam[0].edge_pct > 6


# ---------------------------------- regressões das correções pós-revisão

def test_exchange_so_com_back_ainda_gera_sinal():
    """No histórico só existe o preço de back — o motor não pode ficar cego.

    Exigir os dois lados aqui zerava o backtest inteiro.
    """
    ev = Event(id="e1", home="Flamengo", away="Palmeiras",
               commence_time=datetime.now(timezone.utc) + timedelta(hours=2))
    quotes = [Quote(event_id="e1", bookmaker="betfair_ex", outcome=Outcome.HOME,
                    back=2.60, lay=None)]
    for name, trio in BALANCED.items():
        for oc, price in trio.items():
            quotes.append(Quote(event_id="e1", bookmaker=name, outcome=oc, back=price))
    book = MarketBook(event=ev, quotes=quotes)

    assert book.exchange_book(), "book da exchange não pode sumir sem o lay"
    backs = [s for s in run_all(book, Context()) if s.kind == SignalKind.VALUE_BACK]
    assert backs and backs[0].outcome == Outcome.HOME


def test_sportsbook_da_betfair_nao_e_confundida_com_a_exchange():
    ev = Event(id="e1", home="A", away="B",
               commence_time=datetime.now(timezone.utc) + timedelta(hours=2))
    quotes = [
        Quote(event_id="e1", bookmaker="betfair_sb_uk", outcome=Outcome.HOME, back=2.60),
        Quote(event_id="e1", bookmaker="betfair_ex_uk", outcome=Outcome.HOME,
              back=2.10, lay=2.14),
    ]
    book = MarketBook(event=ev, quotes=quotes)
    exch = book.exchange_book()
    assert exch[Outcome.HOME].back == 2.10  # a exchange, não a sportsbook


def test_agregados_ficam_fora_do_consenso():
    """`market_max` não é uma casa: é a máxima das outras, e infla o justo."""
    ev = Event(id="e1", home="A", away="B",
               commence_time=datetime.now(timezone.utc) + timedelta(hours=2))
    quotes = []
    for name, trio in BALANCED.items():
        for oc, price in trio.items():
            quotes.append(Quote(event_id="e1", bookmaker=name, outcome=oc, back=price))
    for oc, price in {Outcome.HOME: 2.30, Outcome.DRAW: 3.60, Outcome.AWAY: 4.10}.items():
        quotes.append(Quote(event_id="e1", bookmaker="market_max", outcome=oc, back=price))

    cons = build_consensus(MarketBook(event=ev, quotes=quotes))
    assert cons is not None
    assert "market_max" not in cons.books
    assert cons.n_books == 4


def test_arbitragem_ignora_agregados():
    """A máxima do mercado soma < 1 por construção: seria arb fantasma."""
    ev = Event(id="e1", home="A", away="B",
               commence_time=datetime.now(timezone.utc) + timedelta(hours=2))
    quotes = [
        Quote(event_id="e1", bookmaker="market_max", outcome=oc, back=p)
        for oc, p in {Outcome.HOME: 3.60, Outcome.DRAW: 4.40, Outcome.AWAY: 5.20}.items()
    ]
    sigs = run_all(MarketBook(event=ev, quotes=quotes), Context())
    assert not [s for s in sigs if s.kind == SignalKind.ARBITRAGE]
