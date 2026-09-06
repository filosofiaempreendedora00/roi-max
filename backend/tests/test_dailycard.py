"""Testes da carta do dia."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from roimax import db, dailycard
from roimax.models import Event, Outcome, Signal, SignalKind


def _sig(ev_id="e1", league="Liga", side="back", odds=2.60, fair=2.18,
         ev=0.15, kelly=0.08, conf=0.8) -> Signal:
    return Signal(
        id=f"s-{ev_id}-{side}-{odds}", kind=SignalKind.VALUE_BACK,
        event_id=ev_id, event_label=f"{ev_id} A x B", league=league,
        outcome=Outcome.HOME, side=side, market_odds=odds, fair_odds=fair,
        edge_pct=19.0, ev=ev, kelly=kelly, confidence=conf,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=3),
    )


def test_limit_price_back_devolve_o_preco_de_equilibrio():
    """No preço-limite com alvo 0, o EV tem que ser exatamente 0."""
    from roimax.engine.math import ev_back
    s = _sig(fair=2.00)
    lp = dailycard.limit_price(s, target_ev=0.0, commission=0.065)
    # encaixado para cima na escada, então o EV tem que ser >= 0 (nunca abaixo)
    assert ev_back(0.5, lp, 0.065) >= 0


def test_limit_price_lay_devolve_o_teto():
    from roimax.engine.math import ev_lay
    s = _sig(side="lay", fair=2.00)
    lp = dailycard.limit_price(s, target_ev=0.0, commission=0.065)
    # encaixado para baixo na escada, então o EV tem que ser >= 0 (nunca abaixo)
    assert ev_lay(0.5, lp, 0.065) >= 0


def test_limit_price_back_exige_preco_maior_que_o_justo():
    """Com comissão, empatar exige odds acima do justo."""
    s = _sig(fair=2.00)
    assert dailycard.limit_price(s, 0.0, 0.065) > 2.00


def test_carta_respeita_o_teto_de_entradas():
    sigs = [_sig(ev_id=f"e{i}", league=f"L{i}") for i in range(12)]
    card = dailycard.build(sigs, cfg=dailycard.CardConfig(max_entries=5))
    assert len(card.entries) == 5


def test_carta_nao_repete_o_mesmo_jogo():
    """Duas entradas no mesmo jogo são uma aposta com o dobro do tamanho."""
    sigs = [_sig(ev_id="mesmo", side="back", odds=2.6),
            _sig(ev_id="mesmo", side="lay", odds=1.9)]
    card = dailycard.build(sigs, cfg=dailycard.CardConfig(max_entries=5))
    assert len(card.entries) == 1


def test_carta_limita_por_liga():
    sigs = [_sig(ev_id=f"e{i}", league="Brasileirão") for i in range(6)]
    card = dailycard.build(sigs, cfg=dailycard.CardConfig(max_entries=5,
                                                          max_per_league=2))
    assert len(card.entries) == 2


def test_ordena_pelo_ev_ponderado_pela_confianca():
    fraco_mas_confiante = _sig(ev_id="a", league="A", ev=0.05, conf=1.0)
    forte_mas_duvidoso = _sig(ev_id="b", league="B", ev=0.09, conf=0.2)
    card = dailycard.build([fraco_mas_confiante, forte_mas_duvidoso],
                           cfg=dailycard.CardConfig(max_entries=2))
    # 0.05*1.0 = 0.050 vence 0.09*0.2 = 0.018
    assert card.entries[0].signal.event_id == "a"


def test_stake_tem_teto_duro():
    """Kelly pode sugerir demais; o teto de 2% da banca é inegociável."""
    s = _sig(kelly=0.9)
    card = dailycard.build([s], cfg=dailycard.CardConfig(bankroll=1000,
                                                         max_stake_pct=0.02))
    assert card.entries[0].stake == pytest.approx(20.0)


def test_carta_vazia_explica_o_silencio():
    card = dailycard.build([])
    assert card.entries == []
    assert "normal" in card.note.lower()


def test_sinal_sem_ev_nao_entra():
    """Steam e book fino têm EV zero: são avisos, não entradas."""
    card = dailycard.build([_sig(ev=0.0, kelly=0.0)])
    assert card.entries == []


def test_carta_vira_palpite_rastreavel():
    db.upsert_event(Event(id="e1", home="A", away="B",
                          commence_time=datetime.now(timezone.utc) + timedelta(hours=3)))
    dailycard.build([_sig(ev_id="e1")])
    picks = db.all_picks()
    assert len(picks) == 1 and picks[0].taken_odds == 2.60
