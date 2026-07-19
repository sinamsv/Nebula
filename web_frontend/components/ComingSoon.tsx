import type { ReactNode } from "react";
import GlassPanel from "@/components/GlassPanel";

export default function ComingSoon({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-24 text-center sm:px-6">
      <GlassPanel className="flex flex-col items-center gap-3 p-8" glow="none">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/5 text-nebula-text-secondary">
          {icon}
        </div>
        <h1 className="font-display text-lg font-semibold">{title}</h1>
        <span className="rounded-full bg-nebula-purple/15 px-3 py-1 text-xs font-medium text-nebula-purple">
          Coming soon
        </span>
        <p className="max-w-sm text-sm text-nebula-text-secondary">
          This part of the dashboard isn&apos;t built yet — check back in a future update.
        </p>
      </GlassPanel>
    </div>
  );
}
