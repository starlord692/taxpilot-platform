"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBusiness } from "@/contexts/business-context";
import { useCustomer, useCustomerMutations } from "@/features/sales/hooks/use-sales";
import { customerSchema, type CustomerFormValues } from "@/features/sales/schemas/customer-schema";
import { SalesError, SalesLoading } from "./sales-states";

export function CustomerForm({ id }: { id?: string }) {
  const customer = useCustomer(id ?? "");
  if (id && customer.isLoading) return <SalesLoading rows={5} />;
  if (id && (customer.isError || !customer.data)) return <SalesError retry={() => void customer.refetch()} />;
  const initial = customer.data ? { customer_code: customer.data.customer_code, name: customer.data.name, email: customer.data.email ?? "", phone: customer.data.phone ?? "", gstin: customer.data.gstin ?? "", pan: customer.data.pan ?? "", billing_address: customer.data.billing_address ?? "", shipping_address: customer.data.shipping_address ?? "" } : undefined;
  return <CustomerFormFields id={id} initial={initial} />;
}

function CustomerFormFields({ id, initial }: { id?: string; initial?: CustomerFormValues }) {
  const { activeBusinessId } = useBusiness(); const mutations = useCustomerMutations(); const router = useRouter();
  const form = useForm<CustomerFormValues>({ resolver: zodResolver(customerSchema), defaultValues: initial ?? { customer_code: "", name: "", email: "", phone: "", gstin: "", pan: "", billing_address: "", shipping_address: "" } });
  const submit = form.handleSubmit(async values => { if (!activeBusinessId) return; try { const parsed = customerSchema.parse(values); const input = { ...parsed, email: parsed.email || null, phone: parsed.phone || null, gstin: parsed.gstin || null, pan: parsed.pan || null, billing_address: parsed.billing_address || null, shipping_address: parsed.shipping_address || null }; const saved = id ? await mutations.update.mutateAsync({ id, input }) : await mutations.create.mutateAsync({ businessId: activeBusinessId, input }); toast.success(id ? "Customer updated" : "Customer created"); router.push(`/sales/customers/${saved.id}`); } catch (error) { form.setError("root", { message: error instanceof Error ? error.message : "Customer could not be saved." }); } });
  const pending = mutations.create.isPending || mutations.update.isPending;
  return <form onSubmit={submit} noValidate className="mx-auto max-w-4xl space-y-6"><header><h2 className="text-xl font-semibold">{id ? "Edit customer" : "New customer"}</h2><p className="mt-1 text-sm text-muted-foreground">Add only the customer information supported by TaxPilot.</p></header>{form.formState.errors.root?.message ? <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">{form.formState.errors.root.message}</p> : null}<section className="rounded-2xl border bg-card p-5"><h3 className="font-semibold">Customer identity</h3><div className="mt-4 grid gap-4 sm:grid-cols-2"><Field label="Customer name" error={form.formState.errors.name?.message}><Input autoFocus autoComplete="organization" {...form.register("name")} /></Field><Field label="Customer code" error={form.formState.errors.customer_code?.message}><Input {...form.register("customer_code")} /></Field><Field label="Email" error={form.formState.errors.email?.message}><Input type="email" autoComplete="email" {...form.register("email")} /></Field><Field label="Phone" hint="International format, for example +919876543210" error={form.formState.errors.phone?.message}><Input type="tel" autoComplete="tel" {...form.register("phone")} /></Field></div></section><section className="rounded-2xl border bg-card p-5"><h3 className="font-semibold">Tax information</h3><div className="mt-4 grid gap-4 sm:grid-cols-2"><Field label="GSTIN" error={form.formState.errors.gstin?.message}><Input className="uppercase" {...form.register("gstin")} /></Field><Field label="PAN" error={form.formState.errors.pan?.message}><Input className="uppercase" {...form.register("pan")} /></Field></div><p className="mt-3 text-xs text-muted-foreground">Pincode is not a separate backend field. Include it within the applicable address.</p></section><section className="rounded-2xl border bg-card p-5"><h3 className="font-semibold">Addresses</h3><div className="mt-4 grid gap-4 sm:grid-cols-2"><Field label="Billing address" error={form.formState.errors.billing_address?.message}><textarea className="min-h-28 w-full rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" {...form.register("billing_address")} /></Field><Field label="Shipping address" error={form.formState.errors.shipping_address?.message}><textarea className="min-h-28 w-full rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" {...form.register("shipping_address")} /></Field></div></section><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button><Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save customer"}</Button></div></form>;
}

function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) { return <label className="space-y-2"><Label>{label}</Label>{children}{hint && !error ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}{error ? <span className="block text-xs text-destructive">{error}</span> : null}</label>; }
