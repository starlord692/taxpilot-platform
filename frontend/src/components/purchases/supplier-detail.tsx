"use client";
import Link from "next/link";
import { Archive, ArrowLeft, Pencil, ReceiptText, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBusiness } from "@/contexts/business-context";
import { usePurchaseMutations, useSupplier } from "@/features/purchases/hooks/use-purchases";
import { PurchasesError, PurchasesLoading } from "./purchases-states";
import { SupplierActivityCard, SupplierAddressCard, SupplierContactCard, SupplierGSTCard, SupplierInformationCard } from "./supplier-cards";

export function SupplierDetail({ id }: { id: string }) {
  const { activeBusinessId } = useBusiness(); const query = useSupplier(id); const mutations = usePurchaseMutations();
  if (query.isLoading) return <PurchasesLoading rows={5} />;
  if (query.isError || !query.data) return <PurchasesError retry={() => void query.refetch()} />;
  const supplier = query.data;
  if (supplier.business_id !== activeBusinessId) return <div role="alert" className="rounded-xl border p-8 text-center"><h2 className="font-semibold">Supplier unavailable</h2><p className="mt-1 text-sm text-muted-foreground">This supplier does not belong to the active business.</p></div>;
  const toggle = async () => { try { if (supplier.is_active) await mutations.deactivateSupplier.mutateAsync(id); else await mutations.reactivateSupplier.mutateAsync(id); toast.success(supplier.is_active ? "Supplier archived" : "Supplier restored"); await query.refetch(); } catch (error) { toast.error(error instanceof Error ? error.message : "Supplier status could not be changed"); } };
  const pending = mutations.deactivateSupplier.isPending || mutations.reactivateSupplier.isPending;
  return <div className="space-y-5"><Link href="/purchases/suppliers" className="inline-flex items-center gap-2 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="size-4" aria-hidden="true" />Suppliers</Link><header className="rounded-2xl border bg-card p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-semibold">{supplier.name}</h2><Badge tone={supplier.is_active ? "success" : "neutral"}>{supplier.is_active ? "Active" : "Archived"}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{supplier.supplier_code}</p></div><div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href={`/purchases/suppliers/${id}/edit`}><Pencil aria-hidden="true" />Edit</Link></Button><Button asChild variant="outline"><Link href={`/purchases/invoices?supplier=${supplier.id}`}><ReceiptText aria-hidden="true" />View purchases</Link></Button><Button variant="outline" onClick={() => void toggle()} disabled={pending}>{supplier.is_active ? <Archive aria-hidden="true" /> : <RotateCcw aria-hidden="true" />}{pending ? "Saving…" : supplier.is_active ? "Archive" : "Restore"}</Button></div></div></header><div className="grid gap-5 md:grid-cols-2"><SupplierInformationCard supplier={supplier} /><SupplierContactCard supplier={supplier} /><SupplierGSTCard supplier={supplier} /><SupplierAddressCard supplier={supplier} /></div><SupplierActivityCard /></div>;
}
