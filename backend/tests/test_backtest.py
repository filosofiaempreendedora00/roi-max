"""Testes da liquidação e das métricas do backtest."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from roimax.backtest.replay import _book_from_match, _settle, run_backtest
from roimax.models import Outcome, Signal, SignalKind
from roimax.providers.footballdata_uk import HistoricalMatch


def _sig(side: str, outcome: Outcome, odds: float) -> Signal:
    return Signal(id="s", kind=SignalKind.VALUE_BACK, event_id="e",
                  event_label="A x B", outcome=outcome, side=side,
                  market_odds=odds, fair_odds=odds, edge_pct=0, ev=0, kelly=0)


def test_settle_back_ganhando_desconta_comissao():
    pnl, won = _settle(_sig("back", Outcome.HOME, 3.0), "H", 1.0, 0.065)
    assert won and pnl == pytest.approx(2.0 * 0.935)


def test_settle_back_perdendo():
    pnl, won = _settle(_sig("back", Outcome.HOME, 3.0), "A", 1.0, 0.065)
    assert not won and pnl == -1.0


def test_settle_lay_ganha_o_stake():
    pnl, won = _settle(_sig("lay", Outcome.HOME, 3.0), "A", 1.0, 0.065)
    assert won and pnl == pytest.approx(0.935)


def test_settle_lay_paga_liability():
    pnl, won = _settle(_sig("lay", Outcome.HOME, 3.0), "H", 1.0, 0.065)
    assert not won and pnl == pytest.approx(-2.0)


def _match(exch_h: float, result: str) -> HistoricalMatch:
    return HistoricalMatch(
        date=datetime(2025, 3, 1, tzinfo=timezone.utc), league="Teste",
        home="A", away="B", result=result, goals_home=1, goals_away=0,
        odds_open={
            "betfair_ex": {"H": exch_h, "D": 3.70, "A": 4.05},
            "pinnacle": {"H": 2.05, "D": 3.40, "A": 3.75},
            "bet365": {"H": 2.00, "D": 3.40, "A": 3.70},
            "williamhill": {"H": 2.02, "D": 3.35, "A": 3.80},
            "betvictor": {"H": 2.05, "D": 3.30, "A": 3.75},
        },
        odds_close={"betfair_ex": {"H": 2.20, "D": 3.60, "A": 3.95}},
    )


def test_book_reconstruido_sem_lay_por_padrao():
    book = _book_from_match(_match(2.60, "H"), lay_spread=0.0)
    assert book is not None
    exch = book.exchange_book()
    assert exch[Outcome.HOME].back == 2.60
    assert exch[Outcome.HOME].lay is None  # não inventamos preço


def test_backtest_gera_aposta_e_clv():
    res = run_backtest([_match(2.60, "H")])
    assert res.n == 1
    bet = res.bets[0]
    assert bet.side == "back" and bet.won
    # entrou a 2.60, fechou a 2.20 -> CLV bem positivo
    assert bet.clv_pct is not None and bet.clv_pct > 15
    assert res.roi_pct > 0


def test_backtest_ignora_partida_sem_exchange():
    m = _match(2.60, "H")
    m.odds_open.pop("betfair_ex")
    res = run_backtest([m])
    assert res.n == 0 and res.matches_scanned == 1


def test_drawdown_nunca_positivo():
    res = run_backtest([_match(2.60, "A"), _match(2.60, "H")])
    assert res.max_drawdown <= 0
