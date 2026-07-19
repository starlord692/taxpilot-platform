import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

type SearchBarProps = Omit<React.ComponentProps<"input">, "type"> & { onClear?: () => void };

export function SearchBar({ className, onClear, value, ...props }: SearchBarProps) {
  return <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><input type="search" value={value} className={cn("h-10 w-full rounded-xl border bg-background pl-9 pr-9 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring", className)} {...props} />{onClear && value ? <button type="button" onClick={onClear} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Clear search"><X className="size-4" /></button> : null}</div>;
}
