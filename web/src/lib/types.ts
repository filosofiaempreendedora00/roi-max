export type Side = "back" | "lay";
export type Outcome = "HOME" | "DRAW" | "AWAY";
export type SignalKind =
  | "VALUE_BACK" | "VALUE_LAY" | "ARBITRAGE" | "STEAM" | "WIDE_SPREAD";

export interface Signal {
  id: string;
  kind: SignalKind;
  event_id: string;
  event_label: string;
  league: string;
  outcome: Outcome;
  side: Side;
  market_odds: number;
  fair_odds: number;
  edge_pct: number;
  ev: number;
  kelly: number;
  confidence: number;
  bookmaker: string;
  reference: string;
  deeplink: string;
  ts: string;
  expires_at: string | null;
  notes: string;
}

export interface Budget {
  provider: string;
  monthly: number;
  used: number;
  remaining: number;
  days_left: number;
  daily_allowance: number;
  reserve: number;
}

export interface ScanConfig {
  sports: string[];
  window_start: string;
  window_end: string;
  enabled: boolean;
  push_enabled: boolean;
  min_ev_to_push: number;
  cooldown_min: number;
  thresholds: Record<string, number>;
}

export interface Snapshot {
  signals: Signal[];
  budget: Budget;
  config: ScanConfig;
  status: string;
  last_scan: string | null;
  live_odds_enabled: boolean;
  push_configured: boolean;
  commission: number;
  clients: number;
  last_error: string | null;
}

export interface BacktestSummary {
  partidas_analisadas: number;
  apostas: number;
  taxa_de_selecao_pct: number;
  unidades_arriscadas: number;
  lucro_unidades: number;
  roi_pct: number;
  acerto_pct: number;
  odd_media: number;
  clv_medio_pct: number;
  clv_positivo_pct: number;
  drawdown_max_unidades: number;
  comissao_aplicada: number;
  por_tipo: Record<string, { n: number; pnl: number; roi_pct: number }>;
  por_liga: Record<string, { n: number; pnl: number; roi_pct: number }>;
}

export interface BacktestResponse {
  resumo?: BacktestSummary;
  controle_favorito?: { apostas: number; lucro_unidades: number; roi_pct: number };
  curva?: number[];
  ultimas_apostas?: Array<Record<string, unknown>>;
  erro?: string;
}
