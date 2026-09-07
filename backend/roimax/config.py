"""Configuração central. Tudo vem do .env na raiz do projeto."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- provedores de dados ---
    odds_api_key: str = ""
    odds_api_monthly_credits: int = 500
    apifootball_key: str = ""

    # --- parâmetros de mercado ---
    betfair_commission: float = 0.065
    betfair_domain: str = "www.betfair.bet.br"

    # --- push ---
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # --- app ---
    roimax_token: str = "troque-este-token"
    # Vazio = SQLite local. Na nuvem, a URL do Postgres (Neon, Supabase...).
    database_url: str = ""
    # Segredo separado para o agendador externo chamar /api/cron/*
    cron_secret: str = ""
    db_path: Path = ROOT / "data" / "roimax.db"
    data_dir: Path = ROOT / "data"

    # Em serverless não existe processo que sobreviva entre requisições, então
    # o laço de varredura não pode viver dentro do app. A Vercel define VERCEL=1.
    run_scheduler: bool = True

    @property
    def is_serverless(self) -> bool:
        import os
        return bool(os.environ.get("VERCEL")) or not self.run_scheduler

    @property
    def has_live_odds(self) -> bool:
        return bool(self.odds_api_key)


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
