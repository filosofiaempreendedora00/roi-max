import type { Budget } from "../lib/types";

/**
 * O free tier é a restrição que define o app. Deixar o consumo escondido é
 * como dirigir sem marcador de combustível.
 */
export function BudgetBar({ budget }: { budget: Budget }) {
  const used = budget.monthly ? (budget.used / budget.monthly) * 100 : 0;
  const reserve = budget.monthly ? (budget.reserve / budget.monthly) * 100 : 0;
  const level = used > 90 ? "crit" : used > 70 ? "warn" : "ok";

  return (
    <div className="budget">
      <div className="budget-head">
        <span>Créditos do mês</span>
        <b>
          {budget.remaining}/{budget.monthly}
        </b>
      </div>
      <div className="budget-track">
        <div className={`budget-fill ${level}`} style={{ width: `${Math.min(100, used)}%` }} />
        <div className="budget-reserve" style={{ width: `${reserve}%` }} title="reserva" />
      </div>
      <div className="budget-foot">
        <span>{budget.daily_allowance}/dia disponível</span>
        <span>{budget.days_left} dias até renovar</span>
      </div>
    </div>
  );
}
