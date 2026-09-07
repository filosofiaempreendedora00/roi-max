#!/usr/bin/env python
"""Copia o banco local para o Postgres da nuvem.

    ./scripts/db_copy.py "postgresql://usuario:senha@host/neondb?sslmode=require"

Só faz sentido uma vez, na migração. Depois disso a nuvem é a fonte da
verdade e o banco local vira ambiente de testes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, insert, select  # noqa: E402

from roimax import db  # noqa: E402
from roimax.config import settings  # noqa: E402

TABLES = ["events", "quotes", "signals", "picks", "cards",
          "credit_usage", "push_subs", "kv"]


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    target_url = sys.argv[1]
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif target_url.startswith("postgresql://"):
        target_url = target_url.replace("postgresql://", "postgresql+psycopg://", 1)

    source = create_engine(f"sqlite:///{settings.db_path}", future=True)
    target = create_engine(target_url, future=True)
    db.metadata.create_all(target)

    with source.connect() as src, target.begin() as dst:
        for name in TABLES:
            table = db.metadata.tables[name]
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            if not rows:
                print(f"  {name:<14} vazia")
                continue
            # a chave primária serial do Postgres se vira sozinha
            if name in ("quotes", "credit_usage"):
                for r in rows:
                    r.pop("id", None)
            dst.execute(insert(table), rows)
            print(f"  {name:<14} {len(rows)} linhas copiadas")

    print("\nPronto. Confira com: curl https://SEU-APP.vercel.app/api/health")


if __name__ == "__main__":
    main()
