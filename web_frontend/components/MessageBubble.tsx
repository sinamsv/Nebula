import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 animate-fade-in", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg",
          isUser ? "bg-white/10" : "bg-gradient-to-br from-nebula-purple to-nebula-pink"
        )}
      >
        {isUser ? <User className="h-3.5 w-3.5 text-nebula-text-secondary" /> : <Bot className="h-3.5 w-3.5 text-white" />}
      </div>

      <div className={cn("flex max-w-[85%] flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-gradient-to-br from-nebula-purple/25 to-nebula-pink/20 text-nebula-text"
              : "border border-white/10 bg-white/[0.04] text-nebula-text"
          )}
        >
          {isUser ? (
            <p dir="auto" className="whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <div dir="auto" className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
        <span className="px-1 text-[11px] text-nebula-text-secondary/60">
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
