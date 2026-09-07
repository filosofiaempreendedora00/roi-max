"""Banco isolado por teste: o engine é global, então sem isto um teste
enxergaria os palpites do anterior."""
from __future__ import annotations

import pytest

from roimax import db
from roimax.config import settings


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    db.reset_engine()
    yield
    db.reset_engine()
