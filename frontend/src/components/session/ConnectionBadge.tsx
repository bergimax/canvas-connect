import type { ConnectionState } from "@/lib/types";
import { Cloud, CloudOff, RefreshCw } from "lucide-react";

export function ConnectionBadge({
  state,
  savedAt,
}: {
  state: ConnectionState;
  savedAt?: string | null;
}) {
  const map = {
    connected: { icon: Cloud, text: "Connected", cls: "text-success" },
    reconnecting: { icon: RefreshCw, text: "Reconnecting", cls: "text-warning" },
    offline: { icon: CloudOff, text: "Offline", cls: "text-destructive" },
  } as const;
  const { icon: Icon, text, cls } = map[state];
  return (
    <div
      className="flex items-center gap-1.5 rounded-md border border-border bg-elevated px-2 py-1 text-xs"
      role="status"
      aria-live="polite"
    >
      <Icon className={`size-3.5 ${cls} ${state === "reconnecting" ? "animate-spin" : ""}`} />
      <span className={cls}>{text}</span>
      {savedAt && state === "connected" ? (
        <span className="text-muted-foreground">· saved {savedAt}</span>
      ) : null}
    </div>
  );
}
