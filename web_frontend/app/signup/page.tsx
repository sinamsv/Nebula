"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot, Shield } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Button from "@/components/Button";
import TextField from "@/components/TextField";
import Banner from "@/components/Banner";
import { getBootstrapStatus, signup, googleOAuthStartUrl, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";

export default function SignupPage() {
  const router = useRouter();
  const { applySignupResult } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [bootstrapKey, setBootstrapKey] = useState("");
  const [bootstrapAvailable, setBootstrapAvailable] = useState(false);
  const [checkingBootstrap, setCheckingBootstrap] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    getBootstrapStatus()
      .then((res) => setBootstrapAvailable(res.bootstrap_available))
      .catch(() => setBootstrapAvailable(false))
      .finally(() => setCheckingBootstrap(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setConfirmError(null);

    if (password !== confirmPassword) {
      setConfirmError("Passwords don't match.");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await signup({
        username,
        password,
        bootstrap_key: isAdmin && bootstrapKey ? bootstrapKey : undefined,
      });
      applySignupResult(result);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-nebula-purple to-nebula-pink shadow-glow">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <span className="font-display text-lg font-semibold">Nebula</span>
        </div>

        <GlassPanel className="p-7">
          <h1 className="font-display text-xl font-semibold">Create your account</h1>
          <p className="mt-1 text-sm text-nebula-text-secondary">
            One account works across Discord, Telegram, and the web.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <TextField
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="3-32 characters: letters, numbers, underscores"
              required
              minLength={3}
              maxLength={32}
              pattern="[a-zA-Z0-9_]+"
              autoComplete="username"
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
              minLength={8}
              autoComplete="new-password"
            />
            <TextField
              label="Confirm password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              error={confirmError ?? undefined}
            />

            {!checkingBootstrap && bootstrapAvailable ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
                <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                  <input
                    type="checkbox"
                    checked={isAdmin}
                    onChange={(e) => setIsAdmin(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-white/5 accent-nebula-purple"
                  />
                  <Shield className="h-4 w-4 text-nebula-purple" />
                  I&apos;m the admin — this is the first Nebula account
                </label>
                {isAdmin ? (
                  <div className="mt-3">
                    <TextField
                      label="Admin bootstrap key"
                      value={bootstrapKey}
                      onChange={(e) => setBootstrapKey(e.target.value)}
                      placeholder="From your .env file's ADMIN_BOOTSTRAP_KEY"
                      hint="One-time key set by whoever deployed this Nebula instance."
                    />
                  </div>
                ) : null}
              </div>
            ) : null}

            {error ? <Banner variant="error">{error}</Banner> : null}

            <Button type="submit" size="lg" isLoading={isSubmitting} className="mt-1 w-full">
              Create account
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs text-nebula-text-secondary">or</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <Button
            variant="secondary"
            size="lg"
            className="w-full"
            onClick={() => {
              window.location.href = googleOAuthStartUrl();
            }}
          >
            <GoogleIcon />
            Sign up with Google
          </Button>

          <p className="mt-6 text-center text-sm text-nebula-text-secondary">
            Already have an account?{" "}
            <Link href="/login" className="text-nebula-blue hover:underline">
              Log in
            </Link>
          </p>
        </GlassPanel>
      </div>
    </main>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.63h6.46c-.28 1.5-1.13 2.78-2.4 3.63v3h3.88c2.27-2.09 3.58-5.17 3.58-8.81z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.07 7.93-2.91l-3.88-3.01c-1.08.72-2.45 1.15-4.05 1.15-3.11 0-5.75-2.1-6.69-4.92H1.3v3.09C3.26 21.3 7.31 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.31 14.31A7.2 7.2 0 014.9 12c0-.8.14-1.58.4-2.31V6.6H1.3A11.98 11.98 0 000 12c0 1.93.46 3.76 1.3 5.4l4.01-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.77c1.76 0 3.34.6 4.59 1.79l3.44-3.44C17.94 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.3 6.6l4.01 3.09C6.25 6.87 8.89 4.77 12 4.77z"
      />
    </svg>
  );
}
