// The viewer's role until sessions exist (§7.4): sent as X-Fw-Role on every
// request. Kept in localStorage as a per-viewer convenience; storage can be
// missing or blocked, so every access is guarded and the default still works.
import { userRole, type UserRole } from "../contracts/enums";

const KEY = "fw-role";
export const DEFAULT_ROLE: UserRole = "ML_ENGINEER";

export function getRole(): UserRole {
  try {
    const stored = globalThis.localStorage?.getItem(KEY);
    return stored && (userRole as readonly string[]).includes(stored) ? (stored as UserRole) : DEFAULT_ROLE;
  } catch {
    return DEFAULT_ROLE;
  }
}

export function setRole(role: UserRole): void {
  try {
    globalThis.localStorage?.setItem(KEY, role);
  } catch {
    // Storage blocked: the role lasts until reload, which is acceptable for a dev switch.
  }
  current = role;
}

let current: UserRole | null = null;

/** The role for this request: the one just chosen, else the stored one. */
export const role = (): UserRole => current ?? getRole();
