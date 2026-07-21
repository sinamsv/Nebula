"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PanelLeft } from "lucide-react";
import ChatSidebar from "@/components/ChatSidebar";
import MessageBubble from "@/components/MessageBubble";
import TypingIndicator from "@/components/TypingIndicator";
import MessageInput from "@/components/MessageInput";
import Banner from "@/components/Banner";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { useCoins } from "@/lib/CoinsContext";
import {
  getChats,
  createChat,
  getChatHistory,
  renameChat,
  deleteChat,
  sendMessage,
  sendImageMessage,
  ApiError,
} from "@/lib/api";
import type { ChatMessage, ChatSummary, SearchMode } from "@/types/api";

export default function PlaygroundPage() {
  const { token, user } = useAuth();
  // refreshCoins() lives in the shared CoinsContext (see
  // lib/CoinsContext.tsx) -- calling it here after a successful send
  // is what makes the coin badge in DashboardLayout's header update
  // immediately instead of only on a full page reload.
  const { refreshCoins } = useCoins();

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [systemLines, setSystemLines] = useState<string[]>([]); // tool_messages, rendered as small system lines
  const [memoryWarning, setMemoryWarning] = useState<string | null>(null);

  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpenMobile, setSidebarOpenMobile] = useState(false);

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
      setSidebarOpenMobile(false);
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

  async function handleSendText(text: string, searchMode: SearchMode) {
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
    setMessages((prev) => [...prev, optimisticUserMessage]);
    setSystemLines([]);
    setMemoryWarning(null);
    setIsSending(true);

    try {
      const res = await sendMessage(token, chatId, text, { search: searchMode });
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
      // A message always costs a coin (and search mode "on"/"smart"
      // can additionally cost a search coin if the model actually
      // searched) -- refresh the shared balance now so the header
      // badge reflects it immediately instead of on next page load.
      refreshCoins(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong sending that message.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSendImage(file: File, text: string) {
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
      const res = await sendImageMessage(token, chatId, file, text);
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

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden w-72 flex-shrink-0 border-r border-white/5 p-3 md:block">
        <ChatSidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={setActiveChatId}
          onCreateChat={handleCreateChat}
          onRenameChat={handleRenameChat}
          onDeleteChat={handleDeleteChat}
          isCreating={isCreatingChat}
        />
      </aside>

      {/* Mobile sidebar (overlay) */}
      {sidebarOpenMobile ? (
        <div className="fixed inset-0 z-20 flex md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setSidebarOpenMobile(false)} />
          <div className="relative h-full w-72 border-r border-white/10 bg-nebula-bg-secondary p-3">
            <ChatSidebar
              chats={chats}
              activeChatId={activeChatId}
              onSelectChat={(id) => {
                setActiveChatId(id);
                setSidebarOpenMobile(false);
              }}
              onCreateChat={handleCreateChat}
              onRenameChat={handleRenameChat}
              onDeleteChat={handleDeleteChat}
              isCreating={isCreatingChat}
            />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-white/5 px-4 py-2 md:hidden">
          <button
            onClick={() => setSidebarOpenMobile(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-nebula-text-secondary hover:bg-white/5"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-nebula-text-secondary">
            {chats.find((c) => c.chat_id === activeChatId)?.title ?? "Playground"}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {isLoadingChats || isLoadingHistory ? (
            <div className="flex h-full items-center justify-center">
              <LoadingSpinner />
            </div>
          ) : activeChatId === null ? (
            <EmptyState onCreateChat={handleCreateChat} isCreating={isCreatingChat} />
          ) : messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-nebula-text-secondary">
              Say hello to start this conversation.
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
              {messages.map((m, i) => (
                <MessageBubble key={i} message={m} />
              ))}
              {isSending ? <TypingIndicator /> : null}
              <div ref={scrollAnchorRef} />
            </div>
          )}
        </div>

        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
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
                  className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-nebula-text-secondary"
                >
                  {line}
                </p>
              ))}
            </div>
          ) : null}
        </div>

        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
          {!user?.is_approved ? (
            <div className="pb-3">
              <Banner variant="info">
                Your account is still pending admin approval — you&apos;ll be able to chat once approved.
              </Banner>
            </div>
          ) : null}
        </div>

        <MessageInput onSendText={handleSendText} onSendImage={handleSendImage} disabled={inputDisabled} />
      </div>
    </div>
  );
}

function EmptyState({ onCreateChat, isCreating }: { onCreateChat: () => void; isCreating: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-nebula-purple to-nebula-pink shadow-glow">
        <span className="text-2xl">✨</span>
      </div>
      <div>
        <h2 className="font-display text-lg font-semibold">No chat selected</h2>
        <p className="mt-1 text-sm text-nebula-text-secondary">Start a new conversation with Nebula.</p>
      </div>
      <button
        onClick={onCreateChat}
        disabled={isCreating}
        className="rounded-xl bg-gradient-to-r from-nebula-purple to-nebula-pink px-5 py-2.5 text-sm font-medium text-white shadow-glow transition-all hover:brightness-110 disabled:opacity-50 cursor-pointer"
      >
        New Chat
      </button>
    </div>
  );
}
