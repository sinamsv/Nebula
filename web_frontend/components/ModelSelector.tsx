"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Bot, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AvailableModelItem } from "@/types/api";
import OpenAI from "@lobehub/icons/es/OpenAI/components/Mono";
import Gemini from "@lobehub/icons/es/Gemini/components/Mono";
import Claude from "@lobehub/icons/es/Claude/components/Mono";
import Grok from "@lobehub/icons/es/Grok/components/Mono";
import Qwen from "@lobehub/icons/es/Qwen/components/Mono";
import Meta from "@lobehub/icons/es/Meta/components/Mono";
import ChatGLM from "@lobehub/icons/es/ChatGLM/components/Mono";
import DeepSeek from "@lobehub/icons/es/DeepSeek/components/Mono";
import Kimi from "@lobehub/icons/es/Kimi/components/Mono";

interface ModelSelectorProps {
  models: AvailableModelItem[];
  selectedModel: AvailableModelItem | null;
  onSelectModel: (model: AvailableModelItem) => void;
}

function getModelIcon(modelId: string) {
  const id = modelId.toLowerCase();
  if (id.includes("gemini") || id.includes("gemma")) {
    return <Gemini size={14} className="flex-shrink-0" />;
  }
  if (id.includes("gpt")) {
    return <OpenAI size={14} className="flex-shrink-0" />;
  }
  if (id.includes("claude")) {
    return <Claude size={14} className="flex-shrink-0" />;
  }
  if (id.includes("grok")) {
    return <Grok size={14} className="flex-shrink-0" />;
  }
  if (id.includes("qwen")) {
    return <Qwen size={14} className="flex-shrink-0" />;
  }
  if (id.includes("llama")) {
    return <Meta size={14} className="flex-shrink-0" />;
  }
  if (id.includes("glm")) {
    return <ChatGLM size={14} className="flex-shrink-0" />;
  }
  if (id.includes("kimi")) {
    return <Kimi size={14} className="flex-shrink-0" />;
  }
  if (id.includes("deepseek")) {
    return <DeepSeek size={14} className="flex-shrink-0" />;
  }
  return <Bot className="h-3.5 w-3.5 text-nebula-purple flex-shrink-0" />;
}

export default function ModelSelector({
  models,
  selectedModel,
  onSelectModel,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-nebula-text-secondary transition-colors hover:bg-white/[0.06] hover:text-nebula-text cursor-pointer max-w-[200px]"
      >
        {selectedModel ? getModelIcon(selectedModel.model_id) : <Bot className="h-3.5 w-3.5 text-nebula-purple" />}
        <span className="truncate">{selectedModel ? selectedModel.display_name : "Loading..."}</span>
        <ChevronDown className={cn("h-3 w-3 transition-transform flex-shrink-0", open && "rotate-180")} />
      </button>

      {open && models.length > 0 ? (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-64 rounded-xl border border-nebula-border bg-nebula-surface/95 p-1.5 shadow-glow-soft backdrop-blur-xl animate-scale-in max-h-60 overflow-y-auto">
          {models.map((m) => (
            <button
              key={m.model_id}
              onClick={() => {
                onSelectModel(m);
                setOpen(false);
              }}
              className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-nebula-text transition-colors hover:bg-white/5 cursor-pointer"
            >
              <span className="flex items-center gap-2 truncate">
                {getModelIcon(m.model_id)}
                <span className="truncate">{m.display_name}</span>
              </span>
              {selectedModel?.model_id === m.model_id && (
                <Check className="h-3.5 w-3.5 text-nebula-purple flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
