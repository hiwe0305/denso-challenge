// The one fetch wrapper. Every component goes through it, so switching MSW off
// (VITE_API_MODE=real) points the FE at the backend without other changes.
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

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } }));
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
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    }),
  );
}

export const newIdempotencyKey = (): string => crypto.randomUUID();
