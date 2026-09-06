"""football-data.co.uk — a base histórica gratuita.

Duas famílias de arquivo:

  * "main"  https://www.football-data.co.uk/mmz4281/{temporada}/{div}.csv
            Ligas da Europa ocidental, com estatísticas de jogo E — o que
            importa aqui — as colunas BFEH/BFED/BFEA (odds de abertura na
            Betfair Exchange) e BFECH/BFECD/BFECA (odds de fechamento).

  * "extra" https://www.football-data.co.uk/new/{PAIS}.csv
            Inclui BRA.csv (Brasileirão). Sem colunas de Exchange, só
            média e máxima do mercado — ainda serve para consenso.

É de graça, cobre desde os anos 90 e não pede chave nenhuma.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from ..config import settings

log = logging.getLogger(__name__)

# O site vinha devolvendo 503 em HTTPS enquanto o HTTP puro respondia, então
# há um plano B. São CSVs públicos de resultados, sem credencial nenhuma.
MAIN_URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
EXTRA_URL = "https://www.football-data.co.uk/new/{code}.csv"
MAIN_URL_FALLBACK = "http://football-data.co.uk/mmz4281/{season}/{div}.csv"
EXTRA_URL_FALLBACK = "http://football-data.co.uk/new/{code}.csv"

MAIN_DIVS = {
    "E0": "Premier League", "E1": "Championship", "E2": "League One",
    "SP1": "La Liga", "SP2": "La Liga 2", "I1": "Serie A", "I2": "Serie B",
    "D1": "Bundesliga", "D2": "Bundesliga 2", "F1": "Ligue 1", "F2": "Ligue 2",
    "N1": "Eredivisie", "P1": "Primeira Liga", "B1": "Jupiler", "T1": "Super Lig",
    "SC0": "Scottish Premiership", "G1": "Super League Grécia",
}
EXTRA_CODES = {
    "BRA": "Brasileirão Série A", "ARG": "Primera División", "MEX": "Liga MX",
    "USA": "MLS", "JPN": "J1 League", "CHN": "Super League", "NOR": "Eliteserien",
    "SWE": "Allsvenskan", "DNK": "Superliga", "FIN": "Veikkausliiga",
    "IRL": "Premier Division", "POL": "Ekstraklasa", "RUS": "Premier Liga",
    "AUT": "Bundesliga Áustria", "SWZ": "Super League Suíça", "ROU": "Liga I",
}

# prefixo da coluna -> nome da casa. Abertura e fechamento tratados à parte.
BOOK_COLS = {
    "B365": "bet365", "BW": "betwin", "IW": "interwetten", "PS": "pinnacle",
    "P": "pinnacle", "WH": "williamhill", "VC": "betvictor", "BF": "betfair_sb",
    "Max": "market_max", "Avg": "market_avg",
}
EXCHANGE_PREFIX = "BFE"   # abertura na Exchange
EXCHANGE_CLOSE = "BFEC"   # fechamento na Exchange

# O histórico gratuito traz preço de Exchange em três mercados, não só no 1X2.
# As colunas são (abertura, fechamento):
OU_COLS = {"betfair_ex": ("BFE>2.5", "BFE<2.5", "BFEC>2.5", "BFEC<2.5"),
           "pinnacle": ("P>2.5", "P<2.5", "PC>2.5", "PC<2.5"),
           "bet365": ("B365>2.5", "B365<2.5", "B365C>2.5", "B365C<2.5"),
           "market_max": ("Max>2.5", "Max<2.5", "MaxC>2.5", "MaxC<2.5"),
           "market_avg": ("Avg>2.5", "Avg<2.5", "AvgC>2.5", "AvgC<2.5")}
AH_COLS = {"betfair_ex": ("BFEAHH", "BFEAHA", "BFECAHH", "BFECAHA"),
           "pinnacle": ("PAHH", "PAHA", "PCAHH", "PCAHA"),
           "bet365": ("B365AHH", "B365AHA", "B365CAHH", "B365CAHA"),
           "market_max": ("MaxAHH", "MaxAHA", "MaxCAHH", "MaxCAHA"),
           "market_avg": ("AvgAHH", "AvgAHA", "AvgCAHH", "AvgCAHA")}


@dataclass
class HistoricalMatch:
    """Uma partida do passado com odds e resultado — a unidade do backtest."""

    date: datetime
    league: str
    home: str
    away: str
    result: str                       # "H", "D" ou "A"
    goals_home: int | None
    goals_away: int | None
    odds_open: dict[str, dict[str, float]]   # casa -> {"H","D","A"}
    odds_close: dict[str, dict[str, float]]
    ou_open: dict[str, dict[str, float]] = field(default_factory=dict)   # {"O","U"}
    ou_close: dict[str, dict[str, float]] = field(default_factory=dict)
    ah_line: float | None = None            # linha do handicap asiático
    ah_open: dict[str, dict[str, float]] = field(default_factory=dict)   # {"H","A"}
    ah_close: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.home} x {self.away}"


def _cache_path(name: str) -> Path:
    p = settings.data_dir / "historical"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def download(url: str, cache_name: str, *, refresh: bool = False) -> pd.DataFrame | None:
    """Baixa e guarda em cache. Temporadas encerradas nunca mudam."""
    path = _cache_path(cache_name)
    if path.exists() and not refresh:
        return pd.read_csv(path, encoding="latin-1", on_bad_lines="skip")
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:
        log.warning("Falha ao baixar %s: %s", url, exc)
        if not url.startswith("https://"):
            return None
        alt = url.replace("https://www.", "http://").replace("https://", "http://")
        log.info("tentando de novo em HTTP: %s", alt)
        try:
            r = httpx.get(alt, timeout=60, follow_redirects=True)
            r.raise_for_status()
        except Exception as exc2:
            log.warning("Plano B também falhou: %s", exc2)
            return None
    if b"<html" in r.content[:200].lower():
        log.warning("%s devolveu HTML em vez de CSV", url)
        return None
    path.write_bytes(r.content)
    return pd.read_csv(io.BytesIO(r.content), encoding="latin-1", on_bad_lines="skip")


def _num(row, col) -> float | None:
    if col not in row.index:
        return None
    v = row[col]
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 1.0 else None


def _collect(row, prefixes: dict[str, str], suffix: str = "") -> dict[str, dict[str, float]]:
    """Monta {casa: {H,D,A}} a partir das colunas <prefixo><suffix><H|D|A>."""
    out: dict[str, dict[str, float]] = {}
    for pref, book in prefixes.items():
        trio = {}
        for oc in ("H", "D", "A"):
            v = _num(row, f"{pref}{suffix}{oc}")
            if v:
                trio[oc] = v
        if len(trio) == 3:
            out.setdefault(book, trio)
    return out


def _pair(row, cols: dict[str, tuple[str, str, str, str]], close: bool
          ) -> dict[str, dict[str, float]]:
    """Monta {casa: {chave_a, chave_b}} para um mercado de duas pontas."""
    out: dict[str, dict[str, float]] = {}
    i = 2 if close else 0
    for book, names in cols.items():
        a, b = _num(row, names[i]), _num(row, names[i + 1])
        if a and b:
            out[book] = {"O" if cols is OU_COLS else "H": a,
                         "U" if cols is OU_COLS else "A": b}
    return out


def _parse_date(row) -> datetime | None:
    raw = str(row.get("Date", "")).strip()
    if not raw or raw == "nan":
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    time_raw = str(row.get("Time", "")).strip()
    if time_raw and time_raw != "nan" and ":" in time_raw:
        try:
            hh, mm = time_raw.split(":")[:2]
            d = d.replace(hour=int(hh), minute=int(mm))
        except ValueError:
            pass
    return d.replace(tzinfo=timezone.utc)


def parse_main(df: pd.DataFrame, league: str) -> list[HistoricalMatch]:
    matches: list[HistoricalMatch] = []
    for _, row in df.iterrows():
        date = _parse_date(row)
        home, away = str(row.get("HomeTeam", "")), str(row.get("AwayTeam", ""))
        res = str(row.get("FTR", "")).strip().upper()
        if not date or res not in ("H", "D", "A") or home == "nan":
            continue

        opens = _collect(row, BOOK_COLS)
        exch = _collect(row, {EXCHANGE_PREFIX: "betfair_ex"})
        opens.update(exch)

        closes = _collect(row, BOOK_COLS, suffix="C")
        exch_c = _collect(row, {EXCHANGE_CLOSE: "betfair_ex"})
        closes.update(exch_c)

        matches.append(HistoricalMatch(
            date=date, league=league, home=home, away=away, result=res,
            goals_home=_int(row.get("FTHG")), goals_away=_int(row.get("FTAG")),
            odds_open=opens, odds_close=closes,
            ou_open=_pair(row, OU_COLS, close=False),
            ou_close=_pair(row, OU_COLS, close=True),
            ah_line=_float_any(row.get("AHh")),
            ah_open=_pair(row, AH_COLS, close=False),
            ah_close=_pair(row, AH_COLS, close=True),
        ))
    return matches


def _float_any(v) -> float | None:
    """Como `_num`, mas aceita valores <= 1 (a linha do handicap pode ser 0,25)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_extra(df: pd.DataFrame, league: str) -> list[HistoricalMatch]:
    matches: list[HistoricalMatch] = []
    for _, row in df.iterrows():
        date = _parse_date(row)
        home, away = str(row.get("Home", "")), str(row.get("Away", ""))
        res = str(row.get("Res", "")).strip().upper()
        if not date or res not in ("H", "D", "A") or home == "nan":
            continue
        opens = _collect(row, {"P": "pinnacle", "Max": "market_max", "Avg": "market_avg"})
        closes = _collect(row, {"PC": "pinnacle", "MaxC": "market_max", "AvgC": "market_avg"})
        matches.append(HistoricalMatch(
            date=date, league=str(row.get("League", league)), home=home, away=away,
            result=res, goals_home=_int(row.get("HG")), goals_away=_int(row.get("AG")),
            odds_open=opens, odds_close=closes,
        ))
    return matches


def _int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load_main(div: str, seasons: list[str], *, refresh: bool = False) -> list[HistoricalMatch]:
    """`seasons` no formato do site: ['2425', '2526']."""
    out: list[HistoricalMatch] = []
    for season in seasons:
        df = download(MAIN_URL.format(season=season, div=div), f"{div}_{season}.csv",
                      refresh=refresh)
        if df is None or df.empty:
            continue
        out.extend(parse_main(df, MAIN_DIVS.get(div, div)))
    out.sort(key=lambda m: m.date)
    return out


def load_extra(code: str, *, refresh: bool = False) -> list[HistoricalMatch]:
    df = download(EXTRA_URL.format(code=code), f"extra_{code}.csv", refresh=refresh)
    if df is None or df.empty:
        return []
    out = parse_extra(df, EXTRA_CODES.get(code, code))
    out.sort(key=lambda m: m.date)
    return out
