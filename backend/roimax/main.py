"""API HTTP + WebSocket. Um servidor, dois clientes idênticos."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import clv, dailycard, db, push
from .budget import odds_api_budget
from .config import ROOT, settings
from .hub import hub
from .models import PushSubscription
from .scheduler import ScanConfig, scanner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("roimax")

WEB_DIST = ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    task = None
    if settings.is_serverless:
        # a varredura vem de fora, por /api/cron/scan
        log.info("modo serverless: agendador interno desligado")
    else:
        task = asyncio.create_task(scanner.run_forever())
    log.info("ROI Max no ar — odds ao vivo: %s", settings.has_live_odds)
    yield
    if task:
        task.cancel()


app = FastAPI(title="ROI Max", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def require_token(
    token: str = Query(default=""),
    x_token: str = Header(default="", alias="X-Token"),
) -> None:
    """Aceita o token por header ou por query.

    O header é o caminho normal — token em query string vai parar no log de
    acesso do servidor. A query fica só para o WebSocket, porque o navegador
    não deixa definir headers no handshake.
    """
    if settings.roimax_token not in (token, x_token):
        raise HTTPException(status_code=401, detail="token inválido")


def _snapshot() -> dict:
    cfg = ScanConfig.load()
    return {
        "signals": [s.model_dump() for s in db.recent_signals(60)],
        "card": (db.latest_card().model_dump() if db.latest_card() else None),
        "clv": clv.stats().__dict__ | {"veredito": clv.stats().verdict},
        "budget": odds_api_budget.status().__dict__,
        "config": cfg.__dict__,
        "status": hub.status,
        "last_scan": hub.last_scan.isoformat() if hub.last_scan else None,
        "live_odds_enabled": settings.has_live_odds,
        "push_configured": bool(settings.vapid_public_key),
        "commission": settings.betfair_commission,
        "clients": hub.n_clients,
        "last_error": scanner.last_error,
    }


# ------------------------------------------------------------------ REST

@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "live_odds": settings.has_live_odds, "clients": hub.n_clients}


@app.get("/api/state", dependencies=[Depends(require_token)])
async def state() -> dict:
    return _snapshot()


@app.post("/api/scan", dependencies=[Depends(require_token)])
async def scan(urgent: bool = False) -> dict:
    """Varredura manual. Consome créditos — use quando for operar."""
    sigs = await scanner.scan_once(urgent=urgent)
    return {"found": len(sigs), "signals": [s.model_dump() for s in sigs],
            "budget": odds_api_budget.status().__dict__}


@app.post("/api/signals/{signal_id}/act", dependencies=[Depends(require_token)])
async def act(signal_id: str) -> dict:
    db.mark_acted(signal_id)
    await hub.broadcast("acted", {"signal_id": signal_id})
    return {"ok": True}


@app.get("/api/card", dependencies=[Depends(require_token)])
async def card(date: str | None = None) -> dict:
    c = db.get_card(date) if date else db.latest_card()
    return c.model_dump() if c else {"date": None, "entries": [], "note": "Sem carta ainda."}


@app.post("/api/card/build", dependencies=[Depends(require_token)])
async def card_build() -> dict:
    """Monta a carta agora, a partir dos sinais já em banco. Não gasta crédito."""
    cfg = ScanConfig.load()
    c = dailycard.build(
        db.recent_signals(200),
        cfg=dailycard.CardConfig(max_entries=cfg.card_max_entries,
                                 bankroll=cfg.card_bankroll),
        target_ev=cfg.card_target_ev,
        scanned_events=len(db.upcoming_events(500)),
    )
    await hub.broadcast("card", c.model_dump())
    return c.model_dump()


@app.get("/api/clv", dependencies=[Depends(require_token)])
async def clv_stats() -> dict:
    picks = db.all_picks()
    st = clv.stats(picks)
    return {
        "n": st.n, "n_com_fechamento": st.n_with_closing,
        "clv_medio_pct": st.mean_clv, "bateu_o_fecho_pct": st.beat_rate,
        "odd_media": st.mean_odds, "veredito": st.verdict,
        "por_liga": clv.breakdown(picks),
        "palpites": [p.model_dump() for p in picks[:100]],
    }


@app.post("/api/picks/{pick_id}/placed", dependencies=[Depends(require_token)])
async def mark_placed(pick_id: str) -> dict:
    """Você confirmou a entrada na Betfair. Só o que estiver marcado conta
    no CLV real — palpite não executado mede o método, não o seu resultado."""
    for p in db.all_picks():
        if p.id == pick_id:
            p.placed = True
            db.save_pick(p)
            await hub.broadcast("pick", p.model_dump())
            return {"ok": True}
    raise HTTPException(status_code=404, detail="palpite não encontrado")


class ConfigPatch(BaseModel):
    sports: list[str] | None = None
    window_start: str | None = None
    window_end: str | None = None
    enabled: bool | None = None
    push_enabled: bool | None = None
    min_ev_to_push: float | None = None
    cooldown_min: int | None = None
    thresholds: dict | None = None
    card_enabled: bool | None = None
    card_time: str | None = None
    card_max_entries: int | None = None
    card_bankroll: float | None = None
    card_target_ev: float | None = None
    include_lay: bool | None = None


@app.patch("/api/config", dependencies=[Depends(require_token)])
async def patch_config(patch: ConfigPatch) -> dict:
    cfg = ScanConfig.load()
    for k, v in patch.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    cfg.save()
    await hub.broadcast("config", cfg.__dict__)
    return cfg.__dict__


@app.get("/api/budget", dependencies=[Depends(require_token)])
async def budget() -> dict:
    return odds_api_budget.status().__dict__


# ------------------------------------------------------------------- cron

def require_cron(secret: str = Query(default=""),
                 x_cron: str = Header(default="", alias="X-Cron-Secret")) -> None:
    """O agendador externo usa segredo próprio, não o token do app.

    Separado de propósito: o token do app fica no navegador do celular, e um
    endpoint que gasta crédito não deve ser disparável por quem tem só isso.
    """
    expected = settings.cron_secret or settings.roimax_token
    if expected not in (secret, x_cron):
        raise HTTPException(status_code=401, detail="segredo de cron inválido")


@app.post("/api/cron/scan", dependencies=[Depends(require_cron)])
async def cron_scan(build_card: bool = False) -> dict:
    """Chamado pelo agendador externo. Varre, atualiza fechamentos e,
    opcionalmente, monta a carta do dia."""
    cfg = ScanConfig.load()
    sigs = await scanner.scan_once(cfg)
    out: dict = {"sinais": len(sigs), "orcamento": odds_api_budget.status().__dict__}
    if build_card:
        c = dailycard.build(
            db.recent_signals(200),
            cfg=dailycard.CardConfig(max_entries=cfg.card_max_entries,
                                     bankroll=cfg.card_bankroll),
            target_ev=cfg.card_target_ev,
            scanned_events=len(db.upcoming_events(500)),
        )
        if cfg.push_enabled and c.entries:
            push.send_card(c)
        out["carta"] = {"entradas": len(c.entries), "stake_total": c.total_stake}
    return out


# ------------------------------------------------------------------ push

@app.get("/api/push/key")
async def push_key() -> dict:
    return {"publicKey": settings.vapid_public_key}


@app.post("/api/push/subscribe", dependencies=[Depends(require_token)])
async def push_subscribe(sub: PushSubscription) -> dict:
    db.save_subscription(sub)
    return {"ok": True, "devices": len(db.all_subscriptions())}


@app.post("/api/push/test", dependencies=[Depends(require_token)])
async def push_test() -> dict:
    from datetime import timedelta

    from .models import Outcome, Signal, SignalKind, utcnow
    demo = Signal(
        id="test", kind=SignalKind.VALUE_BACK, event_id="test",
        event_label="Teste x ROI Max", outcome=Outcome.HOME, side="back",
        market_odds=2.50, fair_odds=2.20, edge_pct=13.6, ev=0.12, kelly=0.05,
        confidence=1.0, deeplink=f"https://{settings.betfair_domain}/exchange/plus/",
        expires_at=utcnow() + timedelta(minutes=5),
    )
    return {"sent": push.send_signal(demo)}


# ------------------------------------------------------------- backtest

class BacktestRequest(BaseModel):
    divisions: list[str] = ["E0", "SP1", "I1", "D1", "F1"]
    seasons: list[str] = ["2223", "2324", "2425", "2526"]
    extra: list[str] = []
    min_edge_pct: float = 4.0
    min_ev: float = 0.02
    min_books: int = 3
    stake_mode: str = "flat"
    lay_spread: float = 0.0


@app.post("/api/backtest", dependencies=[Depends(require_token)])
async def backtest(req: BacktestRequest) -> dict:
    try:
        from .backtest.replay import baseline_closing_line, run_backtest
        from .engine.detectors import Context, Thresholds
        from .providers.footballdata_uk import load_extra, load_main
    except ImportError:
        # pandas fica fora do pacote da nuvem: pesa demais para o limite de
        # tamanho da função e o backtest é trabalho de pesquisa, não de
        # operação diária. Roda na sua máquina, onde os CSVs ficam em cache.
        return {"erro": "O backtest roda localmente, não na nuvem. "
                        "Use ./scripts/backtest.sh ou a aba Backtest com o "
                        "servidor local em http://localhost:8000"}

    def work() -> dict:
        matches = []
        for div in req.divisions:
            matches.extend(load_main(div, req.seasons))
        for code in req.extra:
            matches.extend(load_extra(code))
        matches.sort(key=lambda m: m.date)
        if not matches:
            return {"erro": "nenhuma partida carregada — verifique a conexão ou as ligas"}
        ctx = Context(thresholds=Thresholds(
            min_edge_pct=req.min_edge_pct, min_ev=req.min_ev, min_books=req.min_books,
        ))
        res = run_backtest(matches, ctx=ctx, stake_mode=req.stake_mode,
                           lay_spread=req.lay_spread)
        return {
            "resumo": res.summary(),
            "controle_favorito": baseline_closing_line(matches),
            "curva": res.equity_curve[-500:],
            "ultimas_apostas": [b.__dict__ for b in res.bets[-40:]],
        }

    return await asyncio.to_thread(work)


# ------------------------------------------------------------ WebSocket

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")):
    if token != settings.roimax_token:
        await ws.close(code=4401)
        return
    await hub.connect(ws)
    try:
        await hub.send(ws, "snapshot", _snapshot())
        while True:
            raw = await ws.receive_text()
            if raw == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)


# ------------------------------------------------------------- estáticos

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
