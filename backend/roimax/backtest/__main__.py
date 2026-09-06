"""CLI de backtest — roda sem chave de API nenhuma.

    python -m roimax.backtest --divs E0 SP1 I1 --seasons 2324 2425 2526
    python -m roimax.backtest --extra BRA --min-edge 5
"""
from __future__ import annotations

import argparse
import json
import sys

from ..engine.detectors import Context, Thresholds
from ..providers.footballdata_uk import EXTRA_CODES, MAIN_DIVS, load_extra, load_main
from .replay import baseline_closing_line, run_backtest


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest do motor de assimetria")
    ap.add_argument("--divs", nargs="*", default=["E0", "SP1", "I1", "D1", "F1"],
                    help=f"ligas principais: {', '.join(MAIN_DIVS)}")
    ap.add_argument("--seasons", nargs="*", default=["2223", "2324", "2425", "2526"])
    ap.add_argument("--extra", nargs="*", default=[],
                    help=f"ligas extras (sem odds de exchange): {', '.join(EXTRA_CODES)}")
    ap.add_argument("--min-edge", type=float, default=4.0)
    ap.add_argument("--min-ev", type=float, default=0.02)
    ap.add_argument("--min-books", type=int, default=3)
    ap.add_argument("--min-odds", type=float, default=1.30)
    ap.add_argument("--max-odds", type=float, default=6.00)
    ap.add_argument("--commission", type=float, default=0.065)
    ap.add_argument("--stake", choices=["flat", "kelly"], default="flat")
    ap.add_argument("--lay-spread", type=float, default=0.0,
                    help="spread sintético para habilitar sinais de LAY (0 = desligado)")
    ap.add_argument("--refresh", action="store_true", help="reBaixa os CSVs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # com --json o stdout tem que ser JSON puro, senão não dá para encadear
    chatter = sys.stderr if args.json else sys.stdout

    matches = []
    for div in args.divs:
        got = load_main(div, args.seasons, refresh=args.refresh)
        print(f"  {div:>4}: {len(got):5d} partidas", file=chatter)
        matches.extend(got)
    for code in args.extra:
        got = load_extra(code, refresh=args.refresh)
        print(f"  {code:>4}: {len(got):5d} partidas", file=chatter)
        matches.extend(got)

    if not matches:
        print("\nNenhuma partida carregada. Verifique a conexão com football-data.co.uk.",
              file=chatter)
        return

    matches.sort(key=lambda m: m.date)
    ctx = Context(
        thresholds=Thresholds(min_edge_pct=args.min_edge, min_ev=args.min_ev,
                              min_books=args.min_books,
                              min_odds=args.min_odds, max_odds=args.max_odds),
        commission=args.commission,
    )
    res = run_backtest(matches, ctx=ctx, stake_mode=args.stake,
                       lay_spread=args.lay_spread)

    if args.json:
        print(json.dumps({"resumo": res.summary(),
                          "controle": baseline_closing_line(matches)},
                         indent=2, ensure_ascii=False))
        return

    s = res.summary()
    print("\n" + "=" * 58)
    print("  RESULTADO DO BACKTEST")
    print("=" * 58)
    for k in ("partidas_analisadas", "apostas", "taxa_de_selecao_pct",
              "unidades_arriscadas", "lucro_unidades", "roi_pct", "acerto_pct",
              "odd_media", "drawdown_max_unidades"):
        print(f"  {k:<26} {s[k]}")
    print("-" * 58)
    print(f"  {'clv_medio_pct':<26} {s['clv_medio_pct']}")
    print(f"  {'clv_positivo_pct':<26} {s['clv_positivo_pct']}")
    print("-" * 58)
    print("  Controle (back no favorito):", baseline_closing_line(matches))
    print("\n  Por liga:")
    for league, v in s["por_liga"].items():
        print(f"    {league:<28} n={v['n']:<5} ROI={v['roi_pct']:>7.2f}%  P&L={v['pnl']:>8.2f}")
    print("\n  Leia o CLV antes do ROI: CLV médio positivo e acima de ~52% de")
    print("  apostas batendo o fechamento é o que sustenta lucro no longo prazo.")
    print("=" * 58)


if __name__ == "__main__":
    main()
