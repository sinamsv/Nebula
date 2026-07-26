"use client";

import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { Send, X } from "lucide-react";
import { cn } from "@/lib/utils";
import PlusMenu from "@/components/PlusMenu";
import ModelSelector from "@/components/ModelSelector";
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
    /** True while centered in the empty-state layout -- controls the
     * "elevated hero" visual treatment vs. the flatter docked-at-bottom
     * treatment. Purely cosmetic; the parent page decides layout
     * position via its own container, this only reads the flag to
     * adjust shadow/border emphasis. */
    variant?: "hero" | "docked";
}

/**
 * The composer: one continuous rounded "capsule" (rounded-3xl) with
 * the toolbar (the "+" tools menu + model selector) sitting INSIDE it
 * on its own row, above the text input row -- the Claude/ChatGPT
 * composer shape. The "+" button (see PlusMenu) now bundles both the
 * image-attach trigger and the search-mode toggle behind one entry
 * point, and a purely-visual model selector sits alongside it.
 */
export default function MessageInput({
    onSendText,
    onSendImage,
    disabled,
    variant = "docked",
}: MessageInputProps) {
    const [text, setText] = useState("");
    const [searchMode, setSearchMode] = useState<SearchMode>("smart");
    const [attachedImage, setAttachedImage] = useState<File | null>(null);
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const [imageError, setImageError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

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

    function autoGrow() {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }

    function handleSend() {
        const trimmed = text.trim();
        if (disabled) return;

        if (attachedImage) {
            if (!trimmed && !attachedImage) return;
            onSendImage(attachedImage, trimmed);
            removeImage();
            setText("");
            requestAnimationFrame(autoGrow);
            return;
        }

        if (!trimmed) return;
        onSendText(trimmed, searchMode);
        setText("");
        requestAnimationFrame(autoGrow);
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
        <div className="w-full">
            <div
                className={cn(
                    "rounded-3xl border bg-nebula-surface/70 p-2.5 backdrop-blur-xl transition-shadow duration-300",
                    variant === "hero"
                        ? "border-nebula-border-hover shadow-glow"
                        : "border-nebula-border shadow-composer"
                )}
            >
                {imageError ? (
                    <p className="mb-2 px-2 text-xs text-red-300">{imageError}</p>
                ) : null}

                {imagePreviewUrl ? (
                    <div className="mb-2 flex items-center gap-3 rounded-xl border border-nebula-border bg-white/5 p-2 animate-scale-in">
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
                            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-nebula-text-secondary hover:bg-white/10 hover:text-red-300 cursor-pointer"
                            aria-label="Remove attached image"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                ) : null}

                {/* Text row */}
                <textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => {
                        setText(e.target.value);
                        autoGrow();
                    }}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                    rows={1}
                    dir="auto"
                    placeholder={
                        attachedImage
                            ? "Add a caption (optional)..."
                            : "Message Nebula..."
                    }
                    className="max-h-[200px] min-h-[2.75rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm text-nebula-text placeholder:text-nebula-text-secondary/50 outline-none disabled:opacity-50"
                />

                {/* Toolbar row -- "+" tools menu + model selector on the
                    left, send on the right */}
                <div className="flex items-center justify-between gap-2 px-1 pt-1">
                    <div className="flex items-center gap-1">
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept={ALLOWED_IMAGE_TYPES.join(",")}
                            className="hidden"
                            onChange={handleFileChange}
                        />
                        <PlusMenu
                            onPickImage={() => fileInputRef.current?.click()}
                            searchMode={searchMode}
                            onSearchModeChange={setSearchMode}
                            disabled={disabled}
                        />
                        <div className="mx-0.5 h-5 w-px bg-nebula-border" />
                        <ModelSelector />
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

            <p className="mt-2.5 text-center text-[11px] text-nebula-text-secondary/60">
                Nebula is an AI and can make mistakes. Please double check responses.
            </p>
        </div>
    );
}
