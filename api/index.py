"""Ponto de entrada da Vercel.

A Vercel procura funções em `api/`. Este arquivo só reexporta o app FastAPI —
toda a lógica continua em `backend/roimax`, que roda igual aqui e no seu Mac.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from roimax.main import app  # noqa: E402

__all__ = ["app"]
