import type { ReactNode } from "react";

import { Icon, type IconName } from "@/components/ui/Icon";

type Tone = "info" | "ok" | "warn" | "danger" | "neutral";

const TONE_ICON: Record<Tone, IconName> = {
  info: "info",
  ok: "check",
  warn: "alert",
  danger: "ban",
  neutral: "info",
};

/** One short message with an icon. Keep the title to a few words. */
export function Callout({
  tone = "info",
  title,
  icon,
  children,
}: {
  tone?: Tone;
  title: string;
  icon?: IconName;
  children?: ReactNode;
}) {
  return (
    <div className={`callout tone-${tone}`} role={tone === "danger" ? "alert" : "note"}>
      <Icon name={icon ?? TONE_ICON[tone]} size={20} />
      <div>
        <strong>{title}</strong>
        {children && <div className="callout-body">{children}</div>}
      </div>
    </div>
  );
}

/** Centered placeholder for "nothing here yet" states, with an optional next action. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <h2>{title}</h2>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ApiDown({ message }: { message: string }) {
  return (
    <Callout tone="danger" title="Evidence Engine not reachable">
      Start it with <code>pnpm dev:api</code>. <span className="muted">{message}</span>
    </Callout>
  );
}
