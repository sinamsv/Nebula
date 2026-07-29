"use client";

/**
 * Auth state, shared app-wide via React Context. Holds the current
 * user (nebula_user_id, username, display_name, is_approved, is_admin)
 * and the JWT. `is_admin`/`is_approved` come from the login/signup
 * response bodies directly (see types/api.ts's AuthUser) -- the JWT
 * itself only carries the user id in its `sub` claim (per the
 * backend's confirmed design), so this context is the only place that
 * knows admin/approval status, not anything decoded from the token.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthUser, LoginResponse, SignupResponse } from "@/types/api";
import {
  clearStoredToken,
  getStoredToken,
  getStoredUserJson,
  setStoredToken,
  setStoredUserJson,
} from "@/lib/tokenStorage";
import { API_BASE_URL } from "@/lib/api";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  /** True until the initial localStorage read on mount completes --
   * used to avoid a flash of "logged out" UI before we've had a
   * chance to check. */
  isLoading: boolean;
  applyLoginResult: (result: LoginResponse) => void;
  applySignupResult: (result: SignupResponse) => void;
  /** Used by /oauth/complete, which only receives a bare token (no
   * user fields) from the redirect -- fetches nothing extra by
   * design (keeps that page's job to "store token, go to
   * dashboard"); the dashboard itself tolerates a null display_name
   * until other calls fill it in. */
  applyBareToken: (token: string) => void;
  logout: () => void;
  updateUser: (updatedUser: AuthUser) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = getStoredToken();
    const storedUserJson = getStoredUserJson();
    if (storedToken) {
      setToken(storedToken);
      if (storedUserJson) {
        try {
          setUser(JSON.parse(storedUserJson) as AuthUser);
        } catch {
          // Corrupt stored value -- ignore, user context stays null.
        }
      }
    }
    setIsLoading(false);
  }, []);

  const persist = useCallback((nextToken: string, nextUser: AuthUser | null) => {
    setStoredToken(nextToken);
    setToken(nextToken);
    if (nextUser) {
      setStoredUserJson(JSON.stringify(nextUser));
      setUser(nextUser);
    }
  }, []);

  const applyLoginResult = useCallback(
    (result: LoginResponse) => {
      const nextUser: AuthUser = {
        nebula_user_id: result.nebula_user_id,
        username: result.username,
        display_name: result.username,
        is_approved: result.is_approved,
        is_admin: result.is_admin,
        welcome_seen: result.welcome_seen,
      };
      persist(result.access_token, nextUser);
    },
    [persist]
  );

  const applySignupResult = useCallback(
    (result: SignupResponse) => {
      const nextUser: AuthUser = {
        nebula_user_id: result.nebula_user_id,
        username: result.username,
        display_name: result.username,
        is_approved: result.is_approved,
        // Signup response has `became_admin`, not `is_admin` --
        // became_admin is true exactly when this signup claimed the
        // bootstrap key, which is also exactly when the account is
        // an admin from this point forward.
        is_admin: result.became_admin,
        welcome_seen: result.welcome_seen,
      };
      persist(result.access_token, nextUser);
    },
    [persist]
  );

  const applyBareToken = useCallback(
    (nextToken: string) => {
      persist(nextToken, null);
    },
    [persist]
  );

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
  }, []);

  const updateUser = useCallback((nextUser: AuthUser) => {
    setStoredUserJson(JSON.stringify(nextUser));
    setUser(nextUser);
  }, []);

  useEffect(() => {
    if (!token || !user || user.is_approved) return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/status`, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          if (data.is_approved) {
            const nextUser = { ...user, is_approved: true };
            setUser(nextUser);
            setStoredUserJson(JSON.stringify(nextUser));
          }
        }
      } catch (err) {
        console.error("Failed to poll approval status", err);
      }
    }, 15000);

    return () => clearInterval(interval);
  }, [token, user]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isLoading, applyLoginResult, applySignupResult, applyBareToken, logout, updateUser }),
    [user, token, isLoading, applyLoginResult, applySignupResult, applyBareToken, logout, updateUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
