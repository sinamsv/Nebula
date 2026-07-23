"use client";

import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { Send, Image as ImageIcon, X } from "lucide-react";
import { cn } from "@/lib/utils";
import SearchModeButton from "@/components/SearchModeButton";
import type { SearchMode } from "@/types/api";

const ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp"
];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10MB, matches backend limit

interface MessageInputProps {
    onSendText: (text: string, searchMode: SearchMode) => void;
    onSendImage: (file: File, text: string) => void;
    disabled: boolean;
}

/**
 * Redesign note: the composer is now one continuous rounded "capsule"
 * (rounded-3xl) with the toolbar (image attach + search mode) sitting
 * INSIDE it on its own row, above the text input row -- this is the
 * Claude/ChatGPT composer shape. Previously every control (attach
 * button, search toggle, textarea, send button) was a separate
 * same-height pill sitting in a single horizontal row, which reads
 * more like a form toolbar than a chat composer.
 */
export default function MessageInput({
    onSendText,
    onSendImage,
    disabled
}: MessageInputProps) {
    const [text, setText] = useState("");
    const [searchMode, setSearchMode] = useState<SearchMode>("smart");
    const [attachedImage, setAttachedImage] = useState<File | null>(null);
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const [imageError, setImageError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        e.target.value = "";
        if (!file) return;

        if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
            setImageError(
                "Unsupported image type. Use JPEG, PNG, GIF, or WebP."
            );
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
        onSendText(trimmed, searchMode);
        setText("");
    }

    function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    const canSend =
        !disabled && (text.trim().length > 0 || attachedImage !== null);

    return (
        <div className="rounded-3xl border border-white/10 bg-nebula-bg-secondary/60 p-2.5 shadow-glow backdrop-blur-xl">
            {imageError ? (
                <p className="mb-2 px-2 text-xs text-red-300">{imageError}</p>
            ) : null}

            {imagePreviewUrl ? (
                <div className="mb-2 flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                        src={imagePreviewUrl}
                        alt="Attached preview"
                        className="h-14 w-14 rounded-lg object-cover"
                    />
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-xs text-nebula-text-secondary">
                            {attachedImage?.name}
                        </p>
                        <p className="text-[11px] text-nebula-text-secondary/60">
                            {attachedImage
                                ? `${(attachedImage.size / 1024 / 1024).toFixed(1)} MB`
                                : ""}
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

            {/* Text row */}
            <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled}
                rows={1}
                dir="auto"
                placeholder={
                    attachedImage
                        ? "Add a caption (optional)..."
                        : "Message Nebula..."
                }
                className="max-h-40 min-h-[2.75rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm text-nebula-text placeholder:text-nebula-text-secondary/50 outline-none disabled:opacity-50"
            />

            {/* Toolbar row -- attach + search mode on the left, send on the right */}
            <div className="flex items-center justify-between gap-2 px-1 pt-1">
                <div className="flex items-center gap-1.5">
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
                        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-nebula-text-secondary transition-colors hover:bg-white/10 hover:text-nebula-text disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    >
                        <ImageIcon className="h-4 w-4" />
                    </button>

                    <SearchModeButton
                        mode={searchMode}
                        onChange={setSearchMode}
                        disabled={disabled}
                    />
                </div>

                <button
                    onClick={handleSend}
                    disabled={!canSend}
                    title="Send (Shift+Enter)"
                    className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-nebula-purple to-nebula-pink text-white transition-all hover:brightness-110 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                >
                    <Send className="h-4 w-4" />
                </button>
            </div>
        </div>
    );
}
