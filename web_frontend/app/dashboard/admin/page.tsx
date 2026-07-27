"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck, Check, X, Bot } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Button from "@/components/Button";
import TextField from "@/components/TextField";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { getPendingUsers, reviewUser, lookupUserByUsername, updateUserRole, getRoleSettings, updateRoleSettings, getAdminModels, saveAdminModel, deleteAdminModel, ApiError } from "@/lib/api";
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
        {token ? <RoleManagementSection token={token} /> : null}
        {token ? <RoleSettingsSection token={token} /> : null}
        {token ? <ModelConfigurationSection token={token} /> : null}
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
              className="flex items-center justify-between gap-3 rounded-xl border border-nebula-border bg-white/[0.03] px-4 py-3"
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

function ModelConfigurationSection({ token }: { token: string }) {
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form states for adding/editing a model
  const [modelId, setModelId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [allowedRoles, setAllowedRoles] = useState<string[]>(["Member", "Trusted", "Researcher", "Admin"]);

  async function loadModels() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminModels(token);
      setModels(res.models);
    } catch (err) {
      setError("Couldn't load model configurations.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadModels();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!modelId.trim() || !displayName.trim()) {
      setError("Please fill in both Model ID and Display Name.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await saveAdminModel(token, {
        model_id: modelId.trim(),
        display_name: displayName.trim(),
        allowed_roles: allowedRoles,
      });
      // Clear form
      setModelId("");
      setDisplayName("");
      setAllowedRoles(["Member", "Trusted", "Researcher", "Admin"]);
      await loadModels();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save model configuration.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(`Are you sure you want to delete model "${id}"?`)) return;
    setError(null);
    try {
      await deleteAdminModel(token, id);
      await loadModels();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete model.");
    }
  }

  function toggleRole(role: string) {
    setAllowedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  }

  return (
    <GlassPanel className="p-5" glow="none">
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-nebula-purple" />
        <h2 className="font-display text-sm font-semibold">AI Model Configurations</h2>
      </div>
      <p className="mt-1 text-xs text-nebula-text-secondary">
        Manage AI models, display names, and role-based access.
      </p>

      {error ? (
        <div className="mt-3">
          <Banner variant="error">{error}</Banner>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 border-b border-nebula-border pb-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Model ID / string"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            placeholder="e.g. google/gemini-2.5-pro"
            required
          />
          <TextField
            label="Custom Display Name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. Gemini 2.5 Pro (High Quality)"
            required
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nebula-text-secondary">Available to Roles</label>
          <div className="flex flex-wrap gap-4 mt-1">
            {["Member", "Trusted", "Researcher", "Admin"].map((r) => (
              <label key={r} className="flex items-center gap-2 cursor-pointer text-xs font-medium">
                <input
                  type="checkbox"
                  checked={allowedRoles.includes(r)}
                  onChange={() => toggleRole(r)}
                  className="rounded border-nebula-border bg-white/[0.03] text-nebula-purple focus:ring-nebula-purple"
                />
                {r}
              </label>
            ))}
          </div>
        </div>

        <Button type="submit" isLoading={isSubmitting} className="self-start mt-1">
          Add / Update Model
        </Button>
      </form>

      <div className="mt-4">
        <h3 className="text-xs font-semibold text-nebula-text-secondary">Current Models</h3>
        {isLoading ? (
          <div className="flex justify-center py-4">
            <LoadingSpinner />
          </div>
        ) : models.length === 0 ? (
          <p className="mt-2 text-xs text-nebula-text-secondary">No models configured.</p>
        ) : (
          <div className="mt-2 flex flex-col gap-2">
            {models.map((m) => (
              <div
                key={m.model_id}
                className="flex items-center justify-between gap-3 rounded-xl border border-nebula-border bg-white/[0.01] px-3.5 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-nebula-text">{m.display_name}</p>
                  <p className="truncate font-mono text-[10px] text-nebula-text-secondary/80">
                    {m.model_id}
                  </p>
                  <p className="mt-1 text-[10px] text-nebula-text-secondary/60">
                    Roles: {m.allowed_roles.join(", ")}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setModelId(m.model_id);
                      setDisplayName(m.display_name);
                      setAllowedRoles(m.allowed_roles);
                    }}
                    className="text-xs text-nebula-purple hover:underline cursor-pointer"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(m.model_id)}
                    className="text-xs text-red-400 hover:underline cursor-pointer"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </GlassPanel>
  );
}

function RoleManagementSection({ token }: { token: string }) {
  const { user: currentAdmin } = useAuth();
  const [searchUsername, setSearchUsername] = useState("");
  const [resolvedUser, setResolvedUser] = useState<any | null>(null);

  const [role, setRole] = useState<"Member" | "Trusted" | "Researcher" | "Admin">("Member");
  const [unlimitedMode, setUnlimitedMode] = useState<"none" | "temporary" | "permanent">("none");
  const [unlimitedDuration, setUnlimitedDuration] = useState<"1 day" | "1 week" | "1 month" | "indefinite">("1 day");

  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!searchUsername.trim()) return;

    setError(null);
    setResult(null);
    setResolvedUser(null);
    setIsSearching(true);

    try {
      const user = await lookupUserByUsername(token, searchUsername.trim());
      setResolvedUser(user);
      setRole(user.role);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't find user by that username.");
    } finally {
      setIsSearching(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!resolvedUser) return;
    setError(null);
    setResult(null);

    // Self-demotion safety warning check
    if (resolvedUser.nebula_user_id === currentAdmin?.nebula_user_id && role !== "Admin") {
      const confirmed = window.confirm(
        "You are about to remove your own admin access. This cannot be undone by yourself. Are you sure?"
      );
      if (!confirmed) return;
    }

    setIsSubmitting(true);
    try {
      await updateUserRole(token, resolvedUser.nebula_user_id, {
        role,
        unlimited_mode: unlimitedMode,
        unlimited_duration: unlimitedDuration,
      });
      setResult(`Updated user @${resolvedUser.username} role to ${role}. Unlimited mode: ${unlimitedMode}.`);
      // Update local role
      setResolvedUser({ ...resolvedUser, role });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update that user's role.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <GlassPanel className="p-5" glow="none">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-nebula-purple" />
        <h2 className="font-display text-sm font-semibold">User Role & Researcher Settings</h2>
      </div>
      <p className="mt-1 text-xs text-nebula-text-secondary">
        Manage user roles. Look up the user by username instead of typing a raw ID.
      </p>

      {/* Lookup Form */}
      <form onSubmit={handleSearch} className="mt-4 flex items-end gap-3">
        <div className="flex-1">
          <TextField
            label="Search by username"
            value={searchUsername}
            onChange={(e) => setSearchUsername(e.target.value)}
            placeholder="e.g. sina"
            required
          />
        </div>
        <Button type="submit" isLoading={isSearching} className="h-[46px]">
          Lookup User
        </Button>
      </form>

      {error ? <div className="mt-3"><Banner variant="error">{error}</Banner></div> : null}
      {result ? <div className="mt-3"><Banner variant="info">{result}</Banner></div> : null}

      {resolvedUser && (
        <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3 border-t border-nebula-border pt-4">
          <div className="rounded-xl border border-nebula-border bg-white/[0.02] px-4 py-3 text-xs">
            <p className="font-semibold text-white">Target User Found:</p>
            <p className="mt-1 text-nebula-text-secondary">
              Display Name: <span className="text-white font-medium">{resolvedUser.display_name}</span>
            </p>
            <p className="text-nebula-text-secondary">
              Username: <span className="text-white font-medium">@{resolvedUser.username}</span>
            </p>
            <p className="text-nebula-text-secondary">
              Current Role: <span className="text-nebula-purple font-semibold">{resolvedUser.role}</span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-1">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-nebula-text-secondary">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as any)}
                className="rounded-xl border border-nebula-border bg-white/[0.03] px-3.5 py-2.5 text-sm text-nebula-text outline-none focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/20"
              >
                <option value="Member">Member</option>
                <option value="Trusted">Trusted</option>
                <option value="Researcher">Researcher</option>
                <option value="Admin">Admin</option>
              </select>
            </div>

            {role === "Researcher" && (
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-nebula-text-secondary">Unlimited Coins Mode</label>
                <select
                  value={unlimitedMode}
                  onChange={(e) => setUnlimitedMode(e.target.value as any)}
                  className="rounded-xl border border-nebula-border bg-white/[0.03] px-3.5 py-2.5 text-sm text-nebula-text outline-none focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/20"
                >
                  <option value="none">None (Standard Limits)</option>
                  <option value="temporary">Temporary</option>
                  <option value="permanent">Permanent</option>
                </select>
              </div>
            )}
          </div>

          {role === "Researcher" && unlimitedMode === "temporary" && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-nebula-text-secondary">Duration</label>
              <select
                value={unlimitedDuration}
                onChange={(e) => setUnlimitedDuration(e.target.value as any)}
                className="rounded-xl border border-nebula-border bg-white/[0.03] px-3.5 py-2.5 text-sm text-nebula-text outline-none focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/20"
              >
                <option value="1 day">1 Day</option>
                <option value="1 week">1 Week</option>
                <option value="1 month">1 Month</option>
                <option value="indefinite">Indefinite</option>
              </select>
            </div>
          )}

          <Button type="submit" isLoading={isSubmitting} className="mt-2 self-start">
            Update Role & Settings
          </Button>
        </form>
      )}
    </GlassPanel>
  );
}

