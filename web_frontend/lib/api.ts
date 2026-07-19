/**
 * Port configuration changes:
 * - Updated default backend fallback port from 50051 to 8000.
 * - Rationale: align backend default to port 8000.
 * - How to revert: change "http://localhost:8000/api/v1" back to "http://localhost:50051/api/v1".
 *
 * Single typed wrapper around every Nebula backend endpoint. Nothing
 * else in this project should call fetch() directly against the API --
 * components import functions from here instead, so the base URL,
 * auth header, and error handling all live in exactly one place.
 *
 * Base URL: read from NEXT_PUBLIC_API_BASE_URL (baked in at build
 * time by Next.js, since it's a browser-visible env var), defaulting
 * to the confirmed backend port 50051.
 */
import type {
  BootstrapStatusResponse,
  ChatHistoryResponse,
  ChatListResponse,
  ChatSummary,
  CoinStatusResponse,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  ModifyCoinsRequest,
  ModifyCoinsResponse,
  PendingUsersResponse,
  PlatformsResponse,
  ReviewUserRequest,
  ReviewUserResponse,
  SendMessageResponse,
  SignupRequest,
  SignupResponse,
  SyncCodeResponse,
  ToolToggles,
} from "@/types/api";
import { ApiError } from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Where the backend itself lives, without the /api/v1 suffix --
 * needed for the two Google OAuth endpoints, which are real browser
 * navigations (not fetch calls) and use the same base. */
function apiRoot(): string {
  return API_BASE_URL;
}

/**
 * Core request helper. Attaches the Authorization header automatically
 * when a token is passed, parses JSON responses, and throws ApiError
 * (carrying the backend's own `detail` string) on any non-2xx status
 * -- callers catch ApiError and show `.message` directly, since the
 * backend's detail strings are already written to be user-facing.
 */
async function request<T>(
  path: string,
  options: {
    method?: string;
    token?: string | null;
    json?: unknown;
    formData?: FormData;
    query?: Record<string, string | undefined>;
  } = {}
): Promise<T> {
  const { method = "GET", token, json, formData, query } = options;

  let url = `${API_BASE_URL}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) params.set(key, value);
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: formData ?? (json !== undefined ? JSON.stringify(json) : undefined),
    });
  } catch (err) {
    // Network-level failure (backend unreachable, CORS, DNS, etc.) --
    // not an HTTP error status, so there's no `detail` body to read.
    throw new ApiError(
      0,
      "Couldn't reach the Nebula server. Check that the backend is running and reachable."
    );
  }

  // 204 No Content (e.g. DELETE /chat/{id}) has no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  let body: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      // Non-JSON body (shouldn't normally happen against this API) --
      // fall through with body left null; the generic message below
      // covers this case.
    }
  }

  if (!response.ok) {
    const detail =
      (body && typeof body === "object" && "detail" in body && typeof (body as any).detail === "string"
        ? (body as any).detail
        : null) ?? `Request failed (${response.status}).`;
    throw new ApiError(response.status, detail);
  }

  return body as T;
}

// ---------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------

export function getBootstrapStatus(): Promise<BootstrapStatusResponse> {
  return request<BootstrapStatusResponse>("/auth/bootstrap-status");
}

export function signup(body: SignupRequest): Promise<SignupResponse> {
  return request<SignupResponse>("/auth/signup", { method: "POST", json: body });
}

export function login(body: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", { method: "POST", json: body });
}

/** Not a fetch call -- these two are real browser navigations, since
 * Google's OAuth flow requires the user's actual browser to visit
 * Google's consent screen and be redirected back. Components should
 * set `window.location.href = googleOAuthStartUrl()`, not call these
 * with fetch(). */
export function googleOAuthStartUrl(): string {
  return `${apiRoot()}/auth/google`;
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------

export function getChats(token: string): Promise<ChatListResponse> {
  return request<ChatListResponse>("/chat", { token });
}

export function createChat(token: string, title?: string): Promise<ChatSummary> {
  return request<ChatSummary>("/chat", { method: "POST", token, json: { title } });
}

export function getChatHistory(token: string, chatId: number): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>(`/chat/${chatId}`, { token });
}

export function renameChat(token: string, chatId: number, title: string): Promise<ChatSummary> {
  return request<ChatSummary>(`/chat/${chatId}`, {
    method: "PATCH",
    token,
    json: { title },
  });
}

export function deleteChat(token: string, chatId: number): Promise<void> {
  return request<void>(`/chat/${chatId}`, { method: "DELETE", token });
}

export function sendMessage(
  token: string,
  chatId: number,
  input: string,
  tools: ToolToggles = { search: true }
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(`/chat/${chatId}/messages`, {
    method: "POST",
    token,
    json: { input, tools },
  });
}

export function sendImageMessage(
  token: string,
  chatId: number,
  file: File,
  text: string
): Promise<SendMessageResponse> {
  const formData = new FormData();
  formData.append("image", file);
  return request<SendMessageResponse>(`/chat/${chatId}/messages/image`, {
    method: "POST",
    token,
    formData,
    query: { text },
  });
}

// ---------------------------------------------------------------------
// Coins
// ---------------------------------------------------------------------

export function getMyCoins(token: string): Promise<CoinStatusResponse> {
  return request<CoinStatusResponse>("/users/me/coins", { token });
}

export function modifyUserCoins(
  token: string,
  userId: number,
  body: ModifyCoinsRequest
): Promise<ModifyCoinsResponse> {
  return request<ModifyCoinsResponse>(`/users/${userId}/coins`, {
    method: "POST",
    token,
    json: body,
  });
}

// ---------------------------------------------------------------------
// Platforms / Sync
// ---------------------------------------------------------------------

export function getPlatforms(): Promise<PlatformsResponse> {
  return request<PlatformsResponse>("/platforms");
}

export function generateSyncCode(token: string, platform: string): Promise<SyncCodeResponse> {
  return request<SyncCodeResponse>(`/sync/${platform}`, { method: "POST", token });
}

// ---------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------

export function getPendingUsers(token: string): Promise<PendingUsersResponse> {
  return request<PendingUsersResponse>("/admin/users/pending", { token });
}

export function reviewUser(
  token: string,
  userId: number,
  body: ReviewUserRequest
): Promise<ReviewUserResponse> {
  return request<ReviewUserResponse>(`/admin/users/${userId}/review`, {
    method: "POST",
    token,
    json: body,
  });
}

export function getAdminPlatforms(token: string): Promise<PlatformsResponse> {
  return request<PlatformsResponse>("/admin/platforms", { token });
}

// ---------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export { ApiError };
