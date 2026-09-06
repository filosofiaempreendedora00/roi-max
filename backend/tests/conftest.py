"""Banco isolado por teste: o módulo db guarda uma conexão global, então sem
isto um teste enxergaria os palpites do anterior."""
from __future__ import annotations

import pytest

from roimax import db
from roimax.config import settings


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    monkeypatch.setattr(db, "_conn", None)
    yield
    monkeypatch.setattr(db, "_conn", None)
