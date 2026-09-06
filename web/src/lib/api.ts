import type { BacktestResponse, ScanConfig, Snapshot } from "./types";

const TOKEN_KEY = "roimax.token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}
export function setToken(t: string): void {
  localStorage.setItem(TOKEN_KEY, t);
}

/** Só o WebSocket usa o token na URL: o handshake não aceita headers. */
function qs(extra: Record<string, string> = {}): string {
  return new URLSearchParams({ token: getToken(), ...extra }).toString();
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Token": getToken(),
      ...(init?.headers ?? {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  state: () => req<Snapshot>("/api/state"),
  scan: (urgent = false) =>
    req<{ found: number }>(`/api/scan?urgent=${urgent}`, { method: "POST" }),
  act: (id: string) => req<{ ok: boolean }>(`/api/signals/${id}/act`, { method: "POST" }),
  patchConfig: (patch: Partial<ScanConfig>) =>
    req<ScanConfig>("/api/config", { method: "PATCH", body: JSON.stringify(patch) }),
  backtest: (body: Record<string, unknown>) =>
    req<BacktestResponse>("/api/backtest", { method: "POST", body: JSON.stringify(body) }),
  pushKey: () => fetch("/api/push/key").then((r) => r.json() as Promise<{ publicKey: string }>),
  pushSubscribe: (sub: Record<string, unknown>) =>
    req<{ ok: boolean }>("/api/push/subscribe", { method: "POST", body: JSON.stringify(sub) }),
  pushTest: () => req<{ sent: number }>("/api/push/test", { method: "POST" }),
};

export type WsEvent =
  | { type: "snapshot"; payload: Snapshot }
  | { type: "signals"; payload: Snapshot["signals"] }
  | { type: "status"; payload: Record<string, unknown> }
  | { type: "config"; payload: ScanConfig }
  | { type: "acted"; payload: { signal_id: string } };

/**
 * Conexão persistente com reconexão exponencial. É ela que mantém desktop e
 * celular vendo exatamente a mesma coisa: nenhum cliente guarda estado próprio.
 */
export function connect(
  onEvent: (e: WsEvent) => void,
  onStatus: (connected: boolean) => void
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let ping: ReturnType<typeof setInterval> | undefined;

  const open = () => {
    if (closed) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws?${qs()}`);

    ws.onopen = () => {
      attempt = 0;
      onStatus(true);
      ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send("ping"), 25000);
    };
    ws.onmessage = (ev) => {
      if (ev.data === "pong") return;
      try {
        onEvent(JSON.parse(ev.data) as WsEvent);
      } catch {
        /* mensagem malformada: ignora em vez de derrubar a conexão */
      }
    };
    ws.onclose = () => {
      onStatus(false);
      if (ping) clearInterval(ping);
      if (closed) return;
      const delay = Math.min(15000, 500 * 2 ** attempt++);
      setTimeout(open, delay);
    };
    ws.onerror = () => ws?.close();
  };

  open();
  // Voltar do background no celular costuma matar o socket em silêncio.
  const onVisible = () => {
    if (document.visibilityState === "visible" && ws?.readyState !== WebSocket.OPEN) {
      attempt = 0;
      open();
    }
  };
  document.addEventListener("visibilitychange", onVisible);

  return () => {
    closed = true;
    document.removeEventListener("visibilitychange", onVisible);
    if (ping) clearInterval(ping);
    ws?.close();
  };
}
