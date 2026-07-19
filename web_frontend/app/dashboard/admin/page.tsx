"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck, Check, X, Coins } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Button from "@/components/Button";
import TextField from "@/components/TextField";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { getPendingUsers, reviewUser, modifyUserCoins, ApiError } from "@/lib/api";
import type { PendingUser } from "@/types/api";
import { formatTimestamp } from "@/lib/utils";

export default function AdminPage() {
  const { user, token } = useAuth();

  if (!user?.is_admin) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <GlassPanel className="p-8" glow="none">
          <p className="text-sm text-nebula-text-secondary">
            This page is only available to Nebula admins.
          </p>
        </GlassPanel>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="flex items-center gap-2.5">
        <ShieldCheck className="h-5 w-5 text-nebula-purple" />
        <h1 className="font-display text-2xl font-semibold">Admin</h1>
      </div>
      <p className="mt-1 text-sm text-nebula-text-secondary">
        Review pending signups and manage Nebula Coin balances.
      </p>

      <div className="mt-6 flex flex-col gap-6">
        {token ? <PendingUsersSection token={token} /> : null}
        {token ? <AddCoinsSection token={token} /> : null}
      </div>
    </div>
  );
}

function PendingUsersSection({ token }: { token: string }) {
  const [pending, setPending] = useState<PendingUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingOnId, setActingOnId] = useState<number | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getPendingUsers(token);
      setPending(res.pending);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load pending users.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleReview(userId: number, status: "approved" | "rejected") {
    setActingOnId(userId);
    setError(null);
    try {
      await reviewUser(token, userId, { status });
      setPending((prev) => prev.filter((p) => p.nebula_user_id !== userId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update that account.");
    } finally {
      setActingOnId(null);
    }
  }

  return (
    <GlassPanel className="p-5" glow="none">
      <h2 className="font-display text-sm font-semibold">Pending signups</h2>

      {error ? (
        <div className="mt-3">
          <Banner variant="error">{error}</Banner>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : pending.length === 0 ? (
        <p className="mt-3 text-sm text-nebula-text-secondary">No accounts are waiting for review.</p>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          {pending.map((p) => (
            <div
              key={p.nebula_user_id}
              className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{p.display_name}</p>
                <p className="truncate text-xs text-nebula-text-secondary">
                  @{p.username} · signed up {formatTimestamp(p.created_at)}
                </p>
              </div>
              <div className="flex flex-shrink-0 gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  isLoading={actingOnId === p.nebula_user_id}
                  onClick={() => handleReview(p.nebula_user_id, "approved")}
                >
                  <Check className="h-3.5 w-3.5 text-green-400" />
                  Approve
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  isLoading={actingOnId === p.nebula_user_id}
                  onClick={() => handleReview(p.nebula_user_id, "rejected")}
                >
                  <X className="h-3.5 w-3.5" />
                  Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </GlassPanel>
  );
}

function AddCoinsSection({ token }: { token: string }) {
  const [userId, setUserId] = useState("");
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState<"add" | "set">("add");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    const parsedUserId = Number(userId);
    const parsedAmount = Number(amount);
    if (!Number.isInteger(parsedUserId) || parsedUserId <= 0) {
      setError("Enter a valid Nebula user id (a whole number).");
      return;
    }
    if (!Number.isInteger(parsedAmount)) {
      setError("Enter a valid whole-number amount.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await modifyUserCoins(token, parsedUserId, { amount: parsedAmount, mode });
      setResult(`New balance for user #${res.nebula_user_id}: ${res.new_balance} coins.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update that user's coins.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <GlassPanel className="p-5" glow="none">
      <div className="flex items-center gap-2">
        <Coins className="h-4 w-4 text-nebula-pink" />
        <h2 className="font-display text-sm font-semibold">Add / set coins</h2>
      </div>
      <p className="mt-1 text-xs text-nebula-text-secondary">
        You&apos;ll need the target account&apos;s Nebula user id (visible to admins via other tools, e.g. Discord&apos;s
        activity check).
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <TextField
          label="Nebula user id"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="e.g. 4"
          inputMode="numeric"
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="e.g. 10"
            inputMode="numeric"
            required
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nebula-text-secondary">Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "add" | "set")}
              className="rounded-xl border border-white/10 bg-white/5 px-3.5 py-2.5 text-sm text-nebula-text outline-none focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/30"
            >
              <option value="add">Add</option>
              <option value="set">Set</option>
            </select>
          </div>
        </div>

        {error ? <Banner variant="error">{error}</Banner> : null}
        {result ? <Banner variant="info">{result}</Banner> : null}

        <Button type="submit" isLoading={isSubmitting} className="mt-1 self-start">
          Update balance
        </Button>
      </form>
    </GlassPanel>
  );
}
