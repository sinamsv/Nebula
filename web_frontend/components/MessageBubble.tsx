import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";
import CodeBlock from "@/components/CodeBlock";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 animate-fade-in-up", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg",
          isUser ? "bg-white/10" : "bg-gradient-to-br from-nebula-purple to-nebula-pink"
        )}
      >
        {isUser ? <User className="h-3.5 w-3.5 text-nebula-text-secondary" /> : <Bot className="h-3.5 w-3.5 text-white" />}
      </div>

      <div className={cn(isUser ? "flex max-w-[85%] flex-col gap-1 items-end" : "flex flex-1 flex-col gap-1 items-start min-w-0")}>
        <div
          className={cn(
            "text-sm leading-relaxed",
            isUser
              ? "rounded-2xl px-4 py-2.5 bg-gradient-to-br from-nebula-purple/25 to-nebula-pink/20 text-nebula-text"
              : "text-nebula-text w-full py-1"
          )}
        >
          {isUser ? (
            <p dir="auto" className="whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <div dir="auto" className="markdown-body relative">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code(props) {
                    const { className, children, ...rest } = props;
                    // react-markdown gives fenced code blocks a
                    // `language-xxx` className (from remark/rehype's
                    // standard convention) and renders them inside a
                    // <pre>; inline code has no className and no <pre>
                    // wrapper. That's the reliable signal to tell them
                    // apart -- checking for a newline in the content is
                    // NOT reliable (a fenced block can be one line).
                    const match = /language-(\w+)/.exec(className || "");
                    if (match) {
                      return <CodeBlock language={match[1]} code={String(children)} />;
                    }
                    return (
                      <code className={className} {...rest}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && (
                <span className="inline-block h-3.5 w-1.5 animate-pulse bg-current ml-1" style={{ animationDuration: '0.8s', verticalAlign: 'middle' }} />
              )}
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
