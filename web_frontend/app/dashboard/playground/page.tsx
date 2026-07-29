"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import MessageBubble from "@/components/MessageBubble";
import TypingIndicator from "@/components/TypingIndicator";
import MessageInput from "@/components/MessageInput";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { useCoins } from "@/lib/CoinsContext";
import { getGreeting, getGreetingSubtitle } from "@/lib/utils";
import {
  getChats,
  createChat,
  getChatHistory,
  renameChat,
  deleteChat,
  sendMessage,
  sendImageMessage,
  ApiError,
  API_BASE_URL,
} from "@/lib/api";
import type { ChatMessage, ChatSummary, SearchMode } from "@/types/api";
import ChatHistoryPopover from "@/components/ChatHistoryPopover";

/**
 * NOTE on the redesign: this page used to own a full desktop sidebar
 * (chat list) plus a mobile drawer. Both are gone now -- primary nav
 * lives permanently in DashboardSidebar (app/dashboard/layout.tsx).
 * The per-chat list (this conversation vs. that one) is a narrower
 * concern than primary nav, so it now lives in a lightweight popover
 * triggered from this page's own header (see ChatHistoryPopover),
 * the same way Claude keeps "your chats" one level down from the
 * global nav rather than as a second permanent column.
 *
 * Layout redesign: when there's no active chat OR the active chat has
 * no messages yet, the composer is vertically centered with a greeting
 * above it (the "hero" empty state, ChatGPT/Claude-style). The moment
 * a message is sent (or an existing chat with history loads), the
 * composer animates down to its docked position at the bottom of the
 * screen and the transcript takes over the remaining space. This is a
 * pure layout/CSS transition -- no change to how chats are created,
 * fetched, or sent.
 */
