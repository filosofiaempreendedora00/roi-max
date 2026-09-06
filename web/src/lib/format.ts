export const pct = (v: number, d = 1) => `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
export const odds = (v: number) => v.toFixed(2);
export const num = (v: number, d = 2) => v.toFixed(d);

export function ago(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}min`;
  return `${Math.floor(s / 3600)}h`;
}

export function until(iso: string | null): string | null {
  if (!iso) return null;
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  if (s <= 0) return null;
  return s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}min`;
}

export const OUTCOME_PT: Record<string, string> = {
  HOME: "Casa", DRAW: "Empate", AWAY: "Fora",
};

export const KIND_PT: Record<string, string> = {
  VALUE_BACK: "Back de valor",
  VALUE_LAY: "Lay de valor",
  ARBITRAGE: "Arbitragem",
  STEAM: "Movimento brusco",
  WIDE_SPREAD: "Book fino",
};

/** Nome do time correspondente ao resultado, extraído de "A x B". */
export function outcomeTeam(label: string, outcome: string): string {
  const parts = label.split(" x ");
  if (outcome === "HOME") return parts[0] ?? "Casa";
  if (outcome === "AWAY") return parts[1] ?? "Fora";
  return "Empate";
}
