import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface GlassPanelProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  glow?: "purple" | "pink" | "blue" | "none";
}

/** The base "glass card" surface used throughout the app: translucent
 * background, hairline border, backdrop blur, soft glow shadow. */
export default function GlassPanel({
  children,
  glow = "purple",
  className,
  ...rest
}: GlassPanelProps) {
  const glowClass =
    glow === "purple" ? "shadow-glow" : glow === "pink" ? "shadow-glow-pink" : glow === "blue" ? "shadow-glow-blue" : "";

  return (
    <div
      className={cn(
        "rounded-2xl border border-white/10 bg-nebula-bg-secondary/60 backdrop-blur-xl",
        glowClass,
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
