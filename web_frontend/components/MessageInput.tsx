"use client";

import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { Send, Image as ImageIcon, X, Search } from "lucide-react";
import { cn } from "@/lib/utils";

const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10MB, matches backend limit

interface MessageInputProps {
  onSendText: (text: string, searchEnabled: boolean) => void;
  onSendImage: (file: File, text: string) => void;
  disabled: boolean;
}

export default function MessageInput({ onSendText, onSendImage, disabled }: MessageInputProps) {
  const [text, setText] = useState("");
  const [searchEnabled, setSearchEnabled] = useState(true);
  const [attachedImage, setAttachedImage] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setImageError("Unsupported image type. Use JPEG, PNG, GIF, or WebP.");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError("Image is too large. Max size is 10MB.");
      return;
    }

    setImageError(null);
    setAttachedImage(file);
    setImagePreviewUrl(URL.createObjectURL(file));
  }

  function removeImage() {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    setAttachedImage(null);
    setImagePreviewUrl(null);
    setImageError(null);
  }

  function handleSend() {
    const trimmed = text.trim();
    if (disabled) return;

    if (attachedImage) {
      if (!trimmed && !attachedImage) return;
      onSendImage(attachedImage, trimmed);
      removeImage();
      setText("");
      return;
    }

    if (!trimmed) return;
    onSendText(trimmed, searchEnabled);
    setText("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const canSend = !disabled && (text.trim().length > 0 || attachedImage !== null);

  return (
    <div className="border-t border-white/10 bg-nebula-bg-secondary/60 p-3 backdrop-blur-xl sm:p-4">
      {imageError ? (
        <p className="mb-2 px-1 text-xs text-red-300">{imageError}</p>
      ) : null}

      {imagePreviewUrl ? (
        <div className="mb-3 flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={imagePreviewUrl} alt="Attached preview" className="h-14 w-14 rounded-lg object-cover" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-nebula-text-secondary">{attachedImage?.name}</p>
            <p className="text-[11px] text-nebula-text-secondary/60">
              {attachedImage ? `${(attachedImage.size / 1024 / 1024).toFixed(1)} MB` : ""}
            </p>
          </div>
          <button
            onClick={removeImage}
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-nebula-text-secondary hover:bg-white/10 hover:text-red-300"
            aria-label="Remove attached image"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_IMAGE_TYPES.join(",")}
          className="hidden"
          onChange={handleFileChange}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Attach an image"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-nebula-text-secondary transition-colors hover:bg-white/10 hover:text-nebula-text disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
        >
          <ImageIcon className="h-4 w-4" />
        </button>

        <button
          onClick={() => setSearchEnabled((v) => !v)}
          disabled={disabled}
          title={searchEnabled ? "Search is ON — click to disable" : "Search is OFF — click to enable"}
          className={cn(
            "flex h-10 flex-shrink-0 items-center gap-1.5 rounded-xl border px-3 text-xs font-medium transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
            searchEnabled
              ? "border-nebula-blue/40 bg-nebula-blue/15 text-nebula-blue"
              : "border-white/10 bg-white/5 text-nebula-text-secondary hover:bg-white/10"
          )}
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search {searchEnabled ? "on" : "off"}</span>
        </button>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={attachedImage ? "Add a caption (optional)..." : "Message Nebula..."}
          className="max-h-32 min-h-[2.5rem] flex-1 resize-none rounded-xl border border-white/10 bg-white/5 px-3.5 py-2.5 text-sm text-nebula-text placeholder:text-nebula-text-secondary/50 outline-none transition-colors focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/30 disabled:opacity-50"
        />

        <button
          onClick={handleSend}
          disabled={!canSend}
          title="Send (Enter)"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nebula-purple to-nebula-pink text-white shadow-glow transition-all hover:brightness-110 disabled:opacity-40 disabled:shadow-none cursor-pointer disabled:cursor-not-allowed"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-nebula-text-secondary/50">
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
}
