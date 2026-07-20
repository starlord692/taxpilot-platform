"use client";
import Link from "next/link";
import { ArrowLeft, Archive, FilePlus2, Pencil, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBusiness } from "@/contexts/business-context";
import { useCustomer, useCustomerMutations } from "@/features/sales/hooks/use-sales";
import { AddressCard, ContactInformationCard, CustomerActivityCard, CustomerInformationCard, GSTInformationCard } from "./customer-cards";
import { SalesError, SalesLoading } from "./sales-states";

export function CustomerDetail({ id }: { id: string }) {
  const { activeBusinessId } = useBusiness(); const query = useCustomer(id); const mutations = useCustomerMutations();
  if (query.isLoading) return <SalesLoading rows={5} />;
  if (query.isError || !query.data) return <SalesError retry={() => void query.refetch()} />;
  const customer = query.data;
  if (customer.business_id !== activeBusinessId) return <div role="alert" className="rounded-xl border p-8 text-center"><h2 className="font-semibold">Customer unavailable</h2><p className="mt-1 text-sm text-muted-foreground">This customer does not belong to the active business.</p></div>;
  const toggleStatus = () => mutations.update.mutate({ id, input: { is_active: !customer.is_active } }, { onSuccess: () => toast.success(customer.is_active ? "Customer archived" : "Customer restored"), onError: error => toast.error(error instanceof Error ? error.message : "Customer status could not be changed") });
  return <div className="space-y-5"><Link href="/sales/customers" className="inline-flex items-center gap-2 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="size-4" aria-hidden="true" />Customers</Link><header className="rounded-2xl border bg-card p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-semibold">{customer.name}</h2><Badge tone={customer.is_active ? "success" : "neutral"}>{customer.is_active ? "Active" : "Archived"}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{customer.customer_code}</p></div><div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href={`/sales/customers/${id}/edit`}><Pencil aria-hidden="true" />Edit</Link></Button><Button asChild variant="outline"><Link href="/sales/invoices"><FilePlus2 aria-hidden="true" />View sales</Link></Button><Button variant="outline" onClick={toggleStatus} disabled={mutations.update.isPending}>{customer.is_active ? <Archive aria-hidden="true" /> : <RotateCcw aria-hidden="true" />}{mutations.update.isPending ? "Saving…" : customer.is_active ? "Archive" : "Restore"}</Button></div></div></header><div className="grid gap-5 md:grid-cols-2"><CustomerInformationCard customer={customer} /><ContactInformationCard customer={customer} /><GSTInformationCard customer={customer} /><AddressCard customer={customer} /></div><CustomerActivityCard /></div>;
}
