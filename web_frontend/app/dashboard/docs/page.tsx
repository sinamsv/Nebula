import { Link2, Coins, Search, Image as ImageIcon } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-semibold">Docs</h1>
      <p className="mt-1 text-sm text-nebula-text-secondary">
        A quick guide to linking platforms and getting the most out of your Nebula Coins.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <GlassPanel className="p-5" glow="none">
          <div className="flex items-center gap-2.5">
            <Link2 className="h-4 w-4 text-nebula-purple" />
            <h2 className="font-display text-sm font-semibold">Linking a platform</h2>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-nebula-text-secondary">
            Head to the <span className="text-nebula-text">Platforms</span> tab and pick Discord or Telegram.
            You&apos;ll get a short code that&apos;s valid for a limited time. Paste the command it gives you into a
            message to the Nebula bot on that platform, and your memory and coin balance will carry over
            automatically — it&apos;s the same account, just reachable from one more place.
          </p>
        </GlassPanel>

        <GlassPanel className="p-5" glow="none">
          <div className="flex items-center gap-2.5">
            <Coins className="h-4 w-4 text-nebula-pink" />
            <h2 className="font-display text-sm font-semibold">Saving Nebula Coins</h2>
          </div>
          <ul className="mt-2 flex flex-col gap-2 text-sm leading-relaxed text-nebula-text-secondary">
            <li className="flex items-start gap-2">
              <Search className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-nebula-blue" />
              Turn off the <span className="text-nebula-text">Search</span> toggle in the message box when you
              don&apos;t need Nebula to look something up online — searches cost more coins than a plain message.
            </li>
            <li className="flex items-start gap-2">
              <ImageIcon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-nebula-purple" />
              Only attach images when you actually want Nebula to look at something — image messages cost more
              than text-only ones.
            </li>
            <li className="flex items-start gap-2">
              <Coins className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-nebula-pink" />
              Your balance resets automatically every few hours, and it&apos;s shared across every platform you use
              — no need to ration separately per platform.
            </li>
          </ul>
        </GlassPanel>
      </div>
    </div>
  );
}
