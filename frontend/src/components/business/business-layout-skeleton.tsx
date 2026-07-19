import { Skeleton } from "@/components/ui/skeleton";
export function BusinessLayoutSkeleton() { return <div className="space-y-5" aria-busy="true" aria-label="Loading business context"><Skeleton className="h-8 w-64" /><Skeleton className="h-12 w-full" /><div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-56 rounded-xl" /><Skeleton className="h-56 rounded-xl" /></div></div>; }
