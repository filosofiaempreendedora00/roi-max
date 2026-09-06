from __future__ import annotations

from typing import Protocol

from ..models import MarketBook


class OddsProvider(Protocol):
    name: str

    async def fetch(self, sport_key: str, **kwargs) -> list[MarketBook]:
        ...
