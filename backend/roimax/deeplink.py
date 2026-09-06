"""Links de 1 toque para o mercado exato na Betfair.

Como a conta brasileira não tem API, a execução é manual — então o único
ganho de tempo possível é eliminar a navegação. O sinal já chega com o link
que abre o mercado certo, no app se estiver instalado, no site se não.
"""
from __future__ import annotations

from urllib.parse import quote_plus

from .config import settings
from .models import Event, Outcome


def market_url(event: Event) -> str:
    """URL do mercado. Usa o market id da Betfair quando conhecido."""
    domain = settings.betfair_domain
    if event.betfair_market_id:
        return f"https://{domain}/exchange/plus/football/market/{event.betfair_market_id}"
    # sem market id, cai na busca — ainda economiza cliques
    return f"https://{domain}/exchange/plus/search?query={quote_plus(event.label)}"


def outcome_label(event: Event, outcome: Outcome) -> str:
    return {
        Outcome.HOME: event.home,
        Outcome.DRAW: "Empate",
        Outcome.AWAY: event.away,
    }[outcome]
