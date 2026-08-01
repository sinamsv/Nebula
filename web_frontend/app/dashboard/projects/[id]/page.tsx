"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { useCoins } from "@/lib/CoinsContext";
import {
  FolderKanban,
  Plus,
  ChevronDown,
  MessageSquare,
  Send,
  Save,
  FileText,
  FileUp,
  X,
  Check,
  AlertCircle,
  HelpCircle
} from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
  getProjectDetails,
  listProjectChats,
  createProjectChat,
  getProjectChatHistory,
  sendProjectChatMessage,
  uploadProjectAsset,
  ApiError,
  getMyCoins
} from "@/lib/api";
import type {
  ProjectDetailResponse,
  ProjectChatSummary,
  ProjectChatMessage,
  CoinStatusResponse
} from "@/types/api";
import MessageBubble from "@/components/MessageBubble";
import TypingIndicator from "@/components/TypingIndicator";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import Banner from "@/components/Banner";
import ComingSoon from "@/components/ComingSoon";
import GlassPanel from "@/components/GlassPanel";

export default function ProjectDetailPage() {
  const { token, user } = useAuth();
  const { refreshCoins } = useCoins();
  const { id: projectId } = useParams() as { id: string };
  const router = useRouter();

  // Project Details State
  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [isLoadingProject, setIsLoadingProject] = useState(true);
  const [projectError, setProjectError] = useState<string | null>(null);

  // Chats State
  const [chats, setChats] = useState<ProjectChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ProjectChatMessage[]>([]);
  const [isLoadingChats, setIsLoadingChats] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [showChatDropdown, setShowChatDropdown] = useState(false);

  // Composer Input
  const [messageText, setMessageText] = useState("");

  // Instruction Save State
  const [instructionText, setInstructionText] = useState("");
  const [isSavingInstruction, setIsSavingInstruction] = useState(false);
  const [instructionSuccess, setInstructionSuccess] = useState(false);
  const [instructionError, setInstructionError] = useState<string | null>(null);

  // File Upload State
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // User upload limits
  const [maxUploadMb, setMaxUploadMb] = useState<number>(128); // default fallback

  // Add text content modal state
  const [isTextContentModalOpen, setIsTextContentModalOpen] = useState(false);
  const [textContentName, setTextContentName] = useState("");
  const [textContentBody, setTextContentBody] = useState("");
  const [isSavingTextContent, setIsSavingTextContent] = useState(false);
  const [textContentError, setTextContentError] = useState<string | null>(null);

  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load project details
  const loadProject = useCallback(async () => {
    if (!token || !projectId) return;
    setIsLoadingProject(true);
    setProjectError(null);
    try {
      const res = await getProjectDetails(token, projectId);
      setProject(res);
      setInstructionText(res.instruction);
    } catch (err) {
      setProjectError(err instanceof ApiError ? err.message : "Failed to load project details.");
    } finally {
      setIsLoadingProject(false);
    }
  }, [token, projectId]);

  // Load chats
  const loadChats = useCallback(async () => {
    if (!token || !projectId) return;
    setIsLoadingChats(true);
    try {
      const res = await listProjectChats(token, projectId);
      setChats(res.chats);
      if (res.chats.length > 0 && !activeChatId) {
        setActiveChatId(res.chats[0].chat_id);
      }
    } catch (err) {
      setChatError("Failed to load project chats.");
    } finally {
      setIsLoadingChats(false);
    }
  }, [token, projectId, activeChatId]);

  // Load active chat history
  const loadHistory = useCallback(async (chatId: string) => {
    if (!token || !projectId) return;
    setIsLoadingHistory(true);
    setChatError(null);
    try {
      const res = await getProjectChatHistory(token, projectId, chatId);
      // Map ProjectChatMessage to ChatMessage compatible format for rendering
      setMessages(res.messages);
    } catch (err) {
      setChatError("Failed to load conversation history.");
    } finally {
      setIsLoadingHistory(false);
    }
  }, [token, projectId]);

  // Fetch coins and role limits to resolve max_upload_mb
  useEffect(() => {
    if (!token) return;
    getMyCoins(token)
      .then((res: CoinStatusResponse) => {
        // Resolve limits based on current role
        const role = res.role || "Member";
        const defaults: Record<string, number> = {
          Member: 128,
          Trusted: 256,
          Researcher: 512,
          Admin: 512
        };
        setMaxUploadMb(defaults[role] ?? 128);
      })
      .catch(() => {
        // Fallback to 128MB
        setMaxUploadMb(128);
      });
  }, [token]);

  useEffect(() => {
    loadProject();
    loadChats();
  }, [loadProject, loadChats]);

  useEffect(() => {
    if (activeChatId) {
      loadHistory(activeChatId);
    } else {
      setMessages([]);
    }
  }, [activeChatId, loadHistory]);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // Click outside dropdown
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowChatDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handlers
  const handleCreateChat = async () => {
    if (!token || !projectId) return;
    setIsCreatingChat(true);
    setChatError(null);
    try {
      const chat = await createProjectChat(token, projectId);
      setChats(prev => [chat, ...prev]);
      setActiveChatId(chat.chat_id);
      setShowChatDropdown(false);
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Couldn't start a new chat.");
    } finally {
      setIsCreatingChat(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = messageText.trim();
    if (!trimmed || !token || !projectId || isSending) return;

    let chatId = activeChatId;
    if (!chatId) {
      // Optimistically start a new chat if none exists
      setIsSending(true);
      try {
        const chat = await createProjectChat(token, projectId);
        setChats(prev => [chat, ...prev]);
        setActiveChatId(chat.chat_id);
        chatId = chat.chat_id;
      } catch (err) {
        setChatError(err instanceof ApiError ? err.message : "Failed to start a new chat.");
        setIsSending(false);
        return;
      }
    }

    const optimisticUserMessage: ProjectChatMessage = {
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, optimisticUserMessage]);
    setMessageText("");
    setIsSending(true);
    setChatError(null);

    try {
      const res = await sendProjectChatMessage(token, projectId, chatId, trimmed);
      if (res.reply_text) {
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: res.reply_text as string,
            timestamp: new Date().toISOString()
          }
        ]);
      }
      refreshCoins(token);
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Failed to get reply from assistant.");
    } finally {
      setIsSending(false);
    }
  };

  const handleSaveInstruction = async () => {
    if (!token || !projectId) return;
    setIsSavingInstruction(true);
    setInstructionError(null);
    setInstructionSuccess(false);
    try {
      await uploadProjectAsset(token, projectId, { instruction: instructionText });
      setInstructionSuccess(true);
      setTimeout(() => setInstructionSuccess(false), 2000);
    } catch (err) {
      setInstructionError(err instanceof ApiError ? err.message : "Failed to save instructions.");
    } finally {
      setIsSavingInstruction(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!token || !projectId) return;

    // Client-side limit check (Fast UX)
    const fileLimitBytes = maxUploadMb * 1024 * 1024;
    if (file.size > fileLimitBytes) {
      setFileError(`File "${file.name}" exceeds the maximum limit of ${maxUploadMb}MB for your role.`);
      return;
    }

    setIsUploadingFile(true);
    setFileError(null);
    try {
      await uploadProjectAsset(token, projectId, { file });
      // Reload details to update file list
      const res = await getProjectDetails(token, projectId);
      setProject(res);
    } catch (err) {
      setFileError(err instanceof ApiError ? err.message : `Failed to upload "${file.name}".`);
    } finally {
      setIsUploadingFile(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleSaveTextContent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !projectId) return;
    const trimmedName = textContentName.trim();
    const trimmedBody = textContentBody.trim();

    if (!trimmedName) {
      setTextContentError("Filename is required.");
      return;
    }
    if (!trimmedBody) {
      setTextContentError("Content cannot be empty.");
      return;
    }

    // Ensure it ends with .txt
    const filename = trimmedName.toLowerCase().endsWith(".txt") ? trimmedName : `${trimmedName}.txt`;

    setIsSavingTextContent(true);
    setTextContentError(null);

    try {
      const blob = new Blob([trimmedBody], { type: "text/plain" });
      const file = new File([blob], filename, { type: "text/plain" });

      // Check size client-side
      const fileLimitBytes = maxUploadMb * 1024 * 1024;
      if (file.size > fileLimitBytes) {
        setTextContentError(`Content exceeds the maximum limit of ${maxUploadMb}MB for your role.`);
        setIsSavingTextContent(false);
        return;
      }

      await uploadProjectAsset(token, projectId, { file });
      setIsTextContentModalOpen(false);
      setTextContentName("");
      setTextContentBody("");

      // Reload details to update file list
      const res = await getProjectDetails(token, projectId);
      setProject(res);
    } catch (err) {
      setTextContentError(err instanceof ApiError ? err.message : "Failed to add text content.");
    } finally {
      setIsSavingTextContent(false);
    }
  };

  if (isLoadingProject) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <Banner variant="error">{projectError || "Project not found."}</Banner>
        <button
          onClick={() => router.push("/dashboard/projects")}
          className="mt-4 px-4 py-2 text-sm bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 text-nebula-text transition-all cursor-pointer font-medium"
        >
          Back to Projects
        </button>
      </div>
    );
  }

  const activeChat = chats.find(c => c.chat_id === activeChatId) ?? null;

  return (
    <div className="flex h-full flex-col lg:flex-row min-h-0 bg-nebula-bg">
      {/* Left Pane: Custom Chat Area (Full height) */}
      <div className="flex flex-1 flex-col min-h-0 border-r border-white/5">
        {/* Chat Header Row */}
        <div className="flex flex-shrink-0 items-center justify-between border-b border-white/5 px-4 py-3 sm:px-6 bg-nebula-bg-secondary/20">
          <div ref={dropdownRef} className="relative">
            <button
              onClick={() => setShowChatDropdown(v => !v)}
              className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium text-nebula-text transition-colors hover:bg-white/5 cursor-pointer"
            >
              <MessageSquare className="h-4 w-4 text-nebula-purple" />
              <span className="max-w-[150px] sm:max-w-xs truncate">{activeChat?.title ?? "Project Chat"}</span>
              <ChevronDown className={cn("h-3.5 w-3.5 text-nebula-text-secondary transition-transform", showChatDropdown && "rotate-180")} />
            </button>

            {showChatDropdown && (
              <div className="absolute left-0 top-full z-30 mt-1 w-72 bg-nebula-surface border border-white/10 rounded-xl p-1.5 shadow-xl animate-scale-in">
                <button
                  onClick={handleCreateChat}
                  disabled={isCreatingChat}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-nebula-border bg-white/5 px-3 py-2 text-xs font-semibold text-nebula-text transition-colors hover:bg-white/10 disabled:opacity-50 cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>New Conversation</span>
                </button>
                <div className="h-px bg-white/5 my-1.5" />
                <div className="max-h-60 overflow-y-auto flex flex-col gap-1">
                  {isLoadingChats ? (
                    <p className="text-center text-xs text-nebula-text-secondary py-2">Loading...</p>
                  ) : chats.length === 0 ? (
                    <p className="text-center text-xs text-nebula-text-secondary py-2">No conversations yet.</p>
                  ) : (
                    chats.map(c => (
                      <button
                        key={c.chat_id}
                        onClick={() => {
                          setActiveChatId(c.chat_id);
                          setShowChatDropdown(false);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between px-2.5 py-2 text-left rounded-lg text-xs transition-colors",
                          c.chat_id === activeChatId ? "bg-nebula-purple/15 text-nebula-text" : "text-nebula-text-secondary hover:bg-white/5"
                        )}
                      >
                        <span className="truncate max-w-[180px]">{c.title}</span>
                        <span className="text-[10px] text-nebula-text-tertiary select-none">{formatRelativeTime(c.last_message_at)}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Chat Transcript */}
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {isLoadingHistory ? (
            <div className="flex h-full items-center justify-center">
              <LoadingSpinner />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-nebula-purple to-nebula-pink mb-3 shadow-glow-soft">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-base font-medium text-nebula-text">Conversation Scoped to {project.name}</h3>
              <p className="text-xs text-nebula-text-secondary max-w-sm mt-1 px-4">
                Send a message to start chatting! Nebula will answer with context from your project's custom instructions and uploaded knowledge files.
              </p>
            </div>
          ) : (
            <div className="mx-auto flex max-w-2xl flex-col gap-6">
              {messages.map((m, i) => (
                <MessageBubble
                  key={i}
                  message={{
                    role: m.role,
                    content: m.content,
                    source_platform: "web",
                    timestamp: m.timestamp
                  }}
                />
              ))}
              {isSending ? <TypingIndicator /> : null}
              <div ref={scrollAnchorRef} />
            </div>
          )}
        </div>

        {/* Chat Input Composer */}
        <div className="flex-shrink-0 px-4 pb-4 sm:px-6">
          {chatError && (
            <div className="mx-auto max-w-2xl pb-2">
              <Banner variant="error">{chatError}</Banner>
            </div>
          )}
          <form onSubmit={handleSendMessage} className="mx-auto max-w-2xl">
            <div className="relative rounded-2xl border border-nebula-border bg-nebula-surface/75 p-2 focus-within:border-nebula-purple/40 backdrop-blur-md shadow-sm">
              <input
                type="text"
                disabled={isSending}
                value={messageText}
                onChange={e => setMessageText(e.target.value)}
                placeholder="Ask Nebula about this project..."
                className="w-full bg-transparent px-3 py-2.5 text-sm text-nebula-text placeholder:text-nebula-text-secondary/50 outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isSending || !messageText.trim()}
                title="Send Message"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-nebula-purple to-nebula-pink text-white transition-all hover:brightness-110 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
            <p className="mt-2 text-center text-[10px] text-nebula-text-tertiary select-none">
              Project chats are saved as local JSON on disk, isolated from global account history.
            </p>
          </form>
        </div>
      </div>

      {/* Right Pane: Workspace Panels (Scrollable sidebar) */}
      <div className="w-full lg:w-96 flex-shrink-0 flex flex-col min-h-0 bg-nebula-bg-secondary/10 overflow-y-auto p-4 sm:p-6 gap-6">
        {/* Project Header Info */}
        <div className="flex flex-col gap-1.5 pb-4 border-b border-white/5 select-none">
          <div className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5 text-nebula-purple" />
            <h2 className="text-xl font-bold font-display text-nebula-text leading-tight">{project.name}</h2>
          </div>
          <p className="text-xs text-nebula-text-secondary">{project.description || "No description provided."}</p>
        </div>

        {/* 1. Custom Instruction Section */}
        <GlassPanel className="flex flex-col p-4 sm:p-5 gap-3" glow="none">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-nebula-text-secondary">Custom Instructions</h3>
            <button
              onClick={handleSaveInstruction}
              disabled={isSavingInstruction}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white/5 border border-white/10 rounded-lg text-nebula-text hover:bg-white/10 disabled:opacity-50 transition-all font-semibold cursor-pointer"
            >
              {isSavingInstruction ? (
                <LoadingSpinner />
              ) : instructionSuccess ? (
                <Check className="h-3.5 w-3.5 text-green-400" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              <span>{instructionSuccess ? "Saved" : "Save"}</span>
            </button>
          </div>

          {instructionError && <Banner variant="error">{instructionError}</Banner>}

          <p className="text-[10px] leading-relaxed text-nebula-text-tertiary p-2 rounded-lg border border-nebula-border bg-white/[0.01]">
            💡 Instructions provide supplementary guidance and are combined with Nebula's core system prompt to bias behavior for this project's turns.
          </p>

          <textarea
            value={instructionText}
            onChange={e => setInstructionText(e.target.value)}
            placeholder="e.g. You are a Senior Rust Engineer. Be extremely precise, use code snippets frequently, and prefer clean functional paradigms."
            rows={5}
            className="px-3.5 py-2 text-xs bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full resize-y font-mono leading-relaxed"
          />
        </GlassPanel>

        {/* 2. Knowledge Files Section */}
        <GlassPanel className="flex flex-col p-4 sm:p-5 gap-4" glow="none">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-nebula-text-secondary">Knowledge Base Files</h3>
            <button
              onClick={() => setIsTextContentModalOpen(true)}
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] border border-white/10 bg-white/5 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
            >
              <Plus className="h-3 w-3" />
              <span>Add text</span>
            </button>
          </div>

          {fileError && <Banner variant="error">{fileError}</Banner>}

          {/* Drag & Drop File Zone */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={cn(
              "flex flex-col items-center justify-center p-4 border border-dashed rounded-xl transition-all text-center",
              dragActive
                ? "border-nebula-purple bg-nebula-purple/5"
                : "border-white/10 bg-white/[0.01] hover:border-white/20 hover:bg-white/[0.02]"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              className="hidden"
            />
            {isUploadingFile ? (
              <div className="flex flex-col items-center py-2 gap-2">
                <LoadingSpinner />
                <span className="text-[11px] text-nebula-text-secondary">Uploading asset...</span>
              </div>
            ) : (
              <>
                <FileUp className="h-6 w-6 text-nebula-text-tertiary mb-1" />
                <p className="text-[11px] text-nebula-text-secondary">
                  Drag file here or{" "}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="text-nebula-purple hover:underline font-semibold cursor-pointer"
                  >
                    Browse
                  </button>
                </p>
                <p className="text-[10px] text-nebula-text-tertiary mt-1">
                  Max file size: <span className="font-semibold">{maxUploadMb}MB</span>
                </p>
              </>
            )}
          </div>

          {/* Files List */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-nebula-text-tertiary uppercase tracking-wider px-1">Uploaded Contexts</span>
            {project.files.length === 0 ? (
              <p className="text-[11px] text-nebula-text-secondary/50 text-center py-4 rounded-xl border border-white/5 bg-white/[0.005]">
                No files uploaded.
              </p>
            ) : (
              <div className="flex flex-col gap-1">
                {project.files.map((file, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/5 hover:border-white/10 rounded-xl text-xs text-nebula-text transition-colors select-none"
                  >
                    <FileText className="h-3.5 w-3.5 text-nebula-text-secondary flex-shrink-0" />
                    <span className="min-w-0 flex-1 truncate text-nebula-text-secondary">{file}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </GlassPanel>

        {/* 3. Project Memory Section (Intentional Stub) */}
        <div className="flex flex-col gap-1.5 select-none">
          <span className="text-[10px] font-bold text-nebula-text-secondary uppercase tracking-wider px-1">Statistics</span>
          <ComingSoon
            icon={<HelpCircle className="h-5 w-5 text-nebula-text-secondary" />}
            title="Project Memory"
          />
        </div>
      </div>

      {/* Add Text Content Modal */}
      {isTextContentModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-nebula-surface border border-white/10 rounded-2xl p-6 shadow-glow-soft animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold font-display text-nebula-text">Add Text Content</h2>
              <button
                onClick={() => setIsTextContentModalOpen(false)}
                className="p-1.5 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-lg cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {textContentError && (
              <div className="mb-4">
                <Banner variant="error">{textContentError}</Banner>
              </div>
            )}

            <form onSubmit={handleSaveTextContent} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">File Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. database-schema (automatically gains .txt)"
                  value={textContentName}
                  onChange={(e) => setTextContentName(e.target.value)}
                  className="px-3.5 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">Text Content</label>
                <textarea
                  placeholder="Paste or write text content to supply as workspace context..."
                  value={textContentBody}
                  onChange={(e) => setTextContentBody(e.target.value)}
                  rows={8}
                  className="px-3.5 py-2 text-xs font-mono leading-relaxed bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setIsTextContentModalOpen(false)}
                  className="px-4 py-2 text-sm text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingTextContent}
                  className="px-4 py-2 text-sm bg-gradient-to-r from-nebula-purple to-nebula-pink text-white rounded-xl hover:opacity-90 font-medium disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                >
                  {isSavingTextContent ? <LoadingSpinner /> : null}
                  <span>Add context</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
