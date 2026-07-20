import { Skeleton } from "@/components/ui/skeleton";

export function DocumentWorkspaceSkeleton() { return <div className="space-y-5" aria-label="Loading document workspace" aria-busy="true"><Skeleton className="h-20 rounded-2xl" /><Skeleton className="h-28 rounded-2xl" /><div className="grid gap-5 lg:grid-cols-2"><Skeleton className="h-[32rem] rounded-2xl" /><Skeleton className="h-[32rem] rounded-2xl" /></div></div>; }