function RoleSettingsSection({ token }: { token: string }) {
  const [settings, setSettings] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);

  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [dailyLimit, setDailyLimit] = useState("");
  const [weeklyLimit, setWeeklyLimit] = useState("");
  const [allowedModels, setAllowedModels] = useState("");
  const [allowedTools, setAllowedTools] = useState<string[]>([]);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getRoleSettings(token);
      setSettings(res.settings);
      if (res.settings.length > 0) {
        selectRole(res.settings[0]);
      }
    } catch (err) {
      setError("Couldn't load role settings.");
    } finally {
      setIsLoading(false);
    }
  }

  function selectRole(roleItem: any) {
    setSelectedRole(roleItem.role);
    setDailyLimit(String(roleItem.daily_limit));
    setWeeklyLimit(String(roleItem.weekly_limit));
    setAllowedModels(roleItem.allowed_models.join(", "));
    setAllowedTools(roleItem.allowed_tools);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUpdate(e: FormEvent) {
    e.preventDefault();
    if (!selectedRole) return;
    setError(null);
    setUpdatingRole(selectedRole);

    const parsedDaily = Number(dailyLimit);
    const parsedWeekly = Number(weeklyLimit);

    const modelsList = allowedModels.split(",").map(m => m.trim()).filter(m => m.length > 0);

    try {
      await updateRoleSettings(token, {
        role: selectedRole,
        allowed_models: modelsList,
        allowed_tools: allowedTools,
        daily_limit: parsedDaily,
        weekly_limit: parsedWeekly,
      });
      const res = await getRoleSettings(token);
      setSettings(res.settings);
      alert(`Updated settings for ${selectedRole} successfully.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update role settings.");
    } finally {
      setUpdatingRole(null);
    }
  }

  const toggleTool = (tool: string) => {
    setAllowedTools(prev =>
      prev.includes(tool) ? prev.filter(t => t !== tool) : [...prev, tool]
    );
  };

  return (
    <GlassPanel className="p-5" glow="none">
      <h2 className="font-display text-sm font-semibold">Role Rates & Permissions Settings</h2>
      <p className="mt-1 text-xs text-nebula-text-secondary">
        Configure daily/weekly coin limits, allowed AI models, and allowed tools for each role in the system hierarchy.
      </p>

      {isLoading ? (
        <div className="flex justify-center py-6">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <div className="flex gap-2 border-b border-nebula-border pb-3 overflow-x-auto">
            {settings.map((item) => (
              <button
                key={item.role}
                type="button"
                onClick={() => selectRole(item)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  selectedRole === item.role
                    ? "bg-nebula-purple text-white"
                    : "bg-white/[0.03] hover:bg-white/[0.08] text-nebula-text-secondary"
                }`}
              >
                {item.role}
              </button>
            ))}
          </div>

          {selectedRole && (
            <form onSubmit={handleUpdate} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Daily Coin Limit (-1 for unlimited)"
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(e.target.value)}
                  placeholder="e.g. 50"
                  inputMode="numeric"
                  required
                />
                <TextField
                  label="Weekly Coin Limit (-1 for unlimited)"
                  value={weeklyLimit}
                  onChange={(e) => setWeeklyLimit(e.target.value)}
                  placeholder="e.g. 200"
                  inputMode="numeric"
                  required
                />
              </div>

              <TextField
                label="Allowed Models (comma-separated)"
                value={allowedModels}
                onChange={(e) => setAllowedModels(e.target.value)}
                placeholder="e.g. google/gemini-3.1-flash-lite, google/gemini-2.5-pro"
                required
              />

              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-nebula-text-secondary">Allowed Tools</label>
                <div className="flex gap-4 mt-1">
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-medium">
                    <input
                      type="checkbox"
                      checked={allowedTools.includes("search")}
                      onChange={() => toggleTool("search")}
                      className="rounded border-nebula-border bg-white/[0.03] text-nebula-purple focus:ring-nebula-purple"
                    />
                    Web Search (search)
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-medium">
                    <input
                      type="checkbox"
                      checked={allowedTools.includes("moderation")}
                      onChange={() => toggleTool("moderation")}
                      className="rounded border-nebula-border bg-white/[0.03] text-nebula-purple focus:ring-nebula-purple"
                    />
                    Server Moderation (kick/ban)
                  </label>
                </div>
              </div>

              {error ? <Banner variant="error">{error}</Banner> : null}

              <Button type="submit" isLoading={updatingRole !== null} className="mt-1 self-start">
                Save Role Settings
              </Button>
            </form>
          )}
        </div>
      )}
    </GlassPanel>
  );
}


