import type { ReactNode } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface BannerProps {
  children: ReactNode;
  variant?: "error" | "warning" | "info";
  className?: string;
}

const variantStyles: Record<NonNullable<BannerProps["variant"]>, string> = {
  error: "border-red-500/30 bg-red-500/10 text-red-200",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  info: "border-nebula-blue/30 bg-nebula-blue/10 text-nebula-blue",
};

export default function Banner({ children, variant = "error", className }: BannerProps) {
  const Icon = variant === "info" ? Info : AlertTriangle;
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm animate-fade-in",
        variantStyles[variant],
        className
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
