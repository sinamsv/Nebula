"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
 */
export default function PlaygroundPage() {
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
  const activeChat = chats.find((c) => c.chat_id === activeChatId) ?? null;

  return (
    <div className="flex h-full flex-col">
      {/* Page-local header: chat title + the chat-switcher popover.
          This is the "one level down from global nav" pattern -- see
          the file-level note above. */}
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

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
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
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-nebula-text-secondary"
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

      <div className="mx-auto w-full max-w-2xl px-4 pb-4 sm:px-6">
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
