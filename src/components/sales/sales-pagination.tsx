"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
export function SalesPagination({ page, pages, pageSize }: { page: number; pages: number; pageSize: number }) {
  const router = useRouter(); const pathname = usePathname(); const params = useSearchParams();
  const go = (next: number, size = pageSize) => { const query = new URLSearchParams(params); query.set("page", String(next)); query.set("page_size", String(size)); router.push(`${pathname}?${query}`); };
  return <nav aria-label="Pagination" className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between"><label className="text-sm text-muted-foreground">Rows per page <select value={pageSize} onChange={(e) => go(1, Number(e.target.value))} className="ml-2 rounded-md border bg-background px-2 py-1" aria-label="Rows per page"><option>10</option><option>20</option><option>50</option></select></label><div className="flex items-center gap-2"><span className="text-sm text-muted-foreground">Page {page} of {Math.max(pages, 1)}</span><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => go(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= pages} onClick={() => go(page + 1)}>Next</Button></div></nav>;
}
