import type { LucideIcon } from "lucide-react";
export function MetricCard({ label, icon: Icon, value, description = "An authoritative summary is not available from the current API." }: { label: string; icon: LucideIcon; value?: string; description?: string }) {
  const unavailable = value === undefined;
  return <article className="min-w-0 rounded-2xl border bg-card p-4 shadow-sm"><div className="flex items-center justify-between gap-3"><p className="truncate text-xs font-medium text-muted-foreground">{label}</p><span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground"><Icon className="size-4" aria-hidden="true" /></span></div><p className="mt-4 text-2xl font-semibold tabular-nums" aria-label={unavailable ? `${label}: data unavailable` : `${label}: ${value}`}>{value ?? "—"}</p><p className="mt-1 text-[11px] leading-4 text-muted-foreground">{description}</p></article>;
}
