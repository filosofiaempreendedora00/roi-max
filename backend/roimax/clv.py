"""Rastreio de CLV — closing line value.

Por que este módulo existe: com o volume de um apostador pessoal, o ROI leva
anos para sair do ruído. No backtest, 17 apostas com odd média 4,85 deram ROI
de −75% por puro azar (esperavam-se 3,5 acertos, saiu 1). Nada se conclui daí.

O CLV dá sinal em dezenas de apostas, não em milhares, porque compara o preço
que você pegou com o preço de fechamento — que é a melhor estimativa que o
mercado produz. Bater o fechamento com consistência é a assinatura de método
que funciona; ROI positivo com CLV negativo é sorte que vai embora.

O preço de fechamento sai de graça: a cada varredura, os palpites de jogos que
ainda não começaram têm o preço atualizado. O último valor antes do apito
inicial é o fechamento.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from . import db
from .models import MarketBook, Pick, Signal, utcnow

log = logging.getLogger(__name__)


def record(sig: Signal, commence_time, stake: float = 0.0) -> Pick:
    """Registra um sinal como palpite rastreável.

    Se já existe palpite para o mesmo jogo/resultado/lado, o preço original é
    preservado: o que interessa medir é o preço que você teria pegado quando
    o sinal apareceu, não o de agora.
    """
    existing = db.find_pick(sig.event_id, sig.outcome.value, sig.side)
    if existing:
        return existing

    pick = Pick(
        id=uuid.uuid4().hex[:12],
        signal_id=sig.id,
        event_id=sig.event_id,
        event_label=sig.event_label,
        league=sig.league,
        outcome=sig.outcome,
        side=sig.side,
        taken_odds=sig.market_odds,
        fair_odds=sig.fair_odds,
        ev=sig.ev,
        stake=stake,
        commence_time=commence_time,
    )
    db.save_pick(pick)
    return pick


def update_closing(books: list[MarketBook]) -> int:
    """Atualiza o preço corrente dos palpites abertos.

    Chamado a cada varredura. O último valor gravado antes do jogo começar
    vira o preço de fechamento — sem custo extra de crédito, porque
    aproveita a varredura que já aconteceu.
    """
    if not books:
        return 0
    by_event = {b.event.id: b for b in books}
    updated = 0

    for pick in db.open_picks():
        book = by_event.get(pick.event_id)
        if not book:
            continue
        exch = book.exchange_book()
        q = exch.get(pick.outcome)
        if not q:
            continue
        price = q.back if pick.side == "back" else q.lay
        if not price:
            continue
        pick.closing_odds = price
        pick.closing_at = utcnow()
        db.save_pick(pick)
        updated += 1

    return updated


@dataclass
class ClvStats:
    n: int = 0
    n_with_closing: int = 0
    mean_clv: float = 0.0
    beat_rate: float = 0.0
    mean_odds: float = 0.0

    @property
    def verdict(self) -> str:
        """Tradução honesta do número, incluindo quando ele não diz nada."""
        if self.n_with_closing < 20:
            return (f"Amostra pequena demais ({self.n_with_closing} palpites "
                    f"com fechamento). Precisa de ~30 para começar a dizer algo.")
        if self.mean_clv > 2 and self.beat_rate > 55:
            return "CLV consistente. É a assinatura de método que funciona."
        if self.mean_clv > 0:
            return "CLV levemente positivo. Vantagem fina — não afrouxe mais o filtro."
        return ("CLV negativo: você está pegando preço pior que o fechamento. "
                "O método precisa de filtro mais apertado, não de mais volume.")


def stats(picks: list[Pick] | None = None) -> ClvStats:
    picks = picks if picks is not None else db.all_picks()
    if not picks:
        return ClvStats()

    clvs = [p.clv_pct for p in picks if p.clv_pct is not None]
    st = ClvStats(n=len(picks), n_with_closing=len(clvs))
    if clvs:
        st.mean_clv = round(sum(clvs) / len(clvs), 3)
        st.beat_rate = round(sum(c > 0 for c in clvs) / len(clvs) * 100, 1)
    st.mean_odds = round(sum(p.taken_odds for p in picks) / len(picks), 3)
    return st


def breakdown(picks: list[Pick] | None = None) -> dict[str, dict]:
    """CLV por liga — mostra onde o método funciona e onde não funciona."""
    picks = picks if picks is not None else db.all_picks()
    groups: dict[str, list[Pick]] = {}
    for p in picks:
        groups.setdefault(p.league or "—", []).append(p)
    out = {}
    for k, v in sorted(groups.items()):
        s = stats(v)
        out[k] = {"n": s.n, "clv": s.mean_clv, "bateu": s.beat_rate}
    return out
