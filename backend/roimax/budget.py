"""Gestor de créditos.

No free tier são 500 créditos/mês (~16 por dia). Gastar isso em polling burro
é queimar a cota em três dias. Este módulo decide se uma chamada vale a pena:
prioriza a janela em que você opera e os jogos da sua watchlist, e sempre
guarda uma reserva para o fim do mês.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import db
from .config import settings
from .models import CreditUsage


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass
class BudgetStatus:
    provider: str
    monthly: int
    used: int
    remaining: int
    days_left: int
    daily_allowance: int
    reserve: int

    @property
    def pct_used(self) -> float:
        return (self.used / self.monthly * 100.0) if self.monthly else 0.0


class CreditBudget:
    """Orçamento mensal de chamadas para um provedor."""

    def __init__(self, provider: str, monthly: int, reserve_pct: float = 0.10):
        self.provider = provider
        self.monthly = monthly
        self.reserve_pct = reserve_pct

    def status(self, now: datetime | None = None) -> BudgetStatus:
        now = now or datetime.now(timezone.utc)
        used = db.credits_used_since(self.provider, _month_start(now))
        remaining = max(0, self.monthly - used)
        nxt = (_month_start(now) + timedelta(days=32)).replace(day=1)
        days_left = max(1, (nxt - now).days)
        reserve = int(self.monthly * self.reserve_pct)
        spendable = max(0, remaining - reserve)
        return BudgetStatus(
            provider=self.provider, monthly=self.monthly, used=used,
            remaining=remaining, days_left=days_left,
            daily_allowance=max(1, spendable // days_left), reserve=reserve,
        )

    def can_spend(self, credits: int, *, urgent: bool = False) -> bool:
        """`urgent=True` autoriza invadir a reserva (ex.: jogo já rolando)."""
        st = self.status()
        if urgent:
            return st.remaining >= credits
        return (st.remaining - st.reserve) >= credits

    def record(self, endpoint: str, credits: int, remaining: int | None = None) -> None:
        db.record_credit(CreditUsage(
            provider=self.provider, endpoint=endpoint,
            credits=credits, remaining=remaining,
        ))


odds_api_budget = CreditBudget("the-odds-api", settings.odds_api_monthly_credits)
