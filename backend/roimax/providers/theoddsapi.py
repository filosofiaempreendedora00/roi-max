"""Adaptador para The Odds API.

É o caminho que sobra para ver preço de Betfair Exchange sem app key:
os bookmakers `betfair_ex_uk/eu/au` expõem back (mercado `h2h`) e lay
(mercado `h2h_lay`) no mesmo payload.

Custo: 1 crédito por mercado por região. Pedir h2h + h2h_lay = 2 créditos.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from ..budget import odds_api_budget
from ..config import settings
from ..models import Event, MarketBook, Outcome, Quote, utcnow

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4"
BETFAIR_KEYS = ["betfair_ex_uk", "betfair_ex_eu", "betfair_ex_au"]

# Casas tradicionais usadas para formar o consenso. Quanto mais, melhor a
# estimativa do preço justo — e o custo em créditos não muda.
SOFT_BOOKS = [
    "pinnacle", "williamhill", "bet365", "unibet_eu", "marathonbet",
    "onexbet", "betclic", "nordicbet", "betsson", "coolbet", "everygame",
    "matchbook", "smarkets", "betfair_sb_uk", "tipico_de", "betvictor",
    "ladbrokes_uk", "coral", "paddypower", "skybet", "boylesports",
]

DEFAULT_SPORTS = [
    "soccer_brazil_campeonato",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
]


class TheOddsAPI:
    name = "the-odds-api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.odds_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def fetch_odds(
        self,
        sport_key: str,
        *,
        markets: tuple[str, ...] = ("h2h", "h2h_lay"),
        urgent: bool = False,
    ) -> list[MarketBook]:
        """Uma chamada -> todas as partidas do campeonato, com todas as casas."""
        if not self.enabled:
            raise RuntimeError("ODDS_API_KEY não configurada")

        cost = len(markets)  # bookmakers= conta como 1 região
        if not odds_api_budget.can_spend(cost, urgent=urgent):
            st = odds_api_budget.status()
            log.warning(
                "Chamada bloqueada pelo orçamento: %d créditos restantes (reserva %d)",
                st.remaining, st.reserve,
            )
            return []

        params = {
            "apiKey": self.api_key,
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
            "dateFormat": "iso",
            "bookmakers": ",".join(BETFAIR_KEYS + SOFT_BOOKS),
        }
        url = f"{BASE}/sports/{sport_key}/odds"

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params)

        remaining = r.headers.get("x-requests-remaining")
        odds_api_budget.record(
            f"odds/{sport_key}", cost,
            int(remaining) if remaining and remaining.isdigit() else None,
        )
        if r.status_code != 200:
            log.error("The Odds API %s: %s", r.status_code, r.text[:300])
            return []

        return [b for b in (self._parse_event(e, sport_key) for e in r.json()) if b]

    # ------------------------------------------------------------------

    def _parse_event(self, raw: dict, sport_key: str) -> MarketBook | None:
        try:
            home, away = raw["home_team"], raw["away_team"]
            event = Event(
                id=raw["id"],
                sport_key=sport_key,
                league=raw.get("sport_title", ""),
                home=home,
                away=away,
                commence_time=datetime.fromisoformat(
                    raw["commence_time"].replace("Z", "+00:00")
                ),
            )
        except (KeyError, ValueError):
            return None

        # (bookmaker, outcome) -> {"back": x, "lay": y}
        acc: dict[tuple[str, Outcome], dict[str, float]] = {}
        for bm in raw.get("bookmakers", []):
            bname = bm.get("key", "")
            for mk in bm.get("markets", []):
                mkey = mk.get("key")
                if mkey not in ("h2h", "h2h_lay"):
                    continue
                side = "back" if mkey == "h2h" else "lay"
                for oc in mk.get("outcomes", []):
                    outcome = self._map_outcome(oc.get("name", ""), home, away)
                    if outcome is None:
                        continue
                    price = oc.get("price")
                    if not price or price <= 1.0:
                        continue
                    acc.setdefault((bname, outcome), {})[side] = float(price)

        quotes = [
            Quote(event_id=event.id, bookmaker=bk, outcome=oc,
                  back=v.get("back"), lay=v.get("lay"), ts=utcnow())
            for (bk, oc), v in acc.items()
        ]
        if not quotes:
            return None
        return MarketBook(event=event, quotes=quotes)

    @staticmethod
    def _map_outcome(name: str, home: str, away: str) -> Outcome | None:
        n = name.strip().lower()
        if n in ("draw", "tie", "empate"):
            return Outcome.DRAW
        if n == home.strip().lower():
            return Outcome.HOME
        if n == away.strip().lower():
            return Outcome.AWAY
        return None

    async def list_sports(self) -> list[dict]:
        """Grátis: não consome crédito."""
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{BASE}/sports", params={"apiKey": self.api_key})
        if r.status_code != 200:
            return []
        return [s for s in r.json() if s.get("key", "").startswith("soccer")]
