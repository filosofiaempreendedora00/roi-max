"""Configuração central. Tudo vem do .env na raiz do projeto."""
from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="before")
    @classmethod
    def _vazio_e_o_mesmo_que_ausente(cls, values):
        """Painéis de nuvem criam variáveis com valor vazio o tempo todo.

        Sem isto, um `BETFAIR_COMMISSION=` em branco faz o pydantic tentar
        converter "" para número e derrubar a aplicação na inicialização — que
        na Vercel aparece só como FUNCTION_INVOCATION_FAILED, sem pista do
        motivo. Vazio passa a significar "usa o padrão".
        """
        if isinstance(values, dict):
            return {k: v for k, v in values.items()
                    if not (isinstance(v, str) and v.strip() == "")}
        return values

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

# Nada de escrever em disco durante o import. Em serverless o sistema de
# arquivos é somente leitura, e um mkdir aqui derruba a função ANTES do
# FastAPI carregar — o que aparece como FUNCTION_INVOCATION_FAILED, sem dizer
# o motivo. Quem precisa da pasta cria na hora de usar.
if not settings.is_serverless:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
