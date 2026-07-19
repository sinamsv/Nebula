"use client";

import { useEffect, useState } from "react";
import { Copy, Check, MessageCircle, Send as SendIcon, Radio } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Button from "@/components/Button";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { getPlatforms, generateSyncCode, ApiError } from "@/lib/api";
import type { PlatformInfo, SyncCodeResponse } from "@/types/api";
import { cn } from "@/lib/utils";

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  discord: <MessageCircle className="h-5 w-5" />,
  telegram: <SendIcon className="h-5 w-5" />,
};

export default function PlatformsPage() {
  const { token } = useAuth();
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncCodeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getPlatforms()
      .then((res) => setPlatforms(res.platforms))
      .catch(() => setError("Couldn't load the list of platforms."))
      .finally(() => setIsLoading(false));
  }, []);

  async function handleGenerate(platformId: string) {
    if (!token) return;
    setSelected(platformId);
    setSyncResult(null);
    setError(null);
    setIsGenerating(true);
    try {
      const res = await generateSyncCode(token, platformId);
      setSyncResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't generate a sync code.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleCopy() {
    if (!syncResult) return;
    try {
      await navigator.clipboard.writeText(syncResult.verify_command_hint);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable (e.g. insecure context) -- the text
      // is still visible on screen for the user to select manually.
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-semibold">Platforms</h1>
      <p className="mt-1 text-sm text-nebula-text-secondary">
        Link Discord or Telegram to this Nebula account — your memory and coin balance carry over.
      </p>

      {isLoading ? (
        <div className="flex justify-center py-10">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {platforms.map((p) => (
            <button
              key={p.id}
              onClick={() => handleGenerate(p.id)}
              disabled={isGenerating}
              className={cn(
                "flex items-center gap-3 rounded-2xl border p-4 text-left transition-colors cursor-pointer disabled:cursor-not-allowed",
                selected === p.id
                  ? "border-nebula-purple/50 bg-nebula-purple/10"
                  : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              )}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-nebula-purple">
                {PLATFORM_ICONS[p.id] ?? <Radio className="h-5 w-5" />}
              </div>
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-nebula-text-secondary">Generate a linking code</p>
              </div>
            </button>
          ))}
        </div>
      )}

      {error ? (
        <div className="mt-4">
          <Banner variant="error">{error}</Banner>
        </div>
      ) : null}

      {isGenerating ? (
        <div className="mt-6 flex justify-center">
          <LoadingSpinner label="Generating your code..." />
        </div>
      ) : null}

      {syncResult ? (
        <GlassPanel className="mt-6 p-5" glow="blue">
          <p className="text-sm text-nebula-text-secondary">
            Paste this into a message to the Nebula bot on{" "}
            <span className="font-medium text-nebula-text capitalize">{syncResult.target_platform}</span> to link
            your account:
          </p>
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-white/10 bg-black/30 p-3">
            <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-sm text-nebula-blue">
              {syncResult.verify_command_hint}
            </code>
            <Button variant="secondary" size="sm" onClick={handleCopy}>
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="mt-3 text-xs text-nebula-text-secondary">
            This code expires in {syncResult.expiry_minutes} minutes and can only be used once. If you haven&apos;t
            messaged the bot before, send it <code className="text-nebula-text">/start</code> first.
          </p>
        </GlassPanel>
      ) : null}
    </div>
  );
}
