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
  card_enabled: boolean;
  card_time: string;
  card_max_entries: number;
  card_bankroll: number;
  card_target_ev: number;
  include_lay: boolean;
  window_start: string;
  window_end: string;
  enabled: boolean;
  push_enabled: boolean;
  min_ev_to_push: number;
  cooldown_min: number;
  thresholds: Record<string, number>;
}

export interface CardEntry {
  signal: Signal;
  stake: number;
  limit_price: number;
  rank: number;
  reason: string;
}

export interface DailyCard {
  date: string;
  generated_at: string;
  entries: CardEntry[];
  scanned_events: number;
  bankroll: number;
  total_stake: number;
  note: string;
}

export interface ClvStats {
  n: number;
  n_with_closing: number;
  mean_clv: number;
  beat_rate: number;
  mean_odds: number;
  veredito: string;
}

export interface Pick {
  id: string;
  event_label: string;
  league: string;
  outcome: Outcome;
  side: Side;
  taken_odds: number;
  closing_odds: number | null;
  stake: number;
  placed: boolean;
  commence_time: string;
}

export interface Snapshot {
  signals: Signal[];
  card: DailyCard | null;
  clv: ClvStats;
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
