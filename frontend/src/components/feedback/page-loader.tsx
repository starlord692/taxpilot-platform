import { LoaderCircle } from "lucide-react";
export function PageLoader({ label = "Loading" }: { label?: string }) { return <div className="grid min-h-[50vh] place-items-center"><div className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" /><span>{label}</span></div></div>; }
