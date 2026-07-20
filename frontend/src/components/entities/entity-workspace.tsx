import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function EntityWorkspaceHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: { href: string; label: string; icon?: LucideIcon } }) {
  const Icon = action?.icon;
  return <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-medium text-primary">{eyebrow}</p><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p></div>{action&&<Button asChild><Link href={action.href}>{Icon&&<Icon aria-hidden="true"/>}{action.label}</Link></Button>}</header>;
}

export function EntityStatusBadge({ active, activeLabel = "Active", inactiveLabel = "Archived" }: { active: boolean; activeLabel?: string; inactiveLabel?: string }) {
  return <Badge tone={active ? "success" : "neutral"}>{active ? activeLabel : inactiveLabel}</Badge>;
}

export function EntityEmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: { href: string; label: string } }) {
  return <section className="rounded-xl border border-dashed p-8 text-center"><Icon className="mx-auto size-8 text-muted-foreground" aria-hidden="true"/><h2 className="mt-3 font-semibold">{title}</h2><p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{description}</p>{action&&<Button asChild className="mt-4"><Link href={action.href}>{action.label}</Link></Button>}</section>;
}
