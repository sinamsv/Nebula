import { Bot } from "lucide-react";

export default function TypingIndicator() {
  return (
    <div className="flex animate-fade-in items-center gap-3">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-purple to-nebula-pink">
        <Bot className="h-4 w-4 text-white" />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-nebula-text-secondary [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-nebula-text-secondary [animation-delay:160ms]" />
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-nebula-text-secondary [animation-delay:320ms]" />
      </div>
    </div>
  );
}
