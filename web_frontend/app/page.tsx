import Link from "next/link";
import { Bot, MessageCircle, Send, Globe, Github, ArrowRight } from "lucide-react";
import GlassPanel from "@/components/GlassPanel";
import Button from "@/components/Button";

export default function LandingPage() {
  return (
    <main className="relative mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 sm:px-10">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-nebula-purple to-nebula-pink shadow-glow">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <span className="font-display text-lg font-semibold tracking-tight">Nebula</span>
        </div>
        <nav className="flex items-center gap-2">
          <a
            href="https://github.com/sinamsv/Nebula"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-nebula-text-secondary transition-colors hover:text-nebula-text"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Log in
            </Button>
          </Link>
        </nav>
      </header>

      <section className="flex flex-1 flex-col items-start justify-center gap-6 py-20">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-nebula-text-secondary">
          Open source · Discord · Telegram · Web
        </span>
        <h1 className="max-w-2xl font-display text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
          Your AI,{" "}
          <span className="bg-gradient-to-r from-nebula-pink via-nebula-purple to-nebula-blue bg-clip-text text-transparent">
            everywhere
          </span>{" "}
          you already are.
        </h1>
        <p className="max-w-xl text-base text-nebula-text-secondary sm:text-lg">
          Nebula is an open-source AI assistant that follows you across platforms.
          One account, one memory, one coin balance — whether you talk to it on
          Discord, Telegram, or right here on the web.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Link href="/signup">
            <Button size="lg">
              Sign Up <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg">
              Log In
            </Button>
          </Link>
        </div>
        <p className="text-xs text-nebula-text-secondary">
          New accounts wait for admin approval before they can chat with Nebula.
        </p>
      </section>

      <section className="grid grid-cols-1 gap-4 pb-20 sm:grid-cols-3">
        <PlatformCard
          icon={<MessageCircle className="h-5 w-5 text-nebula-purple" />}
          title="Discord"
          description="Mention the bot in a server, or DM it directly — no mention needed there."
        />
        <PlatformCard
          icon={<Send className="h-5 w-5 text-nebula-blue" />}
          title="Telegram"
          description="Message it privately, or @mention it in a group chat."
        />
        <PlatformCard
          icon={<Globe className="h-5 w-5 text-nebula-pink" />}
          title="Web"
          description="Sign in here for multi-chat, image uploads, and the full dashboard."
        />
      </section>

      <footer className="flex items-center justify-between border-t border-white/5 py-6 text-xs text-nebula-text-secondary">
        <span>Nebula is open source, MIT licensed.</span>
        <a
          href="https://github.com/sinamsv/Nebula"
          target="_blank"
          rel="noreferrer"
          className="hover:text-nebula-text"
        >
          github.com/sinamsv/Nebula
        </a>
      </footer>
    </main>
  );
}

function PlatformCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <GlassPanel className="flex flex-col gap-3 p-5" glow="none">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/5">{icon}</div>
      <h3 className="font-display text-sm font-semibold">{title}</h3>
      <p className="text-sm text-nebula-text-secondary">{description}</p>
    </GlassPanel>
  );
}
