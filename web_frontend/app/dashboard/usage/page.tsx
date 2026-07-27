"use client";

import { useEffect, useState } from "react";
import { Activity, ShieldCheck, Zap, Clock } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { getMyCoins, ApiError } from "@/lib/api";
import type { CoinStatusResponse } from "@/types/api";
import { formatDuration } from "@/lib/utils";

export default function UsagePage() {
  const { token } = useAuth();
  const [coins, setCoins] = useState<CoinStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getMyCoins(token)
      .then((res) => setCoins(res))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load usage details.");
      })
      .finally(() => setIsLoading(false));
  }, [token]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center min-h-[300px]">
        <LoadingSpinner label="Loading your usage data..." />
      </div>
    );
  }

  const isUnlimited =
    coins?.role === "Admin" ||
    coins?.unlimited_mode === "permanent" ||
    (coins?.unlimited_mode === "temporary" &&
      coins?.unlimited_expires_at &&
      new Date() < new Date(coins.unlimited_expires_at));

  // Limits
  const dailyLimit = coins?.daily_limit ?? 50;
  const weeklyLimit = coins?.weekly_limit ?? 200;
  const dailyUsage = coins?.daily_usage ?? 0;
  const weeklyUsage = coins?.weekly_usage ?? 0;

  // Percentage calculations
  const dailyPercent = dailyLimit > 0 ? Math.min(100, (dailyUsage / dailyLimit) * 100) : 0;
  const weeklyPercent = weeklyLimit > 0 ? Math.min(100, (weeklyUsage / weeklyLimit) * 100) : 0;

  // Reset times
  const hasResetTime = coins?.seconds_until_reset && coins.seconds_until_reset > 0;
  const resetTimeStr = hasResetTime
    ? new Date(Date.now() + (coins?.seconds_until_reset ?? 0) * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;
  const resetDateStr = hasResetTime
    ? new Date(Date.now() + (coins?.seconds_until_reset ?? 0) * 1000).toLocaleDateString([], {
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <div className="flex items-center gap-2.5">
        <Activity className="h-5 w-5 text-nebula-purple" />
        <h1 className="font-display text-2xl font-semibold">Usage Limits</h1>
      </div>
      <p className="mt-1 text-sm text-nebula-text-secondary">
        Track your daily and weekly Nebula Coin usage against your role limits.
      </p>

      {error ? (
        <div className="mt-6">
          <Banner variant="error">{error}</Banner>
        </div>
      ) : null}

      {coins ? (
        <div className="mt-6 flex flex-col gap-6">
          {/* Role Status Banner */}
          <GlassPanel className="p-5" glow="purple">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs text-nebula-text-secondary">Current Role</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <ShieldCheck className="h-4 w-4 text-nebula-purple" />
                  <span className="font-display text-lg font-semibold text-white">
                    {coins.role}
                  </span>
                </div>
              </div>

              {isUnlimited && (
                <div className="flex items-center gap-1.5 rounded-full bg-nebula-pink/15 px-3 py-1 text-xs font-semibold text-nebula-pink self-start sm:self-auto">
                  <Zap className="h-3.5 w-3.5" /> Unlimited Mode Active
                </div>
              )}
            </div>
            {coins.unlimited_expires_at && coins.unlimited_mode === "temporary" && (
              <p className="mt-3 text-xs text-nebula-text-secondary/80">
                Your temporary unlimited mode expires on:{" "}
                <span className="text-white">
                  {new Date(coins.unlimited_expires_at).toLocaleString()}
                </span>
              </p>
            )}
          </GlassPanel>

          {/* Daily limit card */}
          <GlassPanel className="p-5" glow="none">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-semibold">Daily Usage</h2>
              <span className="text-xs text-nebula-text-secondary">
                {isUnlimited ? "Unlimited" : `${dailyUsage.toFixed(2)} / ${dailyLimit.toFixed(0)} coins`}
              </span>
            </div>

            {!isUnlimited && dailyLimit > 0 ? (
              <div className="mt-3">
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-nebula-purple to-nebula-pink transition-all duration-500"
                    style={{ width: `${dailyPercent}%` }}
                  />
                </div>
                <p className="mt-2 text-right text-[11px] text-nebula-text-secondary/60">
                  {dailyPercent.toFixed(1)}% consumed
                </p>
              </div>
            ) : (
              <p className="mt-2 text-xs text-nebula-text-secondary">
                No limit applies to your daily usage.
              </p>
            )}

            <div className="mt-4 flex items-start gap-2 border-t border-white/5 pt-4 text-xs text-nebula-text-secondary">
              <Clock className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-nebula-blue" />
              <div>
                <p className="font-medium text-nebula-text">Daily Limit Reset</p>
                <div className="mt-0.5 text-[11px] leading-normal text-nebula-text-secondary/80">
                  {hasResetTime && coins.seconds_until_reset ? (
                    <>
                      Capacity is currently constrained. Next restoration begins on{" "}
                      <span className="text-white">
                        {resetDateStr} at {resetTimeStr}
                      </span>{" "}
                      (in {formatDuration(coins.seconds_until_reset)}).
                    </>
                  ) : (
                    "Daily usage is computed over a continuous rolling 24-hour window. As past transactions age out, capacity is restored dynamically."
                  )}
                </div>
              </div>
            </div>
          </GlassPanel>

          {/* Weekly limit card */}
          <GlassPanel className="p-5" glow="none">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-semibold">Weekly Usage</h2>
              <span className="text-xs text-nebula-text-secondary">
                {isUnlimited ? "Unlimited" : `${weeklyUsage.toFixed(2)} / ${weeklyLimit.toFixed(0)} coins`}
              </span>
            </div>

            {!isUnlimited && weeklyLimit > 0 ? (
              <div className="mt-3">
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-nebula-blue to-nebula-purple transition-all duration-500"
                    style={{ width: `${weeklyPercent}%` }}
                  />
                </div>
                <p className="mt-2 text-right text-[11px] text-nebula-text-secondary/60">
                  {weeklyPercent.toFixed(1)}% consumed
                </p>
              </div>
            ) : (
              <p className="mt-2 text-xs text-nebula-text-secondary">
                No limit applies to your weekly usage.
              </p>
            )}

            <div className="mt-4 flex items-start gap-2 border-t border-white/5 pt-4 text-xs text-nebula-text-secondary">
              <Clock className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-nebula-purple" />
              <div>
                <p className="font-medium text-nebula-text">Weekly Limit Reset</p>
                <p className="mt-0.5 text-[11px] leading-normal text-nebula-text-secondary/80">
                  Weekly usage is computed over a continuous rolling 7-day window. Old transactions age out individually, restoring your capacity in real-time.
                </p>
              </div>
            </div>
          </GlassPanel>
        </div>
      ) : null}
    </div>
  );
}
