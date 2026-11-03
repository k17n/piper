import { useEffect, useRef, useState, type ReactNode } from "react";
import { Pencil } from "lucide-react";
import { stageColor, stageLabel } from "../lib/stages";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Button({
  children,
  onClick,
  variant = "ghost",
  disabled,
  title,
  label,
  className,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline" | "danger";
  disabled?: boolean;
  title?: string;
  /** Accessible name for buttons that show only an icon. */
  label?: string;
  className?: string;
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-accent text-accent-ink shadow-sm hover:brightness-110",
    ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
    outline: "border border-line text-ink-2 hover:bg-surface-2 hover:text-ink",
    danger: "text-negative hover:bg-negative/10",
  }[variant];
  return (
    <button
      type={type}
      title={title}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        "inline-flex h-8 select-none items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-[13px] font-medium transition-[background-color,color,filter,transform] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40",
        styles,
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Popover({
  trigger,
  children,
  align = "left",
  width = 260,
}: {
  trigger: (open: boolean, toggle: () => void) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  width?: number;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      {trigger(open, () => setOpen((o) => !o))}
      {open && (
        <div
          style={{ width }}
          className={cx(
            "anim-pop-in absolute top-full z-40 mt-1.5 rounded-[10px] border border-line bg-surface p-1.5 shadow-[var(--shadow-pop)]",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function StageBadge({ stage, override }: { stage: string; override?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink-2">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: stageColor(stage) }} />
      {stageLabel(stage)}
      {override && <Pencil size={11} aria-label="Set manually" className="text-muted" />}
    </span>
  );
}

const URL_RE = /(https?:\/\/[^\s<>()"']+)/g;

function shortUrl(url: string) {
  try {
    const u = new URL(url);
    const path = u.pathname === "/" ? "" : u.pathname.replace(/\/$/, "");
    const short = `${u.hostname.replace(/^www\./, "")}${path}`;
    return short.length > 48 ? `${short.slice(0, 45)}…` : short;
  } catch {
    return url.length > 48 ? `${url.slice(0, 45)}…` : url;
  }
}

/** Email text: keeps line breaks, wraps long words, and shows links as short clickable labels. */
export function EmailText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(URL_RE);
  return (
    <p className={cx("whitespace-pre-line text-sm leading-relaxed text-ink-2 [overflow-wrap:anywhere]", className)}>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <a key={i} href={part} target="_blank" rel="noreferrer" title={part} className="text-accent hover:underline">
            {shortUrl(part)}
          </a>
        ) : (
          part
        ),
      )}
    </p>
  );
}

export function Empty({ title, icon, children }: { title: string; icon?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      {icon && <div className="mb-1 flex size-10 items-center justify-center rounded-full bg-surface-2 text-muted">{icon}</div>}
      <div className="text-[15px] font-medium text-ink">{title}</div>
      {children && <div className="max-w-md text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function fmtDate(iso: string) {
  // date-only → local midnight; naive datetimes from the API are UTC
  const d =
    iso.length === 10 ? new Date(`${iso}T00:00:00`) : new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
