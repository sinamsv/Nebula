"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/ProtectedRoute";

export default function DashboardIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard/playground");
  }, [router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <LoadingSpinner />
    </div>
  );
}
