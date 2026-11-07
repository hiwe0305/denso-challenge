// The one fetch wrapper. Every component goes through it, so switching MSW off
// (VITE_API_MODE=real) points the FE at the backend without other changes.
import { role } from "./role";
import type { ActionAccepted, ApiError } from "./types";

export const API_BASE = "/api";

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly body: ApiError,
  ) {
    super(body.message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T;
  let body: ApiError;
  try {
    body = (await response.json()) as ApiError;
  } catch {
    body = { code: `HTTP_${response.status}`, message: response.statusText, hint: null, ref: null };
  }
  throw new ApiRequestError(response.status, body);
}

/** Every request says who is asking (§7.4); the API filters sealed rows by it (BR-10). */
const baseHeaders = (): Record<string, string> => ({ Accept: "application/json", "X-Fw-Role": role() });

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${API_BASE}${path}`, { headers: baseHeaders() }));
}

/**
 * POST that records a human action (§7.2). The caller makes the key once per
 * click and reuses it on retry, so a retried click yields the same action (C16).
 */
export async function apiAction(
  path: string,
  body: unknown,
  idempotencyKey: string,
): Promise<ActionAccepted> {
  return parse<ActionAccepted>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { ...baseHeaders(), "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    }),
  );
}

/** POST that is not a human action, e.g. `POST /sync/run` (§7.2, no action_kind). */
export async function apiPost<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${API_BASE}${path}`, { method: "POST", headers: baseHeaders() }));
}

/** POST or PATCH of a W-table record that is not an action yet, e.g. a draft (§7.2). */
export async function apiWrite<T>(path: string, body: unknown, method: "POST" | "PATCH" = "POST"): Promise<T> {
  return parse<T>(
    await fetch(`${API_BASE}${path}`, {
      method,
      headers: { ...baseHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export const newIdempotencyKey = (): string => crypto.randomUUID();
