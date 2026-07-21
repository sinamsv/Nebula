"use client";

/**
 * Coin balance state, shared app-wide via React Context -- same shape
 * as lib/AuthContext.tsx.
 *
 * Why this exists: the coin balance badge lives in the dashboard's top
 * bar (DashboardLayout), but the thing that actually SPENDS a coin
 * (sending a chat message) happens inside PlaygroundPage, a totally
 * separate component several levels away in the tree. Before this,
 * DashboardLayout owned `coins` as local state with no way for
 * PlaygroundPage to trigger a refresh after a successful send -- the
 * badge only updated on a full page reload. Lifting `coins` +
 * `refreshCoins` into a context lets any component under
 * <CoinsProvider> (both the layout's badge AND the playground page)
 * read the current balance and trigger a refresh, without prop-
 * drilling a callback down through the sidebar/page-switch structure.
 *
 * This does NOT talk to the backend to push updates -- there's no
 * websocket/SSE for balance changes. It's a pull-based refresh: any
 * consumer calls refreshCoins() after an action it knows might have
 * spent a coin (right now: after every successful sendMessage /
 * sendImageMessage call in the playground), and every consumer
 * re-renders with the fresh value once the fetch resolves.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getMyCoins } from "@/lib/api";
import type { CoinStatusResponse } from "@/types/api";

interface CoinsContextValue {
  coins: CoinStatusResponse | null;
  /** Re-fetches the balance from the backend and updates every
   * consumer. Safe to call frequently -- it's a single lightweight
   * GET (see web_backend/routes/coins.py's GET /users/me/coins).
   * No-ops (does nothing, does not throw) if there's no token yet. */
  refreshCoins: (token: string | null) => Promise<void>;
}

const CoinsContext = createContext<CoinsContextValue | undefined>(undefined);

export function CoinsProvider({ children }: { children: ReactNode }) {
  const [coins, setCoins] = useState<CoinStatusResponse | null>(null);

  const refreshCoins = useCallback(async (token: string | null) => {
    if (!token) return;
    try {
      const status = await getMyCoins(token);
      setCoins(status);
    } catch {
      // Non-critical -- badge simply keeps showing the last known
      // balance (or "...") if this fails; not worth surfacing an
      // error banner for a background balance refresh.
    }
  }, []);

  const value = useMemo<CoinsContextValue>(
    () => ({ coins, refreshCoins }),
    [coins, refreshCoins]
  );

  return <CoinsContext.Provider value={value}>{children}</CoinsContext.Provider>;
}

export function useCoins(): CoinsContextValue {
  const ctx = useContext(CoinsContext);
  if (!ctx) {
    throw new Error("useCoins must be used within a CoinsProvider");
  }
  return ctx;
}
