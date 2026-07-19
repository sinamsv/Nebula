import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

/** Always renders a visible label above the input -- placeholder text
 * is never used as the sole label (per UX best practice: placeholders
 * disappear on focus/input, leaving no persistent context). */
const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, hint, id, className, ...rest }, ref) => {
    const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-nebula-text-secondary">
          {label}
        </label>
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "rounded-xl border bg-white/5 px-3.5 py-2.5 text-nebula-text placeholder:text-nebula-text-secondary/50",
            "border-white/10 outline-none transition-colors duration-150",
            "focus:border-nebula-purple/60 focus:ring-2 focus:ring-nebula-purple/30",
            error && "border-red-400/60 focus:border-red-400/60 focus:ring-red-400/30",
            className
          )}
          {...rest}
        />
        {hint && !error ? <p className="text-xs text-nebula-text-secondary">{hint}</p> : null}
        {error ? <p className="text-xs text-red-300">{error}</p> : null}
      </div>
    );
  }
);
TextField.displayName = "TextField";

export default TextField;
