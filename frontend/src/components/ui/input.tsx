import * as React from "react";
import { cn } from "@/lib/utils";
export function Input({ className, type, ...props }: React.ComponentProps<"input">) { return <input type={type} className={cn("flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-muted-foreground focus:border-primary/60 focus:ring-3 focus:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-50", className)} {...props} />; }
