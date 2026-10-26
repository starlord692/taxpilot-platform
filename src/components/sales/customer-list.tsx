"use client";
import Link from "next/link";
import { useBusiness } from "@/contexts/business-context";
import { useCustomers } from "@/features/sales/hooks/use-sales";
import { parsePage, parsePageSize } from "@/features/sales/utils/sales-format";
import { useSearchParams } from "next/navigation";
import { SalesEmpty, SalesError, SalesLoading, UnsupportedTools } from "./sales-states";
import { SalesPagination } from "./sales-pagination";

export function CustomerList() { const { activeBusinessId } = useBusiness(); const params = useSearchParams(); const page = parsePage(params.get("page")); const pageSize = parsePageSize(params.get("page_size")); const query = useCustomers(activeBusinessId ?? "", page, pageSize);
  if (query.isLoading) return <SalesLoading />; if (query.isError) return <SalesError retry={() => void query.refetch()} />; const data = query.data!;
  return <div className="space-y-4"><UnsupportedTools />{data.data.length === 0 ? <SalesEmpty title="No customers" description="No customer records were returned for this business." /> : <><div className="overflow-hidden rounded-xl border"><div className="hidden grid-cols-[1.5fr_1fr_1fr_auto] gap-4 border-b bg-muted/40 px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground md:grid"><span>Customer</span><span>GSTIN</span><span>Contact</span><span>Status</span></div>{data.data.map((customer) => <Link key={customer.id} href={`/sales/customers/${customer.id}`} className="grid gap-2 border-b p-4 last:border-0 hover:bg-muted/40 md:grid-cols-[1.5fr_1fr_1fr_auto] md:items-center"><div><p className="font-medium">{customer.name}</p><p className="text-xs text-muted-foreground">{customer.customer_code}</p></div><p className="text-sm"><span className="md:hidden text-muted-foreground">GSTIN: </span>{customer.gstin ?? "Unavailable"}</p><div className="text-sm"><p>{customer.email ?? "Email unavailable"}</p><p className="text-muted-foreground">{customer.phone ?? "Phone unavailable"}</p></div><span className={customer.is_active ? "text-sm text-emerald-600" : "text-sm text-muted-foreground"}>{customer.is_active ? "Active" : "Inactive"}</span></Link>)}</div><SalesPagination page={data.meta.page} pages={data.meta.pages} pageSize={data.meta.size} /></>}</div>;
}
