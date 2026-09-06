import { api } from "./api";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js");
  } catch {
    return null;
  }
}

export type PushResult =
  | { ok: true; devices: number }
  | { ok: false; reason: string };

/**
 * No iOS isto só funciona depois de "Adicionar à Tela de Início" — a Apple
 * não expõe push para PWA aberta no Safari.
 */
export async function enablePush(): Promise<PushResult> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return { ok: false, reason: "Este navegador não suporta push. No iPhone, adicione o app à Tela de Início primeiro." };
  }
  const { publicKey } = await api.pushKey();
  if (!publicKey) {
    return { ok: false, reason: "VAPID não configurado no servidor. Rode: python -m roimax.push --generate-keys" };
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, reason: "Permissão negada." };

  const reg = (await navigator.serviceWorker.ready) as ServiceWorkerRegistration;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });
  const json = sub.toJSON() as { endpoint?: string; keys?: Record<string, string> };
  const res = await api.pushSubscribe({
    endpoint: json.endpoint ?? "",
    p256dh: json.keys?.p256dh ?? "",
    auth: json.keys?.auth ?? "",
    label: navigator.userAgent.slice(0, 60),
  });
  return res.ok ? { ok: true, devices: 1 } : { ok: false, reason: "Falha ao registrar." };
}
