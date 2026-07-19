/**
 * Token storage.
 *
 * Tradeoff (explained briefly, per the spec's request): the "most
 * correct" way to store a JWT is an httpOnly cookie set by the server,
 * which JavaScript can never read -- that fully protects against XSS
 * token theft. But Nebula's backend is a plain JSON API (it issues the
 * token in a JSON response body, not a Set-Cookie header), and this
 * frontend is a separate origin/port (50080 vs 50051) talking to it
 * over plain fetch() calls with an Authorization header -- not cookie-
 * based auth. Changing that would mean modifying the backend, which is
 * explicitly out of scope here.
 *
 * Given that constraint, this project stores the token in
 * `localStorage`. It is deliberately NOT read during server-side
 * rendering (localStorage doesn't exist on the server) -- all reads
 * happen inside client components after mount, via AuthContext, which
 * keeps this SSR-safe (no hydration mismatch, no crash on the server).
 * If Nebula's backend ever moves to issuing an httpOnly session cookie
 * instead, this is the one file that would need to change.
 */

const TOKEN_KEY = "nebula_token";
const USER_KEY = "nebula_user";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable (private browsing, quota, etc.) -- fail
    // silently; the user will simply need to log in again each visit.
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
  } catch {
    // no-op
  }
}

export function getStoredUserJson(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}

export function setStoredUserJson(json: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(USER_KEY, json);
  } catch {
    // no-op
  }
}
