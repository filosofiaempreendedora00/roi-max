"""Backtest sobre dados históricos gratuitos.

Isto vem ANTES do app na ordem de importância. Um sinal só merece um push no
seu celular se sobreviveu aqui.

Duas métricas importam, nesta ordem:

  1. CLV (closing line value) — a aposta pegou preço melhor que o fechamento?
     É o melhor preditor conhecido de lucro no longo prazo, porque o preço de
     fechamento é a estimativa mais eficiente que o mercado produz. Bater o
     fechamento com consistência é edge; ROI positivo em amostra pequena é sorte.

  2. ROI — o dinheiro de fato.

O backtest usa o preço de ABERTURA da Betfair Exchange (BFEH/BFED/BFEA) como
preço de entrada e o de FECHAMENTO (BFEC*) como referência de CLV.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from ..engine.detectors import Context, build_consensus, run_all
from ..engine.math import to_prob
from ..models import Event, MarketBook, Outcome, Quote, Signal, SignalKind
from ..providers.footballdata_uk import HistoricalMatch

RESULT_TO_OUTCOME = {"H": Outcome.HOME, "D": Outcome.DRAW, "A": Outcome.AWAY}
OUTCOME_TO_KEY = {Outcome.HOME: "H", Outcome.DRAW: "D", Outcome.AWAY: "A"}


@dataclass
class Bet:
    date: str
    league: str
    match: str
    kind: str
    side: str
    outcome: str
    odds: float
    fair_odds: float
    edge_pct: float
    stake: float
    pnl: float
    won: bool
    close_odds: float | None = None
    clv_pct: float | None = None


@dataclass
class BacktestResult:
    bets: list[Bet] = field(default_factory=list)
    matches_scanned: int = 0
    commission: float = 0.065

    # ---------------- métricas ----------------
    @property
    def n(self) -> int:
        return len(self.bets)

    @property
    def staked(self) -> float:
        return sum(b.stake for b in self.bets)

    @property
    def pnl(self) -> float:
        return sum(b.pnl for b in self.bets)

    @property
    def roi_pct(self) -> float:
        return (self.pnl / self.staked * 100.0) if self.staked else 0.0

    @property
    def hit_rate_pct(self) -> float:
        return (sum(b.won for b in self.bets) / self.n * 100.0) if self.n else 0.0

    @property
    def avg_odds(self) -> float:
        return (sum(b.odds for b in self.bets) / self.n) if self.n else 0.0

    @property
    def clv_pct(self) -> float:
        """CLV médio. Positivo = entrou a preço melhor que o fechamento."""
        vals = [b.clv_pct for b in self.bets if b.clv_pct is not None]
        return (sum(vals) / len(vals)) if vals else 0.0

    @property
    def clv_beat_rate_pct(self) -> float:
        vals = [b.clv_pct for b in self.bets if b.clv_pct is not None]
        return (sum(v > 0 for v in vals) / len(vals) * 100.0) if vals else 0.0

    @property
    def max_drawdown(self) -> float:
        peak = equity = 0.0
        dd = 0.0
        for b in self.bets:
            equity += b.pnl
            peak = max(peak, equity)
            dd = min(dd, equity - peak)
        return dd

    @property
    def equity_curve(self) -> list[float]:
        out, eq = [], 0.0
        for b in self.bets:
            eq += b.pnl
            out.append(round(eq, 4))
        return out

    def by(self, attr: str) -> dict[str, dict]:
        groups: dict[str, list[Bet]] = {}
        for b in self.bets:
            groups.setdefault(getattr(b, attr), []).append(b)
        return {
            k: {
                "n": len(v),
                "pnl": round(sum(x.pnl for x in v), 3),
                "roi_pct": round(sum(x.pnl for x in v) / sum(x.stake for x in v) * 100, 2)
                if sum(x.stake for x in v) else 0.0,
            }
            for k, v in sorted(groups.items())
        }

    def summary(self) -> dict:
        return {
            "partidas_analisadas": self.matches_scanned,
            "apostas": self.n,
            "taxa_de_selecao_pct": round(self.n / self.matches_scanned * 100, 2)
            if self.matches_scanned else 0.0,
            "unidades_arriscadas": round(self.staked, 2),
            "lucro_unidades": round(self.pnl, 3),
            "roi_pct": round(self.roi_pct, 2),
            "acerto_pct": round(self.hit_rate_pct, 2),
            "odd_media": round(self.avg_odds, 3),
            "clv_medio_pct": round(self.clv_pct, 3),
            "clv_positivo_pct": round(self.clv_beat_rate_pct, 2),
            "drawdown_max_unidades": round(self.max_drawdown, 3),
            "comissao_aplicada": self.commission,
            "por_tipo": self.by("kind"),
            "por_liga": self.by("league"),
        }


# --------------------------------------------------------------------------


def _book_from_match(m: HistoricalMatch, *, lay_spread: float,
                     use_close: bool = False) -> MarketBook | None:
    """Reconstrói o mercado 1X2 como ele estava, para alimentar os detectores."""
    source = m.odds_close if use_close else m.odds_open
    if "betfair_ex" not in source:
        return None

    event = Event(
        id=f"{m.date:%Y%m%d}-{m.home}-{m.away}".replace(" ", "_"),
        league=m.league, home=m.home, away=m.away, commence_time=m.date,
    )
    quotes: list[Quote] = []
    for book, trio in source.items():
        for key, oc in (("H", Outcome.HOME), ("D", Outcome.DRAW), ("A", Outcome.AWAY)):
            price = trio.get(key)
            if not price:
                continue
            if book == "betfair_ex":
                # O CSV traz só o back. O lay é sintetizado com um spread fixo;
                # com lay_spread=0 os sinais de LAY simplesmente não disparam,
                # que é o padrão — melhor não medir do que medir em cima de
                # um preço que nunca existiu.
                lay = round(price * (1 + lay_spread), 3) if lay_spread > 0 else None
                quotes.append(Quote(event_id=event.id, bookmaker="betfair_ex",
                                    outcome=oc, back=price, lay=lay, ts=m.date))
            else:
                quotes.append(Quote(event_id=event.id, bookmaker=book,
                                    outcome=oc, back=price, ts=m.date))
    return MarketBook(event=event, quotes=quotes, ts=m.date)


def _settle(sig: Signal, result: str, stake: float, commission: float) -> tuple[float, bool]:
    """P&L de uma aposta liquidada. Retorna (lucro_em_unidades, ganhou)."""
    hit = OUTCOME_TO_KEY[sig.outcome] == result
    if sig.side == "back":
        if hit:
            return (sig.market_odds - 1.0) * stake * (1 - commission), True
        return -stake, False
    # lay: `stake` é o stake do backer; a liability é (odds-1)*stake
    if hit:
        return -(sig.market_odds - 1.0) * stake, False
    return stake * (1 - commission), True


def run_backtest(
    matches: list[HistoricalMatch],
    *,
    ctx: Context | None = None,
    stake_mode: str = "flat",     # "flat" | "kelly"
    kelly_fraction: float = 0.25,
    bankroll: float = 100.0,
    lay_spread: float = 0.0,
    kinds: tuple[SignalKind, ...] = (SignalKind.VALUE_BACK, SignalKind.VALUE_LAY),
) -> BacktestResult:
    ctx = ctx or Context()
    res = BacktestResult(commission=ctx.commission)

    for m in matches:
        res.matches_scanned += 1
        book = _book_from_match(m, lay_spread=lay_spread)
        if book is None:
            continue

        # STEAM não faz sentido sem série temporal; ARBITRAGE precisa de
        # execução simultânea em várias casas. Ambos ficam de fora aqui.
        for sig in run_all(book, ctx):
            if sig.kind not in kinds:
                continue

            if stake_mode == "kelly":
                stake = max(0.0, bankroll * sig.kelly * kelly_fraction)
                if stake <= 0:
                    continue
            else:
                stake = 1.0

            pnl, won = _settle(sig, m.result, stake, ctx.commission)

            close = m.odds_close.get("betfair_ex", {}).get(OUTCOME_TO_KEY[sig.outcome])
            clv = None
            if close:
                # back: quero ter pego odd MAIOR que o fechamento.
                # lay: quero ter pego odd MENOR que o fechamento.
                clv = ((sig.market_odds / close - 1.0) if sig.side == "back"
                       else (close / sig.market_odds - 1.0)) * 100.0

            res.bets.append(Bet(
                date=f"{m.date:%Y-%m-%d}", league=m.league, match=m.label,
                kind=sig.kind.value, side=sig.side,
                outcome=sig.outcome.value, odds=sig.market_odds,
                fair_odds=sig.fair_odds, edge_pct=sig.edge_pct,
                stake=round(stake, 4), pnl=round(pnl, 4), won=won,
                close_odds=close, clv_pct=round(clv, 3) if clv is not None else None,
            ))

    return res


def baseline_closing_line(matches: list[HistoricalMatch]) -> dict:
    """Controle: quanto se perde apostando no favorito ao preço de abertura.

    Serve para você ter com o que comparar. Qualquer estratégia precisa bater
    isto com folga antes de merecer dinheiro real.
    """
    pnl = n = 0.0
    for m in matches:
        odds = m.odds_open.get("betfair_ex") or m.odds_open.get("market_avg")
        if not odds or len(odds) < 3:
            continue
        fav = min(odds, key=lambda k: odds[k])
        n += 1
        pnl += (odds[fav] - 1) * 0.935 if fav == m.result else -1
    return {"apostas": int(n), "lucro_unidades": round(pnl, 2),
            "roi_pct": round(pnl / n * 100, 2) if n else 0.0}
