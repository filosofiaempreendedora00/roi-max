import { useMemo, useState } from "react";
import { num } from "../lib/format";
import type { Side } from "../lib/types";

/**
 * Calculadora de stake embutida no card.
 *
 * No lay o número que assusta não é o stake, é a liability — e é justamente
 * o que a Betfair mostra por último. Aqui ele aparece primeiro.
 */
export function StakeCalc({
  side, odds, commission, kelly, bankroll,
}: {
  side: Side;
  odds: number;
  commission: number;
  kelly: number;
  bankroll: number;
}) {
  const suggested = Math.max(1, Math.round(bankroll * kelly * 0.25));
  const [stake, setStake] = useState<number>(suggested);

  const { profit, risk } = useMemo(() => {
    if (side === "back") {
      return { profit: (odds - 1) * stake * (1 - commission), risk: stake };
    }
    return { profit: stake * (1 - commission), risk: (odds - 1) * stake };
  }, [side, odds, stake, commission]);

  return (
    <div className="calc">
      <label className="calc-field">
        <span>Stake</span>
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step={1}
          value={Number.isFinite(stake) ? stake : ""}
          onChange={(e) => setStake(parseFloat(e.target.value))}
        />
      </label>
      <div className="calc-out">
        <div>
          <span className="calc-label">Lucro</span>
          <b className="pos">R$ {num(profit)}</b>
        </div>
        <div>
          <span className="calc-label">{side === "lay" ? "Liability" : "Risco"}</span>
          <b className="neg">R$ {num(risk)}</b>
        </div>
      </div>
      {kelly > 0 && (
        <p className="calc-hint">
          Kelly ¼ sugere R$ {suggested} sobre banca de R$ {bankroll}.
        </p>
      )}
    </div>
  );
}
