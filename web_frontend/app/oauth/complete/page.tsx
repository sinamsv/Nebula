"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";

function OAuthCompleteInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { applyBareToken } = useAuth();

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      applyBareToken(token);
      router.replace("/dashboard");
    } else {
      // No token in the redirect -- something went wrong upstream in
      // the OAuth flow. Send back to login rather than stranding the
      // user on a blank page.
      router.replace("/login");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <LoadingSpinner label="Finishing sign-in with Google..." />
    </main>
  );
}

export default function OAuthCompletePage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center px-6">
          <LoadingSpinner label="Finishing sign-in..." />
        </main>
      }
    >
      <OAuthCompleteInner />
    </Suspense>
  );
}
