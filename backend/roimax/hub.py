"""Hub de sincronização.

O estado da aplicação vive aqui, no servidor. Desktop e celular não guardam
nada: assinam este hub e recebem o mesmo fluxo. É o que garante que os dois
mostram exatamente a mesma coisa no mesmo instante, sem lógica de merge.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


def _default(o: Any):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"não serializável: {type(o)}")


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.last_scan: datetime | None = None
        self.status: str = "idle"

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("cliente conectado (%d ativos)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def n_clients(self) -> int:
        return len(self._clients)

    async def send(self, ws: WebSocket, kind: str, payload: Any) -> None:
        await ws.send_text(json.dumps({"type": kind, "payload": payload,
                                       "ts": datetime.now(timezone.utc).isoformat()},
                                      default=_default))

    async def broadcast(self, kind: str, payload: Any) -> None:
        msg = json.dumps({"type": kind, "payload": payload,
                          "ts": datetime.now(timezone.utc).isoformat()}, default=_default)
        async with self._lock:
            targets = list(self._clients)
        dead = []
        for ws in targets:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


hub = Hub()
