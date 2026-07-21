/**
 * TypeScript types mirroring every request/response shape in the
 * Nebula backend's confirmed API surface (see web_backend/schemas/*.py
 * on the backend). Kept in one place so every component/lib file
 * imports from here instead of re-declaring shapes ad hoc.
 */

// ---------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------

export interface SignupRequest {
  username: string;
  password: string;
  display_name?: string;
  bootstrap_key?: string;
}

export interface SignupResponse {
  nebula_user_id: number;
  username: string;
  is_approved: boolean;
  became_admin: boolean;
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  nebula_user_id: number;
  username: string;
  is_approved: boolean;
  is_admin: boolean;
  access_token: string;
  token_type: string;
}

export interface BootstrapStatusResponse {
  bootstrap_available: boolean;
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------

export interface ChatSummary {
  chat_id: number;
  title: string;
  created_at: string;
  last_message_at: string;
}

export interface ChatListResponse {
  chats: ChatSummary[];
}

export interface ChatMessage {
  role: "user" | "assistant" | string;
  content: string;
  source_platform: string;
  timestamp: string;
}

export interface ChatHistoryResponse {
  chat_id: number;
  title: string;
  messages: ChatMessage[];
}

/** Mirrors the backend's ToolToggles.search Literal type
 * (web_backend/schemas/chat.py) -- "off" never offers the search
 * tool, "smart" (default) lets the model decide for itself, "on"
 * biases the model toward actually searching when the message
 * plausibly needs it (see ai/handler.py's _SEARCH_ON_INSTRUCTION). */
export type SearchMode = "on" | "off" | "smart";

export interface ToolToggles {
  search: SearchMode;
}

export interface SendMessageRequest {
  input: string;
  tools?: ToolToggles;
}

export interface MemoryUsage {
  total_tokens: number;
  max_tokens: number;
  percentage: number;
  remaining: number;
  is_full: boolean;
}

export interface SendMessageResponse {
  reply_text: string | null;
  tool_messages: string[];
  memory_warning: string | null;
  usage: MemoryUsage;
}

// ---------------------------------------------------------------------
// Coins
// ---------------------------------------------------------------------

export interface CoinStatusResponse {
  balance: number;
  seconds_until_reset: number;
}

export interface ModifyCoinsRequest {
  amount: number;
  mode: "add" | "set";
}

export interface ModifyCoinsResponse {
  nebula_user_id: number;
  new_balance: number;
}

// ---------------------------------------------------------------------
// Platforms / Sync
// ---------------------------------------------------------------------

export interface PlatformInfo {
  id: string;
  name: string;
  supports_guild_moderation: boolean;
}

export interface PlatformsResponse {
  platforms: PlatformInfo[];
}

export interface SyncCodeResponse {
  code: string;
  target_platform: string;
  expiry_minutes: number;
  verify_command_hint: string;
}

// ---------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------

export interface PendingUser {
  nebula_user_id: number;
  username: string;
  display_name: string;
  created_at: string;
}

export interface PendingUsersResponse {
  pending: PendingUser[];
}

export interface ReviewUserRequest {
  status: "approved" | "rejected";
}

export interface ReviewUserResponse {
  nebula_user_id: number;
  username: string;
  approved: boolean;
}

// ---------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  ai_configured: boolean;
}

// ---------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------

/** Shape of every backend error body: {"detail": "..."} */
export interface ApiErrorBody {
  detail?: string;
}

/** Thrown by lib/api.ts on any non-2xx response. Carries the HTTP
 * status and the backend's own `detail` message so callers can show
 * it directly (per the spec: backend detail strings are already
 * user-facing and friendly). */
export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------
// Local auth state shape (not a backend type, but shared across the app)
// ---------------------------------------------------------------------

export interface AuthUser {
  nebula_user_id: number;
  username: string;
  display_name: string;
  is_approved: boolean;
  is_admin: boolean;
}
