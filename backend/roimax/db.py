"""Persistência.

Roda em SQLite no seu Mac e em Postgres na nuvem, com o mesmo código. Isso
importa porque a Vercel é serverless: não existe disco que sobreviva entre
uma invocação e outra, então o SQLite em arquivo simplesmente some lá.

`DATABASE_URL` define qual dos dois. Sem ela, arquivo local.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Text,
    create_engine, delete, func, insert, select, update,
)
from sqlalchemy.engine import Engine

from .config import settings
from .models import (CreditUsage, DailyCard, Event, Pick, PushSubscription,
                     Quote, Signal)

metadata = MetaData()

events = Table(
    "events", metadata,
    Column("id", String(120), primary_key=True),
    Column("sport_key", String(80), nullable=False),
    Column("league", String(120)),
    Column("home", String(120), nullable=False),
    Column("away", String(120), nullable=False),
    Column("commence_time", DateTime(timezone=True), nullable=False, index=True),
    Column("betfair_market_id", String(40)),
)

# histórico de ticks: alimenta o detector de movimento e o preço de fechamento
quotes = Table(
    "quotes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String(120), nullable=False, index=True),
    Column("bookmaker", String(60), nullable=False),
    Column("outcome", String(10), nullable=False),
    Column("back", Float),
    Column("lay", Float),
    Column("ts", DateTime(timezone=True), nullable=False, index=True),
)

signals = Table(
    "signals", metadata,
    Column("id", String(40), primary_key=True),
    Column("payload", Text, nullable=False),
    Column("kind", String(30), nullable=False),
    Column("event_id", String(120), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False, index=True),
    Column("acted", Boolean, nullable=False, default=False),
)

picks = Table(
    "picks", metadata,
    Column("id", String(40), primary_key=True),
    Column("payload", Text, nullable=False),
    Column("event_id", String(120), nullable=False),
    Column("outcome", String(10), nullable=False),
    Column("side", String(6), nullable=False),
    Column("commence_time", DateTime(timezone=True), nullable=False, index=True),
    Column("settled", Boolean, nullable=False, default=False),
    Column("taken_at", DateTime(timezone=True), nullable=False),
    # um palpite por lance: evita duplicar a mesma entrada
    Column("dedupe", String(160), unique=True, nullable=False),
)

cards = Table(
    "cards", metadata,
    Column("date", String(12), primary_key=True),
    Column("payload", Text, nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
)

credit_usage = Table(
    "credit_usage", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String(40), nullable=False, index=True),
    Column("endpoint", String(120), nullable=False),
    Column("credits", Integer, nullable=False),
    Column("remaining", Integer),
    Column("ts", DateTime(timezone=True), nullable=False, index=True),
)

push_subs = Table(
    "push_subs", metadata,
    Column("endpoint", Text, primary_key=True),
    Column("p256dh", Text, nullable=False),
    Column("auth", Text, nullable=False),
    Column("label", Text),
    Column("ts", DateTime(timezone=True), nullable=False),
)

kv = Table(
    "kv", metadata,
    Column("key", String(80), primary_key=True),
    Column("value", Text, nullable=False),
)

_engine: Engine | None = None


def _url() -> str:
    if settings.database_url:
        # a Neon entrega "postgres://"; o SQLAlchemy quer "postgresql+psycopg://"
        u = settings.database_url
        if u.startswith("postgres://"):
            u = u.replace("postgres://", "postgresql+psycopg://", 1)
        elif u.startswith("postgresql://"):
            u = u.replace("postgresql://", "postgresql+psycopg://", 1)
        return u
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{settings.db_path}"


def _is_transaction_pooler(url: str) -> bool:
    """Detecta pooler em modo transação (Supabase Supavisor, PgBouncer).

    Importa porque nesse modo a conexão é reatribuída a cada transação, então
    um `prepared statement` criado numa requisição não existe na seguinte — e
    o psycopg cria isso sozinho por padrão. O sintoma é um erro intermitente
    de "prepared statement does not exist" que só aparece sob carga.
    """
    return ":6543" in url or "pooler.supabase.com" in url


def connect() -> Engine:
    global _engine
    if _engine is None:
        url = _url()
        kwargs: dict[str, Any] = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        elif _is_transaction_pooler(url):
            # o pooler externo já gerencia conexões: um pool nosso por cima
            # só atrapalha. E prepared statements têm que sair de cena.
            from sqlalchemy.pool import NullPool
            kwargs.update(poolclass=NullPool,
                          connect_args={"prepare_threshold": None})
        else:
            # serverless abre e fecha conexão o tempo todo; sem pre_ping a
            # função herda um socket morto do pool e falha na primeira query
            kwargs.update(pool_pre_ping=True, pool_size=1, max_overflow=2)
        _engine = create_engine(url, **kwargs)
        metadata.create_all(_engine)
    return _engine


def reset_engine() -> None:
    """Usado pelos testes, que trocam o banco a cada caso."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


