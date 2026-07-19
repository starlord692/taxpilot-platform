import { cn } from "@/lib/utils";

export function PageHeader({ title, description, actions, className }: { title: string; description?: string; actions?: React.ReactNode; className?: string }) {
  return <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between", className)}><div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>{description ? <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p> : null}</div>{actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}</header>;
}

export function SectionHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-4"><div><h2 className="text-base font-semibold">{title}</h2>{description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}</div>{actions}</div>;
}
