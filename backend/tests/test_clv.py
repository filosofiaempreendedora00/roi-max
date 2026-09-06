"""Testes do rastreio de CLV."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from roimax import clv, db
from roimax.models import (Event, MarketBook, Outcome, Pick, Quote, Signal,
                           SignalKind)


def _pick(taken=2.60, closing=None, side="back", league="Liga") -> Pick:
    return Pick(
        id=f"p{taken}{side}", signal_id="s1", event_id=f"e{taken}{side}",
        event_label="A x B", league=league, outcome=Outcome.HOME, side=side,
        taken_odds=taken, fair_odds=2.2, ev=0.1, closing_odds=closing,
        commence_time=datetime.now(timezone.utc) + timedelta(hours=2),
    )


def test_clv_back_positivo_quando_pegou_preco_maior():
    assert _pick(taken=2.60, closing=2.20).clv_pct == pytest.approx(18.18, abs=0.01)


def test_clv_back_negativo_quando_pegou_preco_menor():
    assert _pick(taken=2.00, closing=2.20).clv_pct < 0


def test_clv_lay_inverte_o_sinal():
    """No lay, pagar MENOS que o fechamento é que é bom."""
    assert _pick(taken=2.00, closing=2.20, side="lay").clv_pct > 0
    assert _pick(taken=2.60, closing=2.20, side="lay").clv_pct < 0


def test_clv_indefinido_sem_fechamento():
    assert _pick(closing=None).clv_pct is None


def _sig(ev_id="e1", odds=2.60) -> Signal:
    return Signal(id="s1", kind=SignalKind.VALUE_BACK, event_id=ev_id,
                  event_label="A x B", outcome=Outcome.HOME, side="back",
                  market_odds=odds, fair_odds=2.2, edge_pct=18, ev=0.1, kelly=0.05)


def test_record_preserva_o_preco_original():
    """O que interessa é o preço de quando o sinal apareceu, não o de agora."""
    ko = datetime.now(timezone.utc) + timedelta(hours=2)
    clv.record(_sig(odds=2.60), ko)
    clv.record(_sig(odds=3.10), ko)   # segundo sinal, mesmo lance
    picks = db.all_picks()
    assert len(picks) == 1 and picks[0].taken_odds == 2.60


def test_update_closing_grava_o_preco_corrente():
    ko = datetime.now(timezone.utc) + timedelta(hours=2)
    clv.record(_sig(odds=2.60), ko)
    book = MarketBook(
        event=Event(id="e1", home="A", away="B", commence_time=ko),
        quotes=[Quote(event_id="e1", bookmaker="betfair_ex_uk",
                      outcome=Outcome.HOME, back=2.20, lay=2.24)],
    )
    assert clv.update_closing([book]) == 1
    p = db.all_picks()[0]
    assert p.closing_odds == 2.20
    assert p.clv_pct == pytest.approx(18.18, abs=0.01)


def test_update_closing_ignora_jogo_ja_comecado():
    """Depois do apito o preço não é mais 'fechamento'."""
    ko = datetime.now(timezone.utc) - timedelta(minutes=5)
    clv.record(_sig(), ko)
    book = MarketBook(
        event=Event(id="e1", home="A", away="B", commence_time=ko),
        quotes=[Quote(event_id="e1", bookmaker="betfair_ex_uk",
                      outcome=Outcome.HOME, back=2.20, lay=2.24)],
    )
    assert clv.update_closing([book]) == 0


def test_stats_agrega():
    st = clv.stats([_pick(2.60, 2.20), _pick(2.00, 2.20)])
    assert st.n == 2 and st.n_with_closing == 2
    assert st.beat_rate == 50.0


def test_veredito_admite_amostra_pequena():
    st = clv.stats([_pick(2.60, 2.20)])
    assert "pequena" in st.verdict.lower()


def test_veredito_reconhece_clv_negativo():
    picks = [_pick(taken=2.00 + i * 0.001, closing=2.40) for i in range(25)]
    st = clv.stats(picks)
    assert st.mean_clv < 0
    assert "negativo" in st.verdict.lower()


def test_breakdown_por_liga():
    b = clv.breakdown([_pick(2.6, 2.2, league="EPL"),
                       _pick(2.7, 2.2, league="Serie A")])
    assert set(b) == {"EPL", "Serie A"}
