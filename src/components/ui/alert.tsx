import { CircleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
export function Alert({ children, className }: { children: React.ReactNode; className?: string }) { return <div role="alert" className={cn("flex gap-2.5 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-foreground", className)}><CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />{children}</div>; }