@contextmanager
def tx() -> Iterator:
    with connect().begin() as conn:
        yield conn


def _aware(dt: datetime) -> datetime:
    """O SQLite devolve datetime sem fuso; sem isto a comparação explode."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _upsert(conn, table: Table, values: dict, index_elements: list[str],
            update_cols: dict | None = None) -> None:
    """INSERT ... ON CONFLICT DO UPDATE, no dialeto certo."""
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(table).values(**values)
    else:
        from sqlalchemy.dialects.sqlite import insert as sq_insert
        stmt = sq_insert(table).values(**values)
    setter = update_cols if update_cols is not None else {
        k: getattr(stmt.excluded, k) for k in values if k not in index_elements
    }
    conn.execute(stmt.on_conflict_do_update(index_elements=index_elements, set_=setter))


# ---------------------------------------------------------------- eventos

def upsert_event(ev: Event) -> None:
    with tx() as c:
        _upsert(c, events, {
            "id": ev.id, "sport_key": ev.sport_key, "league": ev.league,
            "home": ev.home, "away": ev.away,
            "commence_time": _aware(ev.commence_time),
            "betfair_market_id": ev.betfair_market_id,
        }, ["id"])


def _to_event(r) -> Event:
    return Event(id=r.id, sport_key=r.sport_key, league=r.league or "",
                 home=r.home, away=r.away,
                 commence_time=_aware(r.commence_time),
                 betfair_market_id=r.betfair_market_id)


def get_event(event_id: str) -> Event | None:
    with connect().connect() as c:
        r = c.execute(select(events).where(events.c.id == event_id)).first()
    return _to_event(r) if r else None


def upcoming_events(limit: int = 100) -> list[Event]:
    with connect().connect() as c:
        rows = c.execute(
            select(events).order_by(events.c.commence_time.asc()).limit(limit)
        ).fetchall()
    return [_to_event(r) for r in rows]


# ---------------------------------------------------------------- cotações

def insert_quotes(rows: list[Quote]) -> None:
    if not rows:
        return
    with tx() as c:
        c.execute(insert(quotes), [
            {"event_id": q.event_id, "bookmaker": q.bookmaker,
             "outcome": q.outcome.value, "back": q.back, "lay": q.lay,
             "ts": _aware(q.ts)} for q in rows
        ])


def quote_history(event_id: str, bookmaker: str, outcome: str,
                  limit: int = 200) -> list[Quote]:
    with connect().connect() as c:
        rows = c.execute(
            select(quotes)
            .where(quotes.c.event_id == event_id,
                   quotes.c.bookmaker == bookmaker,
                   quotes.c.outcome == outcome)
            .order_by(quotes.c.ts.desc()).limit(limit)
        ).fetchall()
    return [Quote(event_id=r.event_id, bookmaker=r.bookmaker, outcome=r.outcome,
                  back=r.back, lay=r.lay, ts=_aware(r.ts)) for r in rows]


# ----------------------------------------------------------------- sinais

def insert_signal(sig: Signal) -> None:
    with tx() as c:
        _upsert(c, signals, {
            "id": sig.id, "payload": sig.model_dump_json(), "kind": sig.kind.value,
            "event_id": sig.event_id, "ts": _aware(sig.ts), "acted": False,
        }, ["id"])


def recent_signals(limit: int = 50) -> list[Signal]:
    with connect().connect() as c:
        rows = c.execute(
            select(signals.c.payload).order_by(signals.c.ts.desc()).limit(limit)
        ).fetchall()
    return [Signal.model_validate_json(r.payload) for r in rows]


def mark_acted(signal_id: str) -> None:
    with tx() as c:
        c.execute(update(signals).where(signals.c.id == signal_id).values(acted=True))


# --------------------------------------------------------------- palpites

def save_pick(pick: Pick) -> None:
    key = f"{pick.event_id}|{pick.outcome.value}|{pick.side}"
    with tx() as c:
        _upsert(c, picks, {
            "id": pick.id, "payload": pick.model_dump_json(),
            "event_id": pick.event_id, "outcome": pick.outcome.value,
            "side": pick.side, "commence_time": _aware(pick.commence_time),
            "settled": bool(pick.result), "taken_at": _aware(pick.taken_at),
            "dedupe": key,
        }, ["dedupe"], update_cols={"payload": pick.model_dump_json(),
                                    "settled": bool(pick.result)})


def open_picks() -> list[Pick]:
    """Jogos que ainda não começaram: os que ainda podem ter fechamento."""
    now = datetime.now(timezone.utc)
    with connect().connect() as c:
        rows = c.execute(
            select(picks.c.payload)
            .where(picks.c.settled.is_(False), picks.c.commence_time > now)
            .order_by(picks.c.commence_time)
        ).fetchall()
    return [Pick.model_validate_json(r.payload) for r in rows]


def all_picks(limit: int = 500) -> list[Pick]:
    with connect().connect() as c:
        rows = c.execute(
            select(picks.c.payload).order_by(picks.c.taken_at.desc()).limit(limit)
        ).fetchall()
    return [Pick.model_validate_json(r.payload) for r in rows]


def find_pick(event_id: str, outcome: str, side: str) -> Pick | None:
    with connect().connect() as c:
        r = c.execute(select(picks.c.payload).where(
            picks.c.dedupe == f"{event_id}|{outcome}|{side}")).first()
    return Pick.model_validate_json(r.payload) if r else None


# ----------------------------------------------------------------- cartas

def save_card(card: DailyCard) -> None:
    with tx() as c:
        _upsert(c, cards, {"date": card.date, "payload": card.model_dump_json(),
                           "ts": _aware(card.generated_at)}, ["date"])


def get_card(date: str) -> DailyCard | None:
    with connect().connect() as c:
        r = c.execute(select(cards.c.payload).where(cards.c.date == date)).first()
    return DailyCard.model_validate_json(r.payload) if r else None


def latest_card() -> DailyCard | None:
    with connect().connect() as c:
        r = c.execute(select(cards.c.payload).order_by(cards.c.date.desc()).limit(1)).first()
    return DailyCard.model_validate_json(r.payload) if r else None


# --------------------------------------------------------------- créditos

def record_credit(usage: CreditUsage) -> None:
    with tx() as c:
        c.execute(insert(credit_usage).values(
            provider=usage.provider, endpoint=usage.endpoint,
            credits=usage.credits, remaining=usage.remaining, ts=_aware(usage.ts)))


def credits_used_since(provider: str, since: datetime) -> int:
    with connect().connect() as c:
        r = c.execute(select(func.coalesce(func.sum(credit_usage.c.credits), 0))
                      .where(credit_usage.c.provider == provider,
                             credit_usage.c.ts >= _aware(since))).scalar()
    return int(r or 0)


# ------------------------------------------------------------------- push

def save_subscription(sub: PushSubscription) -> None:
    with tx() as c:
        _upsert(c, push_subs, {
            "endpoint": sub.endpoint, "p256dh": sub.p256dh, "auth": sub.auth,
            "label": sub.label, "ts": datetime.now(timezone.utc)}, ["endpoint"])


def all_subscriptions() -> list[PushSubscription]:
    with connect().connect() as c:
        rows = c.execute(select(push_subs)).fetchall()
    return [PushSubscription(endpoint=r.endpoint, p256dh=r.p256dh,
                             auth=r.auth, label=r.label or "") for r in rows]


def delete_subscription(endpoint: str) -> None:
    with tx() as c:
        c.execute(delete(push_subs).where(push_subs.c.endpoint == endpoint))


# --------------------------------------------------------------------- kv

def kv_get(key: str, default: Any = None) -> Any:
    with connect().connect() as c:
        r = c.execute(select(kv.c.value).where(kv.c.key == key)).first()
    return json.loads(r.value) if r else default


def kv_set(key: str, value: Any) -> None:
    with tx() as c:
        _upsert(c, kv, {"key": key, "value": json.dumps(value)}, ["key"])
