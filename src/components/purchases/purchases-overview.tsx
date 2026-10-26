"use client";
import Link from "next/link";
import { Building2, FileText, Plus } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { usePurchases, useSuppliers } from "@/features/purchases/hooks/use-purchases";
import { PurchasesError, PurchasesLoading } from "./purchases-states";

export function PurchasesOverview() {
  const { activeBusinessId } = useBusiness(); const id = activeBusinessId ?? "";
  const suppliers = useSuppliers(id, { page: 1, pageSize: 1 }); const all = usePurchases(id, { page: 1, pageSize: 1 });
  const draft = usePurchases(id, { page: 1, pageSize: 1, status: "draft" }); const approved = usePurchases(id, { page: 1, pageSize: 1, status: "approved" }); const received = usePurchases(id, { page: 1, pageSize: 1, status: "received" }); const paid = usePurchases(id, { page: 1, pageSize: 1, status: "paid" }); const cancelled = usePurchases(id, { page: 1, pageSize: 1, status: "cancelled" });
  const queries = [suppliers, all, draft, approved, received, paid, cancelled];
  if (queries.some((query) => query.isLoading)) return <PurchasesLoading rows={3} />;
  if (queries.some((query) => query.isError)) return <PurchasesError retry={() => queries.forEach((query) => void query.refetch())} />;
  const counts = [{ title: "Suppliers", value: suppliers.data?.meta.total ?? 0, href: "/purchases/suppliers", icon: Building2 }, { title: "Purchase invoices", value: all.data?.meta.total ?? 0, href: "/purchases/invoices", icon: FileText }, { title: "Draft", value: draft.data?.meta.total ?? 0, href: "/purchases/invoices?status=draft", icon: FileText }, { title: "Approved", value: approved.data?.meta.total ?? 0, href: "/purchases/invoices?status=approved", icon: FileText }, { title: "Received", value: received.data?.meta.total ?? 0, href: "/purchases/invoices?status=received", icon: FileText }, { title: "Paid", value: paid.data?.meta.total ?? 0, href: "/purchases/invoices?status=paid", icon: FileText }, { title: "Cancelled", value: cancelled.data?.meta.total ?? 0, href: "/purchases/invoices?status=cancelled", icon: FileText }];
  return <div className="space-y-6"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{counts.map((count) => <Count key={count.title} {...count} />)}</div><section className="grid gap-3 sm:grid-cols-2"><Quick href="/purchases/suppliers/new" title="New supplier" description="Create a verified supplier record." /><Quick href="/purchases/invoices/new" title="New purchase" description="Create a draft purchase invoice." /></section><section className="rounded-xl border border-dashed p-6"><h2 className="font-semibold">Financial analytics unavailable</h2><p className="mt-1 text-sm text-muted-foreground">The verified backend does not expose purchase totals, trends, supplier balances, or payment analytics. Record counts above come from pagination metadata only.</p></section></div>;
}
function Count({ title, value, href, icon: Icon }: { title: string; value: number; href: string; icon: typeof Building2 }) { return <Link href={href} className="rounded-xl border bg-card p-4 hover:border-primary/40"><div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">{title}</p><Icon className="size-4 text-muted-foreground" /></div><p className="mt-3 text-2xl font-semibold tabular-nums">{value}</p><p className="mt-1 text-xs text-muted-foreground">Verified record count</p></Link>; }
function Quick({ href, title, description }: { href: string; title: string; description: string }) { return <Link href={href} className="flex items-center gap-3 rounded-xl border bg-card p-5 hover:border-primary/40"><Plus className="size-5" /><div><p className="font-medium">{title}</p><p className="text-sm text-muted-foreground">{description}</p></div></Link>; }
