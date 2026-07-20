"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PurchasesPagination } from "@/components/purchases/purchases-pagination";
import { useBusiness } from "@/contexts/business-context";
import { usePendingReviews } from "@/features/documents/hooks/use-documents";
import { page, size } from "@/features/documents/utils/document-utils";
import { DocumentBadge } from "./document-badge";
import { DocumentEmpty, DocumentError, DocumentLoading } from "./document-states";

export function PendingReviews() {
  const { activeBusinessId } = useBusiness(); const params = useSearchParams(); const result = usePendingReviews(activeBusinessId ?? "", page(params.get("page")), size(params.get("page_size")));
  return <div className="space-y-4"><div><h2 className="text-lg font-semibold">Needs review</h2><p className="text-sm text-muted-foreground">Documents waiting for you to check and approve their information.</p></div>{result.isLoading ? <DocumentLoading /> : result.isError ? <DocumentError retry={() => void result.refetch()} /> : !result.data?.data.length ? <DocumentEmpty title="Nothing needs review" description="There are no documents waiting for your decision." /> : <><div className="rounded-xl border">{result.data.data.map(item => <Link className="flex items-center justify-between border-b p-4 transition-colors last:border-0 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" key={item.id} href={`/documents/${item.document_id}`}><span><span className="block text-sm font-medium">Review document</span><span className="font-mono text-xs text-muted-foreground">{item.document_id}</span></span><DocumentBadge value="Needs review" tone="warn" /></Link>)}</div><PurchasesPagination page={result.data.meta.page} pages={result.data.meta.pages} pageSize={result.data.meta.size} /></>}</div>;
}
