"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useBusiness } from "@/contexts/business-context";
import { usePurchaseMutations, useSupplier } from "@/features/purchases/hooks/use-purchases";
import { supplierSchema, type SupplierFormValues } from "@/features/purchases/schemas/purchase-schemas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PurchasesError, PurchasesLoading } from "./purchases-states";

export function SupplierForm({ id }: { id?: string }) {
  const existing = useSupplier(id ?? "");
  if (id && existing.isLoading) return <PurchasesLoading rows={4} />;
  if (id && (existing.isError || !existing.data)) return <PurchasesError retry={() => void existing.refetch()} />;
  const initial = existing.data ? { name: existing.data.name, email: existing.data.email ?? "", phone: existing.data.phone ?? "", gstin: existing.data.gstin ?? "", pan: existing.data.pan ?? "", address: existing.data.address ?? "", payment_terms: existing.data.payment_terms ?? "", is_active: existing.data.is_active } : undefined;
  return <SupplierFormFields id={id} initial={initial} />;
}

function SupplierFormFields({ id, initial }: { id?: string; initial?: SupplierFormValues }) {
  const { activeBusinessId } = useBusiness(); const mutations = usePurchaseMutations(); const router = useRouter();
  const form = useForm<SupplierFormValues>({ resolver: zodResolver(supplierSchema), defaultValues: initial ?? { name: "", email: "", phone: "", gstin: "", pan: "", address: "", payment_terms: "", is_active: true } });
  const pending = mutations.createSupplier.isPending || mutations.updateSupplier.isPending;
  const submit = form.handleSubmit(async values => { if (!activeBusinessId) return; try { const parsed = supplierSchema.parse(values); const input = { ...parsed, email: parsed.email || null, phone: parsed.phone || null, gstin: parsed.gstin || null, pan: parsed.pan || null, address: parsed.address || null, payment_terms: parsed.payment_terms || null }; const supplier = id ? await mutations.updateSupplier.mutateAsync({ id, input }) : await mutations.createSupplier.mutateAsync({ businessId: activeBusinessId, input }); toast.success(id ? "Supplier updated" : "Supplier created"); router.push(`/purchases/suppliers/${supplier.id}`); } catch (error) { form.setError("root", { message: error instanceof Error ? error.message : "Supplier could not be saved." }); } });
  return <form onSubmit={submit} noValidate className="mx-auto max-w-3xl space-y-5 rounded-2xl border bg-card p-5"><header><h2 className="text-xl font-semibold">{id ? "Edit supplier" : "New supplier"}</h2><p className="mt-1 text-sm text-muted-foreground">Only fields supported by the supplier API are included.</p></header>{form.formState.errors.root?.message ? <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">{form.formState.errors.root.message}</p> : null}<div className="grid gap-4 sm:grid-cols-2"><Field label="Supplier name" error={form.formState.errors.name?.message}><Input autoFocus autoComplete="organization" {...form.register("name")} /></Field><Field label="Email" error={form.formState.errors.email?.message}><Input type="email" autoComplete="email" {...form.register("email")} /></Field><Field label="Phone" error={form.formState.errors.phone?.message}><Input type="tel" autoComplete="tel" placeholder="+919876543210" {...form.register("phone")} /></Field><Field label="Payment terms" error={form.formState.errors.payment_terms?.message}><Input placeholder="Net 30" {...form.register("payment_terms")} /></Field><Field label="GSTIN" error={form.formState.errors.gstin?.message}><Input className="uppercase" {...form.register("gstin")} /></Field><Field label="PAN" error={form.formState.errors.pan?.message}><Input className="uppercase" {...form.register("pan")} /></Field></div><Field label="Address" error={form.formState.errors.address?.message}><textarea {...form.register("address")} className="min-h-24 w-full rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></Field>{id ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...form.register("is_active")} />Active supplier</label> : null}<div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button><Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save supplier"}</Button></div></form>;
}
function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) { return <label className="space-y-2"><Label>{label}</Label>{children}{error ? <span className="block text-xs text-destructive">{error}</span> : null}</label>; }