export default function ChatPage() {
  const { token, user } = useAuth();
  const { refreshCoins } = useCoins();

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [systemLines, setSystemLines] = useState<string[]>([]);
  const [memoryWarning, setMemoryWarning] = useState<string | null>(null);

  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Greeting text is picked once per mount (not on every render) so it
  // doesn't change while the person is looking at the empty state.
  const [greeting] = useState(() => getGreeting(user?.username ?? null));
  const [subtitle] = useState(() => getGreetingSubtitle());

  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  const loadChats = useCallback(
    async (selectFirst: boolean) => {
      if (!token) return;
      setIsLoadingChats(true);
      try {
        const res = await getChats(token);
        setChats(res.chats);
        if (selectFirst && res.chats.length > 0 && activeChatId === null) {
          setActiveChatId(res.chats[0].chat_id);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't load your chats.");
      } finally {
        setIsLoadingChats(false);
      }
    },
    [token, activeChatId]
  );

  useEffect(() => {
    loadChats(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const loadHistory = useCallback(
    async (chatId: number) => {
      if (!token) return;
      setIsLoadingHistory(true);
      setError(null);
      setSystemLines([]);
      setMemoryWarning(null);
      try {
        const res = await getChatHistory(token, chatId);
        setMessages(res.messages);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't load this chat.");
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [token]
  );

  useEffect(() => {
    if (activeChatId !== null) {
      loadHistory(activeChatId);
    } else {
      setMessages([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChatId]);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  async function handleCreateChat() {
    if (!token) return;
    setIsCreatingChat(true);
    try {
      const chat = await createChat(token);
      setChats((prev) => [
        { chat_id: chat.chat_id, title: chat.title, created_at: chat.created_at, last_message_at: chat.last_message_at },
        ...prev,
      ]);
      setActiveChatId(chat.chat_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create a new chat.");
    } finally {
      setIsCreatingChat(false);
    }
  }

  async function handleRenameChat(chatId: number, title: string) {
    if (!token) return;
    try {
      await renameChat(token, chatId, title);
      setChats((prev) => prev.map((c) => (c.chat_id === chatId ? { ...c, title } : c)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't rename that chat.");
    }
  }

  async function handleDeleteChat(chatId: number) {
    if (!token) return;
    try {
      await deleteChat(token, chatId);
      setChats((prev) => prev.filter((c) => c.chat_id !== chatId));
      if (activeChatId === chatId) {
        setActiveChatId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete that chat.");
    }
  }

  function touchChatOrdering(chatId: number) {
    setChats((prev) => {
      const idx = prev.findIndex((c) => c.chat_id === chatId);
      if (idx === -1) return prev;
      const updated = { ...prev[idx], last_message_at: new Date().toISOString() };
      const rest = prev.filter((c) => c.chat_id !== chatId);
      return [updated, ...rest];
    });
  }

  async function ensureActiveChat(): Promise<number | null> {
    if (activeChatId !== null) return activeChatId;
    if (!token) return null;
    try {
      const chat = await createChat(token);
      setChats((prev) => [
        { chat_id: chat.chat_id, title: chat.title, created_at: chat.created_at, last_message_at: chat.last_message_at },
        ...prev,
      ]);
      setActiveChatId(chat.chat_id);
      return chat.chat_id;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start a new chat.");
      return null;
    }
  }

  async function handleSendText(text: string, searchMode: SearchMode, model?: string) {
    if (!token) return;
    setError(null);
    const chatId = await ensureActiveChat();
    if (chatId === null) return;

    const optimisticUserMessage: ChatMessage = {
      role: "user",
      content: text,
      source_platform: "web",
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [
      ...prev,
      optimisticUserMessage,
      {
        role: "assistant",
        content: "",
        source_platform: "web",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      },
    ]);
    setSystemLines([]);
    setMemoryWarning(null);
    setIsSending(true);

    try {
      const url = `${API_BASE_URL}/chat/${chatId}/messages`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          input: text,
          tools: { search: searchMode },
          model: model,
          stream: true,
        }),
      });

      if (!response.ok) {
        let detail = "Streaming request failed.";
        try {
          const body = await response.json();
          detail = body.detail || detail;
        } catch {}
        throw new Error(detail);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body stream found.");
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;

          const jsonStr = trimmed.slice(6);
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "content") {
              accumulatedText += event.content;
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                if (last && last.role === "assistant") {
                  last.content = accumulatedText;
                }
                return copy;
              });
            } else if (event.type === "tool_message") {
              setSystemLines((prev) => [...prev, event.content]);
            } else if (event.type === "error") {
              throw new Error(event.error);
            } else if (event.type === "done") {
              if (event.reply_text !== undefined && event.reply_text !== null) {
                accumulatedText = event.reply_text;
              }
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                if (last && last.role === "assistant") {
                  last.content = accumulatedText;
                  last.isStreaming = false;
                }
                return copy;
              });
              setSystemLines(event.tool_messages ?? []);
              setMemoryWarning(event.memory_warning ?? null);
            }
          } catch (e) {
            console.error("Failed to parse SSE line", trimmed, e);
          }
        }
      }

      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant") {
          last.isStreaming = false;
        }
        return copy;
      });

      touchChatOrdering(chatId);
      refreshCoins(token);
    } catch (err: any) {
      // If we errored out, remove the trailing empty message bubble and show error
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant" && !last.content) {
          return copy.slice(0, -1);
        } else if (last && last.role === "assistant") {
          last.isStreaming = false;
        }
        return copy;
      });
      setError(err instanceof Error ? err.message : "Something went wrong sending that message.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSendImage(file: File, text: string, model?: string) {
    if (!token) return;
    setError(null);
    const chatId = await ensureActiveChat();
    if (chatId === null) return;

    const optimisticUserMessage: ChatMessage = {
      role: "user",
      content: text ? `${text}\n\n[Image attached]` : "[Image attached]",
      source_platform: "web",
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMessage]);
    setSystemLines([]);
    setMemoryWarning(null);
    setIsSending(true);

    try {
      const res = await sendImageMessage(token, chatId, file, text, model);
      if (res.reply_text) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.reply_text as string,
            source_platform: "web",
            timestamp: new Date().toISOString(),
          },
        ]);
      }
      setSystemLines(res.tool_messages ?? []);
      setMemoryWarning(res.memory_warning ?? null);
      touchChatOrdering(chatId);
      refreshCoins(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong sending that image.");
    } finally {
      setIsSending(false);
    }
  }

  const inputDisabled = isSending || !user?.is_approved;
  const activeChat = chats.find((c) => c.chat_id === activeChatId) ?? null;
  const isLoading = isLoadingChats || isLoadingHistory;
  // "Empty state" = nothing to scroll through yet, so the composer
  // gets the centered hero treatment instead of docking at the bottom.
  const isEmptyState = !isLoading && messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      {/* Page-local header: chat title + the chat-switcher popover.
          This is the "one level down from global nav" pattern -- see
          the file-level note above. Hidden in the pure empty state
          (no chat selected yet) to keep that screen uncluttered,
          matching ChatGPT/Claude's blank-slate look. */}
      {activeChatId !== null || chats.length > 0 ? (
        <div className="flex flex-shrink-0 items-center justify-between border-b border-white/5 px-4 py-2.5 sm:px-6">
          <ChatHistoryPopover
            chats={chats}
            activeChat={activeChat}
            isLoading={isLoadingChats}
            isCreating={isCreatingChat}
            onSelectChat={setActiveChatId}
            onCreateChat={handleCreateChat}
            onRenameChat={handleRenameChat}
            onDeleteChat={handleDeleteChat}
          />
        </div>
      ) : null}

      {isEmptyState ? (
        // --- HERO / CENTERED STATE ------------------------------------
        <div className="flex flex-1 flex-col items-center justify-center px-4 pb-24 sm:px-6">
          <div className="w-full max-w-2xl animate-fade-in-up">
            <div className="mb-8 text-center">
              <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
                <span className="text-gradient-brand">{greeting}</span>
              </h1>
              <p className="mt-2 text-sm text-nebula-text-secondary sm:text-base">{subtitle}</p>
            </div>

            {error ? (
              <div className="mb-4">
                <Banner variant="error">{error}</Banner>
              </div>
            ) : null}

            <MessageInput onSendText={handleSendText} onSendImage={handleSendImage} disabled={inputDisabled} variant="hero" />

            {!user?.is_approved ? (
              <div className="mt-3">
                <Banner variant="info">
                  Your account is still pending admin approval — you&apos;ll be able to chat once approved.
                </Banner>
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        // --- ACTIVE CHAT / DOCKED STATE ---------------------------------
        <>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
            {isLoading ? (
              <div className="flex h-full items-center justify-center">
                <LoadingSpinner />
              </div>
            ) : (
              <div className="mx-auto flex max-w-2xl flex-col gap-6">
                {messages.map((m, i) => (
                  <MessageBubble key={i} message={m} />
                ))}
                {isSending ? <TypingIndicator /> : null}
                <div ref={scrollAnchorRef} />
              </div>
            )}
          </div>

          <div className="mx-auto w-full max-w-2xl px-4 sm:px-6">
            {error ? (
              <div className="pb-2">
                <Banner variant="error">{error}</Banner>
              </div>
            ) : null}
            {memoryWarning ? (
              <div className="pb-2">
                <Banner variant="warning">{memoryWarning}</Banner>
              </div>
            ) : null}
            {systemLines.length > 0 ? (
              <div className="flex flex-col gap-1 pb-2">
                {systemLines.map((line, i) => (
                  <p
                    key={i}
                    dir="auto"
                    className="rounded-lg border border-nebula-border bg-white/[0.03] px-3 py-1.5 text-xs text-nebula-text-secondary"
                  >
                    {line}
                  </p>
                ))}
              </div>
            ) : null}
            {!user?.is_approved ? (
              <div className="pb-3">
                <Banner variant="info">
                  Your account is still pending admin approval — you&apos;ll be able to chat once approved.
                </Banner>
              </div>
            ) : null}
          </div>

          <div className="mx-auto w-full max-w-2xl px-4 pb-4 sm:px-6 animate-fade-in-up">
            <MessageInput onSendText={handleSendText} onSendImage={handleSendImage} disabled={inputDisabled} variant="docked" />
          </div>
        </>
      )}
    </div>
  );
}
