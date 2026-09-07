"""Testes da camada de persistência que não dependem de banco remoto."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from roimax import db
from roimax.models import CreditUsage, Event, Outcome, Quote


def test_detecta_pooler_de_transacao():
    """Supabase em modo transação exige tratamento especial; errar isso dá
    erro intermitente de prepared statement que só aparece sob carga."""
    assert db._is_transaction_pooler(
        "postgresql://u:p@aws-0-sa-east-1.pooler.supabase.com:6543/postgres")
    assert db._is_transaction_pooler("postgresql://u:p@host:6543/db")


def test_conexao_direta_nao_e_pooler():
    assert not db._is_transaction_pooler("postgresql://u:p@db.abc.supabase.co:5432/postgres")
    assert not db._is_transaction_pooler("postgresql://u:p@ep-x.neon.tech/neondb")
    assert not db._is_transaction_pooler("sqlite:///local.db")


def test_url_normaliza_esquema_do_postgres(monkeypatch):
    """Neon e Supabase entregam 'postgres://'; o SQLAlchemy recusa isso."""
    from roimax.config import settings
    monkeypatch.setattr(settings, "database_url", "postgres://u:p@h/db")
    assert db._url().startswith("postgresql+psycopg://")
    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@h/db")
    assert db._url().startswith("postgresql+psycopg://")


def test_ida_e_volta_de_evento():
    ko = datetime.now(timezone.utc) + timedelta(hours=3)
    db.upsert_event(Event(id="e1", home="A", away="B", commence_time=ko, league="L"))
    got = db.get_event("e1")
    assert got and got.home == "A" and got.league == "L"


def test_upsert_de_evento_nao_duplica():
    ko = datetime.now(timezone.utc) + timedelta(hours=3)
    for liga in ("Antiga", "Nova"):
        db.upsert_event(Event(id="e1", home="A", away="B", commence_time=ko, league=liga))
    assert len(db.upcoming_events()) == 1
    assert db.get_event("e1").league == "Nova"


def test_historico_de_cotacoes_vem_do_mais_novo():
    agora = datetime.now(timezone.utc)
    db.insert_quotes([
        Quote(event_id="e1", bookmaker="betfair_ex", outcome=Outcome.HOME,
              back=2.0, ts=agora - timedelta(minutes=10)),
        Quote(event_id="e1", bookmaker="betfair_ex", outcome=Outcome.HOME,
              back=2.5, ts=agora),
    ])
    h = db.quote_history("e1", "betfair_ex", "HOME")
    assert [q.back for q in h] == [2.5, 2.0]


def test_creditos_contam_so_a_partir_da_data():
    agora = datetime.now(timezone.utc)
    db.record_credit(CreditUsage(provider="p", endpoint="x", credits=5,
                                 ts=agora - timedelta(days=40)))
    db.record_credit(CreditUsage(provider="p", endpoint="x", credits=3, ts=agora))
    assert db.credits_used_since("p", agora - timedelta(days=1)) == 3
    assert db.credits_used_since("p", agora - timedelta(days=60)) == 8


def test_kv_guarda_estrutura():
    db.kv_set("cfg", {"a": [1, 2], "b": "x"})
    assert db.kv_get("cfg") == {"a": [1, 2], "b": "x"}
    assert db.kv_get("inexistente", "padrao") == "padrao"


# ------------------------------------------- configuração vinda de painel

def test_variavel_vazia_usa_o_padrao(monkeypatch):
    """Painel de nuvem cria variável em branco o tempo todo. Sem tolerar isso,
    o app morre na inicialização com erro que não diz nada."""
    from roimax.config import Settings
    for k in ("ODDS_API_MONTHLY_CREDITS", "BETFAIR_COMMISSION",
              "APIFOOTBALL_KEY", "DATABASE_URL"):
        monkeypatch.setenv(k, "")
    s = Settings(_env_file=None)
    assert s.odds_api_monthly_credits == 500
    assert s.betfair_commission == 0.065
    assert s.database_url == ""


def test_variavel_com_espacos_tambem_conta_como_vazia(monkeypatch):
    from roimax.config import Settings
    monkeypatch.setenv("BETFAIR_COMMISSION", "   ")
    assert Settings(_env_file=None).betfair_commission == 0.065


def test_valor_de_verdade_sobrescreve(monkeypatch):
    from roimax.config import Settings
    monkeypatch.setenv("ODDS_API_MONTHLY_CREDITS", "20000")
    monkeypatch.setenv("BETFAIR_COMMISSION", "0.02")
    s = Settings(_env_file=None)
    assert s.odds_api_monthly_credits == 20000
    assert s.betfair_commission == 0.02
