"use client";
import Link from "next/link";
import { ArrowRight, FileCheck2, Files, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBusiness } from "@/contexts/business-context";
import { useDocuments, usePendingReviews } from "@/features/documents/hooks/use-documents";
import { DocumentEmpty, DocumentError, DocumentLoading } from "./document-states";

export function DocumentDashboard() {
  const { activeBusinessId } = useBusiness();
  const businessId = activeBusinessId ?? "";
  const documents = useDocuments(businessId, { page: 1, pageSize: 10 });
  const reviews = usePendingReviews(businessId, 1, 10);
  if (documents.isLoading || reviews.isLoading) return <DocumentLoading />;
  if (documents.isError || reviews.isError) return <DocumentError retry={() => void Promise.all([documents.refetch(), reviews.refetch()])} />;
  const total = documents.data?.meta.total ?? 0;
  const pending = reviews.data?.meta.total ?? 0;
  return <div className="space-y-6"><section aria-labelledby="document-overview-title"><div className="mb-3 flex items-end justify-between gap-4"><div><h2 id="document-overview-title" className="text-lg font-semibold">Workspace overview</h2><p className="text-sm text-muted-foreground">Counts come directly from the current business records.</p></div><Button asChild><Link href="/documents/upload"><Upload aria-hidden="true" />Upload document</Link></Button></div><div className="grid gap-4 md:grid-cols-2"><OverviewCard href="/documents/list" icon={Files} label="Documents in queue" value={total} action="Open queue" /><OverviewCard href="/documents/review" icon={FileCheck2} label="Needs your review" value={pending} action="Review documents" /></div></section>{total === 0 ? <DocumentEmpty title="No documents yet" description="Upload a PDF or image to begin. TaxPilot will show each available step without running it in the background." /> : null}<section className="rounded-xl border border-dashed p-5" aria-labelledby="workflow-availability-title"><h2 id="workflow-availability-title" className="font-semibold">What you can do here</h2><p className="mt-2 text-sm text-muted-foreground">Read a document, check its information, approve it, and create the supported business record. Each step starts only when you choose it.</p><p className="mt-2 text-xs text-muted-foreground">Queue-wide completion summaries, trends, and background processing are not available from the current backend.</p></section></div>;
}

function OverviewCard({ href, icon: Icon, label, value, action }: { href: string; icon: typeof Files; label: string; value: number; action: string }) { return <Link href={href} className="group rounded-xl border bg-card p-5 transition-colors hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Icon className="size-5 text-primary" aria-hidden="true" /><p className="mt-4 text-sm text-muted-foreground">{label}</p><strong className="text-2xl">{value}</strong><span className="mt-4 flex items-center gap-1 text-sm font-medium text-primary">{action}<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" /></span></Link>; }
