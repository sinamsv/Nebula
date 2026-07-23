"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Plus, MessageSquare, Pencil, Trash2, Check, X } from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { ChatSummary } from "@/types/api";

interface ChatHistoryPopoverProps {
  chats: ChatSummary[];
  activeChat: ChatSummary | null;
  isLoading: boolean;
  isCreating: boolean;
  onSelectChat: (chatId: number) => void;
  onCreateChat: () => void;
  onRenameChat: (chatId: number, title: string) => void;
  onDeleteChat: (chatId: number) => void;
}

/**
 * Dropdown chat switcher, opened from the Playground page's own
 * header. Holds exactly the same rename/delete/create behavior the
 * old always-visible ChatSidebar had -- only the *presentation*
 * changed (popover instead of a permanent column), since primary nav
 * now owns that screen real estate (see DashboardSidebar).
 */
export default function ChatHistoryPopover({
  chats,
  activeChat,
  isLoading,
  isCreating,
  onSelectChat,
  onCreateChat,
  onRenameChat,
  onDeleteChat,
}: ChatHistoryPopoverProps) {
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
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

  function startEditing(chat: ChatSummary) {
    setEditingId(chat.chat_id);
    setEditValue(chat.title);
  }

  function commitEdit(chatId: number) {
    const trimmed = editValue.trim();
    if (trimmed) onRenameChat(chatId, trimmed);
    setEditingId(null);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium text-nebula-text transition-colors hover:bg-white/5"
      >
        <span className="max-w-[50vw] truncate sm:max-w-xs">{activeChat?.title ?? "Playground"}</span>
        <ChevronDown className={cn("h-3.5 w-3.5 text-nebula-text-secondary transition-transform", open && "rotate-180")} />
      </button>

      {open ? (
        <div className="absolute left-0 top-full z-30 mt-2 w-80 max-w-[90vw] rounded-2xl border border-white/10 bg-nebula-bg-secondary/95 p-2 shadow-glow backdrop-blur-xl animate-fade-in">
          <button
            onClick={() => {
              onCreateChat();
              setOpen(false);
            }}
            disabled={isCreating}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm font-medium text-nebula-text transition-colors hover:bg-white/10 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>

          <div className="mt-2 max-h-80 overflow-y-auto">
            {isLoading ? (
              <p className="px-2 py-4 text-center text-xs text-nebula-text-secondary">Loading…</p>
            ) : chats.length === 0 ? (
              <p className="px-2 py-4 text-center text-xs text-nebula-text-secondary">No chats yet.</p>
            ) : (
              <div className="flex flex-col gap-1">
                {chats.map((chat) => {
                  const isActive = chat.chat_id === activeChat?.chat_id;
                  const isEditing = editingId === chat.chat_id;
                  const isConfirmingDelete = confirmDeleteId === chat.chat_id;

                  return (
                    <div
                      key={chat.chat_id}
                      className={cn(
                        "group flex items-center gap-2 rounded-xl px-2.5 py-2 text-sm transition-colors",
                        isActive ? "bg-nebula-purple/15 text-nebula-text" : "text-nebula-text-secondary hover:bg-white/5"
                      )}
                    >
                      {isEditing ? (
                        <>
                          <input
                            autoFocus
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitEdit(chat.chat_id);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            className="min-w-0 flex-1 rounded-lg border border-nebula-purple/40 bg-white/5 px-2 py-1 text-sm text-nebula-text outline-none"
                          />
                          <button
                            onClick={() => commitEdit(chat.chat_id)}
                            className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-green-400 hover:bg-white/10"
                            aria-label="Save name"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-nebula-text-secondary hover:bg-white/10"
                            aria-label="Cancel"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </>
                      ) : isConfirmingDelete ? (
                        <>
                          <span className="min-w-0 flex-1 truncate text-xs">Delete &quot;{chat.title}&quot;?</span>
                          <button
                            onClick={() => {
                              onDeleteChat(chat.chat_id);
                              setConfirmDeleteId(null);
                            }}
                            className="flex-shrink-0 rounded-md bg-red-500/20 px-2 py-1 text-xs text-red-300 hover:bg-red-500/30"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="flex-shrink-0 rounded-md px-2 py-1 text-xs text-nebula-text-secondary hover:bg-white/10"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              onSelectChat(chat.chat_id);
                              setOpen(false);
                            }}
                            className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer"
                          >
                            <MessageSquare className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="min-w-0 flex-1 truncate">{chat.title}</span>
                          </button>
                          <span className="flex-shrink-0 text-[10px] text-nebula-text-secondary/50 group-hover:hidden">
                            {formatRelativeTime(chat.last_message_at)}
                          </span>
                          <button
                            onClick={() => startEditing(chat)}
                            className="hidden h-6 w-6 flex-shrink-0 items-center justify-center rounded-md hover:bg-white/10 group-hover:flex"
                            aria-label="Rename chat"
                          >
                            <Pencil className="h-3 w-3" />
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(chat.chat_id)}
                            className="hidden h-6 w-6 flex-shrink-0 items-center justify-center rounded-md hover:bg-red-500/20 hover:text-red-300 group-hover:flex"
                            aria-label="Delete chat"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
