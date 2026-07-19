import { cn } from "@/lib/utils";
export function StatusBadge({ label, positive = false }: { label: string; positive?: boolean }) { return <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-medium capitalize", positive ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-muted text-muted-foreground")}>{label}</span>; }
