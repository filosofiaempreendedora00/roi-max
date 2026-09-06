"""Modelos de domínio. Puros, sem dependência de banco ou de provedor."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


Side = Literal["back", "lay"]


class Outcome(str, Enum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


class Event(BaseModel):
    """Uma partida."""

    id: str
    sport_key: str = "soccer"
    league: str = ""
    home: str
    away: str
    commence_time: datetime
    betfair_market_id: str | None = None

    @property
    def label(self) -> str:
        return f"{self.home} x {self.away}"

    @property
    def is_live(self) -> bool:
        return self.commence_time <= utcnow()


class Quote(BaseModel):
    """Um preço observado, de uma casa, para um resultado.

    Numa exchange existem dois preços por resultado: `back` (o que você recebe
    apostando a favor) e `lay` (o que você paga apostando contra).
    """

    event_id: str
    bookmaker: str
    outcome: Outcome
    back: float | None = None
    lay: float | None = None
    ts: datetime = Field(default_factory=utcnow)

    @property
    def is_exchange(self) -> bool:
        return self.back is not None and self.lay is not None


class MarketBook(BaseModel):
    """Fotografia do mercado 1X2 de uma partida, em um instante."""

    event: Event
    quotes: list[Quote] = Field(default_factory=list)
    ts: datetime = Field(default_factory=utcnow)

    def by_bookmaker(self, name: str) -> dict[Outcome, Quote]:
        return {q.outcome: q for q in self.quotes if q.bookmaker == name}

    @property
    def bookmakers(self) -> list[str]:
        seen: list[str] = []
        for q in self.quotes:
            if q.bookmaker not in seen:
                seen.append(q.bookmaker)
        return seen

    def exchange_book(self) -> dict[Outcome, Quote]:
        """O book da Betfair Exchange.

        Casa o prefixo `betfair_ex` e não apenas `betfair`, senão a sportsbook
        da Betfair (`betfair_sb_*`) seria confundida com a exchange.

        Basta ter preço de back: no histórico só existe o back, e exigir os
        dois lados aqui zeraria o backtest inteiro.
        """
        for bk in self.bookmakers:
            if not bk.startswith("betfair_ex"):
                continue
            book = self.by_bookmaker(bk)
            if any(q.back for q in book.values()):
                return book
        return {}


class SignalKind(str, Enum):
    VALUE_BACK = "VALUE_BACK"      # exchange paga acima do justo
    VALUE_LAY = "VALUE_LAY"        # exchange cobra abaixo do justo
    ARBITRAGE = "ARBITRAGE"        # soma das probabilidades < 1
    STEAM = "STEAM"                # movimento brusco de preço
    WIDE_SPREAD = "WIDE_SPREAD"    # book fino, oportunidade de market making


class Signal(BaseModel):
    """Um sinal acionável. É isto que chega no seu celular."""

    id: str
    kind: SignalKind
    event_id: str
    event_label: str
    league: str = ""
    outcome: Outcome
    side: Side
    market_odds: float
    fair_odds: float
    edge_pct: float
    ev: float                       # valor esperado por unidade arriscada
    kelly: float                    # fração de Kelly (banca cheia)
    confidence: float = 0.0         # 0..1, quanto o consenso é confiável
    bookmaker: str = ""
    reference: str = ""             # de onde veio o preço justo
    deeplink: str = ""
    ts: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    notes: str = ""

    @property
    def is_live(self) -> bool:
        return self.expires_at is None or self.expires_at > utcnow()


class Pick(BaseModel):
    """Uma entrada que você de fato fez (ou pretende fazer).

    Existe separado de `Signal` porque o sinal é efêmero e o palpite é o
    registro permanente: é ele que carrega o preço de fechamento e permite
    medir o CLV real, que é a única forma de saber se o método funciona antes
    de acumular milhares de apostas.
    """

    id: str
    signal_id: str
    event_id: str
    event_label: str
    league: str = ""
    market: str = "1X2"
    outcome: Outcome
    side: Side
    taken_odds: float
    fair_odds: float
    ev: float
    stake: float = 0.0
    commence_time: datetime
    taken_at: datetime = Field(default_factory=utcnow)

    # preenchido pela última varredura antes do apito inicial
    closing_odds: float | None = None
    closing_at: datetime | None = None

    result: str | None = None      # "WON" | "LOST" | None
    pnl: float | None = None
    placed: bool = False           # você confirmou na Betfair?

    @property
    def clv_pct(self) -> float | None:
        """Quanto o preço tomado foi melhor que o de fechamento."""
        if not self.closing_odds or self.closing_odds <= 1.0:
            return None
        if self.side == "back":
            return (self.taken_odds / self.closing_odds - 1.0) * 100.0
        return (self.closing_odds / self.taken_odds - 1.0) * 100.0

    @property
    def kicked_off(self) -> bool:
        return self.commence_time <= utcnow()


class CardEntry(BaseModel):
    """Uma linha da carta do dia, já mastigada."""

    signal: "Signal"
    stake: float
    limit_price: float             # back: preço mínimo. lay: preço máximo.
    rank: int
    reason: str


class DailyCard(BaseModel):
    """O que você abre uma vez por dia e executa."""

    date: str
    generated_at: datetime = Field(default_factory=utcnow)
    entries: list[CardEntry] = Field(default_factory=list)
    scanned_events: int = 0
    bankroll: float = 0.0
    total_stake: float = 0.0
    note: str = ""


class CreditUsage(BaseModel):
    provider: str
    endpoint: str
    credits: int
    remaining: int | None = None
    ts: datetime = Field(default_factory=utcnow)


class PushSubscription(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    label: str = ""
