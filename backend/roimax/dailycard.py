"""A carta do dia.

Um punhado de entradas, uma vez por dia, prontas para executar e deixar
rolar. Nada de acompanhar jogo.

Três coisas que a carta faz e uma varredura crua não faz:

1. **Ordena e corta.** Vinte sinais fracos são piores que quatro fortes:
   diluem a banca e enterram o que importa.
2. **Diversifica.** Duas entradas no mesmo jogo não são duas apostas, são
   uma aposta com o dobro do tamanho. O limite por evento e por liga existe
   para o resultado de um jogo não decidir o seu dia.
3. **Dá o preço-limite.** O preço se move entre o sinal e o seu toque. Sem
   um piso explícito você entra num preço que já não tem vantagem — e é
   assim que uma carteira de EV positivo vira uma de EV negativo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_cls

from . import clv, db
from .config import settings
from .engine.math import snap_price
from .models import CardEntry, DailyCard, Signal, utcnow

log = logging.getLogger(__name__)


@dataclass
class CardConfig:
    max_entries: int = 5
    max_per_event: int = 1
    max_per_league: int = 2
    bankroll: float = 1000.0
    kelly_fraction: float = 0.25    # Kelly cheio quebra banca; um quarto é o usual
    max_stake_pct: float = 0.02     # teto duro de 2% da banca por entrada
    min_stake: float = 1.0


def limit_price(sig: Signal, target_ev: float, commission: float) -> float:
    """Preço a partir do qual a entrada ainda vale a pena.

    Resolve a equação de EV para as odds, dado o EV alvo. Para back é um
    piso (entre se pagar isso ou mais); para lay é um teto (entre se cobrar
    isso ou menos).
    """
    p = 1.0 / sig.fair_odds if sig.fair_odds > 0 else 0.0
    if p <= 0 or p >= 1:
        return sig.market_odds

    if sig.side == "back":
        # p*(o-1)*(1-c) - (1-p) = alvo
        raw = 1.0 + (target_ev + 1.0 - p) / (p * (1.0 - commission))
    else:
        # lay: (1-p)*(1-c) - p*(o-1) = alvo
        raw = 1.0 + ((1.0 - p) * (1.0 - commission) - target_ev) / p
    return snap_price(raw, sig.side)


def _stake(sig: Signal, cfg: CardConfig) -> float:
    raw = cfg.bankroll * sig.kelly * cfg.kelly_fraction
    capped = min(raw, cfg.bankroll * cfg.max_stake_pct)
    return round(max(cfg.min_stake, capped), 2) if capped > 0 else 0.0


def _reason(sig: Signal) -> str:
    lado = "Back" if sig.side == "back" else "Lay"
    return (f"{lado} a {sig.market_odds:.2f} contra justo {sig.fair_odds:.2f} "
            f"({sig.edge_pct:+.1f}%), pelo {sig.reference}.")


def build(
    signals: list[Signal],
    *,
    cfg: CardConfig | None = None,
    target_ev: float = 0.0,
    scanned_events: int = 0,
    commission: float | None = None,
) -> DailyCard:
    cfg = cfg or CardConfig()
    commission = settings.betfair_commission if commission is None else commission

    # só o que é acionável e ainda não começou
    live = [s for s in signals if s.is_live and s.ev > 0 and s.kelly > 0]
    # o mais forte primeiro: EV ponderado pela confiança do consenso
    live.sort(key=lambda s: s.ev * max(s.confidence, 0.1), reverse=True)

    entries: list[CardEntry] = []
    per_event: dict[str, int] = {}
    per_league: dict[str, int] = {}

    for sig in live:
        if len(entries) >= cfg.max_entries:
            break
        if per_event.get(sig.event_id, 0) >= cfg.max_per_event:
            continue
        if per_league.get(sig.league, 0) >= cfg.max_per_league:
            continue
        stake = _stake(sig, cfg)
        if stake <= 0:
            continue

        entries.append(CardEntry(
            signal=sig, stake=stake, rank=len(entries) + 1,
            limit_price=limit_price(sig, target_ev, commission),
            reason=_reason(sig),
        ))
        per_event[sig.event_id] = per_event.get(sig.event_id, 0) + 1
        per_league[sig.league] = per_league.get(sig.league, 0) + 1

    card = DailyCard(
        date=date_cls.today().isoformat(),
        entries=entries,
        scanned_events=scanned_events,
        bankroll=cfg.bankroll,
        total_stake=round(sum(e.stake for e in entries), 2),
        note=_note(entries, scanned_events),
    )
    db.save_card(card)

    # cada entrada vira palpite rastreável: é o que alimenta o CLV real
    for e in entries:
        ev_row = db.get_event(e.signal.event_id)
        if ev_row:
            clv.record(e.signal, ev_row.commence_time, stake=e.stake)

    return card


def _note(entries: list[CardEntry], scanned: int) -> str:
    if not entries:
        return ("Nenhuma entrada hoje. Dia sem carta é normal e é sinal de "
                "filtro funcionando — o mercado da Betfair é eficiente na "
                "maior parte do tempo.")
    return (f"{len(entries)} entrada(s) de {scanned} jogos varridos. "
            f"Respeite o preço-limite: abaixo dele a vantagem já foi embora.")


def summary_line() -> str:
    """Texto curto para a notificação — precisa caber na tela bloqueada."""
    card = db.latest_card()
    if not card or not card.entries:
        return "Nenhuma entrada hoje."
    st = clv.stats()
    tail = f" · CLV {st.mean_clv:+.1f}%" if st.n_with_closing >= 20 else ""
    return f"{len(card.entries)} entradas · R$ {card.total_stake:.0f}{tail}"
