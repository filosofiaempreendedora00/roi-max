"""Laço de ingestão consciente de orçamento.

Com 500 créditos/mês, polling ingênuo queima a cota em três dias. A regra
aqui é: só varre dentro da janela em que você opera, distribui a cota do dia
pelas horas dessa janela, e guarda uma reserva para o fim do mês.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db, push
from .budget import odds_api_budget
from .engine.detectors import Context, Thresholds, run_all
from .hub import hub
from .models import MarketBook, Signal
from .providers.theoddsapi import DEFAULT_SPORTS, TheOddsAPI

log = logging.getLogger(__name__)
BRT = ZoneInfo("America/Sao_Paulo")


@dataclass
class ScanConfig:
    """Tudo o que você calibra sem tocar em código (persistido no banco)."""

    sports: list[str] = field(default_factory=lambda: list(DEFAULT_SPORTS))
    window_start: str = "13:00"      # horário de Brasília
    window_end: str = "23:30"
    enabled: bool = True
    push_enabled: bool = True
    min_ev_to_push: float = 0.03
    cooldown_min: int = 20           # não repetir o mesmo sinal antes disso
    thresholds: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "ScanConfig":
        raw = db.kv_get("scan_config")
        return cls(**raw) if raw else cls()

    def save(self) -> None:
        db.kv_set("scan_config", self.__dict__)

    def in_window(self, now: datetime | None = None) -> bool:
        now = (now or datetime.now(timezone.utc)).astimezone(BRT)
        try:
            sh, sm = map(int, self.window_start.split(":"))
            eh, em = map(int, self.window_end.split(":"))
        except ValueError:
            return True
        start, end = time(sh, sm), time(eh, em)
        cur = now.time()
        if start <= end:
            return start <= cur <= end
        return cur >= start or cur <= end  # janela que cruza a meia-noite

    def to_thresholds(self) -> Thresholds:
        return Thresholds(**self.thresholds) if self.thresholds else Thresholds()


class Scanner:
    def __init__(self) -> None:
        self.provider = TheOddsAPI()
        self._recent: dict[str, datetime] = {}   # fingerprint -> visto em
        self.last_error: str | None = None

    # ------------------------------------------------------------- dedupe

    @staticmethod
    def _fingerprint(sig: Signal) -> str:
        return f"{sig.event_id}|{sig.outcome.value}|{sig.side}|{sig.kind.value}"

    def _is_fresh(self, sig: Signal, cooldown_min: int) -> bool:
        now = datetime.now(timezone.utc)
        fp = self._fingerprint(sig)
        seen = self._recent.get(fp)
        if seen and now - seen < timedelta(minutes=cooldown_min):
            return False
        self._recent[fp] = now
        # limpeza preguiçosa
        cutoff = now - timedelta(hours=6)
        for k in [k for k, v in self._recent.items() if v < cutoff]:
            self._recent.pop(k, None)
        return True

    # --------------------------------------------------------------- scan

    def _context(self, books: list[MarketBook], cfg: ScanConfig) -> Context:
        """Carrega o histórico recente só dos pares que vamos avaliar."""
        history = {}
        for b in books:
            for q in b.quotes:
                if not q.bookmaker.startswith("betfair"):
                    continue
                key = (b.event.id, q.bookmaker, q.outcome.value)
                if key not in history:
                    history[key] = db.quote_history(*key, limit=50)
        return Context(thresholds=cfg.to_thresholds(), history=history)

    async def scan_once(self, cfg: ScanConfig | None = None, *,
                        urgent: bool = False) -> list[Signal]:
        cfg = cfg or ScanConfig.load()
        if not self.provider.enabled:
            self.last_error = "ODDS_API_KEY não configurada — rodando em modo replay"
            return []

        hub.status = "scanning"
        await hub.broadcast("status", {"status": "scanning"})

        all_books: list[MarketBook] = []
        for sport in cfg.sports:
            try:
                books = await self.provider.fetch_odds(sport, urgent=urgent)
            except Exception as exc:
                log.exception("falha ao buscar %s", sport)
                self.last_error = str(exc)
                continue
            all_books.extend(books)
            if not odds_api_budget.can_spend(2, urgent=urgent):
                log.warning("orçamento esgotado no meio da varredura")
                break

        # persiste tudo: é o que alimenta o detector de steam e o histórico
        for b in all_books:
            db.upsert_event(b.event)
            db.insert_quotes(b.quotes)

        ctx = self._context(all_books, cfg)
        fresh: list[Signal] = []
        for b in all_books:
            for sig in run_all(b, ctx):
                if self._is_fresh(sig, cfg.cooldown_min):
                    db.insert_signal(sig)
                    fresh.append(sig)

        fresh.sort(key=lambda s: s.ev, reverse=True)

        hub.status = "idle"
        hub.last_scan = datetime.now(timezone.utc)
        if fresh:
            await hub.broadcast("signals", [s.model_dump() for s in fresh])
        await hub.broadcast("status", {
            "status": "idle",
            "last_scan": hub.last_scan.isoformat(),
            "budget": odds_api_budget.status().__dict__,
            "found": len(fresh),
            "events": len(all_books),
        })

        if cfg.push_enabled:
            for sig in fresh:
                if sig.ev >= cfg.min_ev_to_push:
                    push.send_signal(sig)

        self.last_error = None
        return fresh

    # ---------------------------------------------------------------- loop

    async def run_forever(self) -> None:
        """Acorda de tempos em tempos e decide se vale gastar crédito agora."""
        log.info("scheduler iniciado")
        while True:
            try:
                cfg = ScanConfig.load()
                if not cfg.enabled or not self.provider.enabled:
                    await asyncio.sleep(300)
                    continue
                if not cfg.in_window():
                    await asyncio.sleep(600)
                    continue

                st = odds_api_budget.status()
                cost = 2 * len(cfg.sports)
                if st.daily_allowance < cost:
                    # cota do dia não cobre uma varredura completa: reduz o escopo
                    keep = max(1, st.daily_allowance // 2)
                    cfg.sports = cfg.sports[:keep]
                    cost = 2 * len(cfg.sports)

                if not odds_api_budget.can_spend(cost):
                    log.info("sem orçamento para varrer agora; aguardando")
                    await asyncio.sleep(1800)
                    continue

                await self.scan_once(cfg)

                # espaça as varreduras para caber na cota diária
                scans_per_day = max(1, st.daily_allowance // max(cost, 1))
                window_hours = 10
                sleep_s = max(300, int(window_hours * 3600 / scans_per_day))
                log.info("próxima varredura em %d min (%d/dia)", sleep_s // 60, scans_per_day)
                await asyncio.sleep(sleep_s)

            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("erro no laço do scheduler")
                await asyncio.sleep(120)


scanner = Scanner()
