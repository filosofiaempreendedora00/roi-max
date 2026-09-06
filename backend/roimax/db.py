"""Persistência em SQLite.

SQLite porque o app é single-tenant (você), roda em um processo só e precisa
de custo zero. O acesso está isolado aqui: trocar por Postgres/TimescaleDB
depois é reescrever este arquivo, não o resto.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import settings
from .models import CreditUsage, DailyCard, Event, Pick, PushSubscription, Quote, Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    sport_key       TEXT NOT NULL,
    league          TEXT,
    home            TEXT NOT NULL,
    away            TEXT NOT NULL,
    commence_time   TEXT NOT NULL,
    betfair_market_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(commence_time);

-- histórico de ticks: é o que permite detectar steam e refazer backtest
CREATE TABLE IF NOT EXISTS quotes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL,
    bookmaker   TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    back        REAL,
    lay         REAL,
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_event_ts ON quotes(event_id, ts);
CREATE INDEX IF NOT EXISTS idx_quotes_lookup   ON quotes(event_id, bookmaker, outcome, ts);

CREATE TABLE IF NOT EXISTS signals (
    id          TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    ts          TEXT NOT NULL,
    acted       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts DESC);

CREATE TABLE IF NOT EXISTS credit_usage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    credits     INTEGER NOT NULL,
    remaining   INTEGER,
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_credit_ts ON credit_usage(provider, ts);

CREATE TABLE IF NOT EXISTS push_subs (
    endpoint    TEXT PRIMARY KEY,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    label       TEXT,
    ts          TEXT NOT NULL
);

-- palpites: o registro permanente, com preço de fechamento para medir CLV
CREATE TABLE IF NOT EXISTS picks (
    id              TEXT PRIMARY KEY,
    payload         TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    side            TEXT NOT NULL,
    commence_time   TEXT NOT NULL,
    settled         INTEGER NOT NULL DEFAULT 0,
    taken_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_picks_open ON picks(settled, commence_time);
CREATE UNIQUE INDEX IF NOT EXISTS idx_picks_unique ON picks(event_id, outcome, side);

CREATE TABLE IF NOT EXISTS cards (
    date        TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    ts          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


_conn: sqlite3.Connection | None = None


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------- events

def upsert_event(ev: Event) -> None:
    with tx() as c:
        c.execute(
            """INSERT INTO events (id, sport_key, league, home, away, commence_time, betfair_market_id)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 league=excluded.league,
                 commence_time=excluded.commence_time,
                 betfair_market_id=COALESCE(excluded.betfair_market_id, events.betfair_market_id)""",
            (ev.id, ev.sport_key, ev.league, ev.home, ev.away,
             _iso(ev.commence_time), ev.betfair_market_id),
        )


def get_event(event_id: str) -> Event | None:
    row = connect().execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    return _row_to_event(row) if row else None


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"], sport_key=row["sport_key"], league=row["league"] or "",
        home=row["home"], away=row["away"],
        commence_time=_parse(row["commence_time"]),
        betfair_market_id=row["betfair_market_id"],
    )


def upcoming_events(limit: int = 100) -> list[Event]:
    rows = connect().execute(
        "SELECT * FROM events ORDER BY commence_time ASC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_event(r) for r in rows]


# ---------------------------------------------------------------- quotes

def insert_quotes(quotes: list[Quote]) -> None:
    if not quotes:
        return
    with tx() as c:
        c.executemany(
            "INSERT INTO quotes (event_id, bookmaker, outcome, back, lay, ts) VALUES (?,?,?,?,?,?)",
            [(q.event_id, q.bookmaker, q.outcome.value, q.back, q.lay, _iso(q.ts)) for q in quotes],
        )


def quote_history(event_id: str, bookmaker: str, outcome: str, limit: int = 200) -> list[Quote]:
    rows = connect().execute(
        """SELECT * FROM quotes WHERE event_id=? AND bookmaker=? AND outcome=?
           ORDER BY ts DESC LIMIT ?""",
        (event_id, bookmaker, outcome, limit),
    ).fetchall()
    return [
        Quote(event_id=r["event_id"], bookmaker=r["bookmaker"], outcome=r["outcome"],
              back=r["back"], lay=r["lay"], ts=_parse(r["ts"]))
        for r in rows
    ]


# ---------------------------------------------------------------- signals

def insert_signal(sig: Signal) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR REPLACE INTO signals (id, payload, kind, event_id, ts, acted) VALUES (?,?,?,?,?,0)",
            (sig.id, sig.model_dump_json(), sig.kind.value, sig.event_id, _iso(sig.ts)),
        )


def recent_signals(limit: int = 50) -> list[Signal]:
    rows = connect().execute(
        "SELECT payload FROM signals ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [Signal.model_validate_json(r["payload"]) for r in rows]


def mark_acted(signal_id: str) -> None:
    with tx() as c:
        c.execute("UPDATE signals SET acted=1 WHERE id=?", (signal_id,))


# ---------------------------------------------------------------- créditos

def record_credit(usage: CreditUsage) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO credit_usage (provider, endpoint, credits, remaining, ts) VALUES (?,?,?,?,?)",
            (usage.provider, usage.endpoint, usage.credits, usage.remaining, _iso(usage.ts)),
        )


def credits_used_since(provider: str, since: datetime) -> int:
    row = connect().execute(
        "SELECT COALESCE(SUM(credits),0) AS n FROM credit_usage WHERE provider=? AND ts>=?",
        (provider, _iso(since)),
    ).fetchone()
    return int(row["n"])


# ---------------------------------------------------------------- push

def save_subscription(sub: PushSubscription) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR REPLACE INTO push_subs (endpoint, p256dh, auth, label, ts) VALUES (?,?,?,?,?)",
            (sub.endpoint, sub.p256dh, sub.auth, sub.label, _iso(datetime.now(timezone.utc))),
        )


def all_subscriptions() -> list[PushSubscription]:
    rows = connect().execute("SELECT * FROM push_subs").fetchall()
    return [PushSubscription(endpoint=r["endpoint"], p256dh=r["p256dh"],
                             auth=r["auth"], label=r["label"] or "") for r in rows]


def delete_subscription(endpoint: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))


# ---------------------------------------------------------------- kv

def kv_get(key: str, default: Any = None) -> Any:
    row = connect().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(key: str, value: Any) -> None:
    with tx() as c:
        c.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, json.dumps(value)))


# ---------------------------------------------------------------- palpites

def save_pick(pick: Pick) -> None:
    """Grava ou atualiza. O índice único evita palpite duplicado no mesmo lance."""
    with tx() as c:
        c.execute(
            """INSERT INTO picks (id, payload, event_id, outcome, side,
                                  commence_time, settled, taken_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(event_id, outcome, side) DO UPDATE SET
                 payload=excluded.payload, settled=excluded.settled""",
            (pick.id, pick.model_dump_json(), pick.event_id, pick.outcome.value,
             pick.side, _iso(pick.commence_time),
             1 if pick.result else 0, _iso(pick.taken_at)),
        )


def open_picks() -> list[Pick]:
    """Palpites de jogos que ainda não começaram — os que ainda podem ter o
    preço de fechamento atualizado."""
    rows = connect().execute(
        "SELECT payload FROM picks WHERE settled=0 AND commence_time > ? ORDER BY commence_time",
        (_iso(datetime.now(timezone.utc)),),
    ).fetchall()
    return [Pick.model_validate_json(r["payload"]) for r in rows]


def all_picks(limit: int = 500) -> list[Pick]:
    rows = connect().execute(
        "SELECT payload FROM picks ORDER BY taken_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [Pick.model_validate_json(r["payload"]) for r in rows]


def find_pick(event_id: str, outcome: str, side: str) -> Pick | None:
    row = connect().execute(
        "SELECT payload FROM picks WHERE event_id=? AND outcome=? AND side=?",
        (event_id, outcome, side),
    ).fetchone()
    return Pick.model_validate_json(row["payload"]) if row else None


# ----------------------------------------------------------------- cartas

def save_card(card: DailyCard) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR REPLACE INTO cards (date, payload, ts) VALUES (?,?,?)",
            (card.date, card.model_dump_json(), _iso(card.generated_at)),
        )


def get_card(date: str) -> DailyCard | None:
    row = connect().execute("SELECT payload FROM cards WHERE date=?", (date,)).fetchone()
    return DailyCard.model_validate_json(row["payload"]) if row else None


def latest_card() -> DailyCard | None:
    row = connect().execute("SELECT payload FROM cards ORDER BY date DESC LIMIT 1").fetchone()
    return DailyCard.model_validate_json(row["payload"]) if row else None
