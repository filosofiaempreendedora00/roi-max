"""Coletor de fotografias do mercado de skins.

Testa a hipótese do Ragnarok: aparecem anúncios abaixo do preço corrente, e
eles sobrevivem tempo suficiente para serem pegos?

Isso não dá para responder com uma foto só — precisa de série temporal. O
script tira uma foto a cada N minutos e guarda. Depois o analisador procura
quedas bruscas no menor preço de um item e mede quanto tempo elas duram.

Fontes abertas e gratuitas, sem chave:
  - api.waxpeer.com/v1/prices   (menor preço + quantidade de anúncios)
  - market.csgo.com/api/v2/prices  (preço + volume de vendas)

Uso:
    python research/mercados/coletor.py [minutos_entre_fotos] [quantas_fotos]
"""
from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "snapshots"
FONTES = {
    "waxpeer": "https://api.waxpeer.com/v1/prices?game=csgo&minified=1",
    "marketcsgo": "https://market.csgo.com/api/v2/prices/USD.json",
}


def baixar(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            bruto = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                bruto = gzip.decompress(bruto)
            return json.loads(bruto)
    except Exception as exc:
        print(f"    falhou: {type(exc).__name__}: {exc}")
        return None


def foto() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(timezone.utc)
    carimbo = agora.strftime("%Y%m%dT%H%M%SZ")
    for nome, url in FONTES.items():
        d = baixar(url)
        if not d:
            continue
        itens = d.get("items", [])
        destino = DESTINO / f"{nome}_{carimbo}.json.gz"
        # comprimido: cada foto tem ~25 mil itens e o disco agradece
        with gzip.open(destino, "wt", encoding="utf-8") as f:
            json.dump({"ts": agora.isoformat(), "fonte": nome, "items": itens}, f)
        print(f"    {nome}: {len(itens)} itens -> {destino.name} "
              f"({destino.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    intervalo = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    quantas = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    print(f"Coletando {quantas} fotos, uma a cada {intervalo} min "
          f"({quantas * intervalo / 60:.1f} horas de cobertura)")
    for i in range(quantas):
        print(f"[{i+1}/{quantas}] {datetime.now().strftime('%H:%M:%S')}")
        foto()
        if i < quantas - 1:
            time.sleep(intervalo * 60)
    print("Coleta encerrada.")
