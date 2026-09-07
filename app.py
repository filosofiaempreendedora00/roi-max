"""Ponto de entrada da Vercel.

A Vercel detecta FastAPI no requirements.txt e procura um `app` num arquivo de
nome conhecido na raiz — este. A partir daí a aplicação atende TODAS as rotas,
inclusive os arquivos da PWA, que o próprio FastAPI já serve.

Toda a lógica continua em `backend/roimax`, que roda igual aqui e no seu Mac.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from roimax.main import app  # noqa: E402,F401

__all__ = ["app"]
