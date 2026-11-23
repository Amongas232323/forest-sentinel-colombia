import { useAuth } from "@/lib/auth/store";
import type { ApiErrorBody, TokenResponse } from "./types";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: { field: string; message: string }[] = [],
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

export function buildQuery(params: Query): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, v));
    else qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

let refreshing: Promise<boolean> | null = null;

/** Refresh de vuelo único: los 401 que llegan al tiempo comparten una sola petición de refresh. */
export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" })
      .then(async (res) => {
        if (!res.ok || res.status === 204) {
          useAuth.getState().clear();
          return false;
        }
        const data = (await res.json()) as TokenResponse;
        useAuth.getState().setSession(data.access_token, data.user);
        return true;
      })
      .catch(() => {
        useAuth.getState().clear();
        return false;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
}

export async function api<T>(path: string, { method = "GET", body, auth = true, signal }: RequestOptions = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = useAuth.getState().accessToken;
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });

  if (res.status === 401 && auth && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, { method, body, auth, signal }, false);
  }
  if (!res.ok) {
    let parsed: ApiErrorBody | null = null;
    try {
      parsed = (await res.json()) as ApiErrorBody;
    } catch {
      /* error que no es JSON */
    }
    throw new ApiError(
      res.status,
      parsed?.error.code ?? "http_error",
      parsed?.error.message ?? "No pudimos completar la solicitud. Inténtalo de nuevo.",
      parsed?.error.details ?? [],
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Descarga binaria autenticada (reportes). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = useAuth.getState().accessToken;
  const res = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: "same-origin" });
  if (res.status === 401 && (await refreshSession())) return downloadFile(path, fallbackName);
  if (!res.ok) throw new ApiError(res.status, "download_failed", "No se pudo descargar el archivo.");
  const blob = await res.blob();
  const name = /filename="?([^"]+)"?/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
