"""Notificações push (Web Push / VAPID).

É a peça que atende o requisito de timing: o sinal precisa furar a tela
bloqueada do celular. Funciona em Android e, com a PWA instalada na tela
inicial, em iOS 16.4+.

Gerar as chaves uma vez:  python -m roimax.push --generate-keys
"""
from __future__ import annotations

import json
import logging

from . import db
from .config import settings
from .models import DailyCard, Signal

log = logging.getLogger(__name__)


def generate_keys() -> tuple[str, str]:
    """Devolve (public, private) em base64url, prontos para o .env."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return b64(public_raw), b64(private_raw)


def _notification(sig: Signal) -> dict:
    arrow = "▲" if sig.side == "back" else "▼"
    return {
        "title": f"{arrow} {sig.side.upper()} {sig.outcome.value} @ {sig.market_odds:.2f}",
        "body": f"{sig.event_label}\n{sig.edge_pct:+.1f}% vs justo {sig.fair_odds:.2f} "
                f"· EV {sig.ev:+.3f}",
        "tag": sig.event_id,
        "url": f"/signal/{sig.id}",
        "deeplink": sig.deeplink,
        "signal_id": sig.id,
    }


def send_signal(sig: Signal) -> int:
    """Dispara o sinal para todos os dispositivos inscritos. Retorna quantos receberam."""
    if not settings.vapid_private_key:
        log.debug("VAPID não configurado; push desativado")
        return 0

    from pywebpush import WebPushException, webpush

    sent = 0
    for sub in db.all_subscriptions():
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps(_notification(sig)),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=300,  # sinal velho não serve para nada
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                db.delete_subscription(sub.endpoint)  # inscrição morta
            else:
                log.warning("push falhou: %s", exc)
    return sent


if __name__ == "__main__":
    pub, priv = generate_keys()
    print("Cole no seu .env:\n")
    print(f"VAPID_PUBLIC_KEY={pub}")
    print(f"VAPID_PRIVATE_KEY={priv}")


def send_card(card: DailyCard) -> int:
    """Uma notificação por dia, com a carta inteira. É a única que precisa
    furar a tela bloqueada — as outras são ruído."""
    if not settings.vapid_private_key or not card.entries:
        return 0

    import json as _json

    from pywebpush import WebPushException, webpush

    top = card.entries[0].signal
    body = "\n".join(
        f"{e.rank}. {e.signal.side.upper()} {e.signal.event_label} "
        f"@ {e.signal.market_odds:.2f} (min {e.limit_price:.2f}) R$ {e.stake:.0f}"
        for e in card.entries[:5]
    )
    payload = {
        "title": f"Carta do dia: {len(card.entries)} entradas",
        "body": body,
        "tag": f"card-{card.date}",
        "url": "/card",
        "deeplink": top.deeplink,
    }
    sent = 0
    for sub in db.all_subscriptions():
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint,
                                   "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=_json.dumps(payload),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=6 * 3600,  # a carta vale o dia, não os cinco minutos
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, "status_code", None) in (404, 410):
                db.delete_subscription(sub.endpoint)
    return sent
