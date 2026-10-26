"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Calculator, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { useBusiness } from "@/contexts/business-context";
import { useCatalogItems } from "@/features/catalog/hooks/use-catalog";
import { useWarehouses } from "@/features/inventory/hooks/use-inventory";
import { useCustomers, useSalesMutations } from "@/features/sales/hooks/use-sales";
import {
  invoiceCreateSchema,
  type InvoiceCreateFormValues,
} from "@/features/sales/schemas/sales-schemas";
import type { InvoiceCreateInput, InvoiceLineInput } from "@/features/sales/types/sales.types";
import { formatMoney } from "@/features/sales/utils/sales-format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SalesLoading } from "./sales-states";

export const standardGSTRates = [0, 5, 12, 18, 28] as const;

export function calculateLinePreview(line: {
  quantity: number;
  unit_price: number;
  discount?: number;
  tax_rate?: number;
}) {
  const qty = Number(line.quantity) || 0;
  const price = Number(line.unit_price) || 0;
  const gross = Number((qty * price).toFixed(2));
  const discount = Math.min(Number(line.discount) || 0, gross);
  const taxable = Number((gross - discount).toFixed(2));
  const taxRate = Number(line.tax_rate) || 0;
  const tax = Number(((taxable * taxRate) / 100).toFixed(2));
  const cgst = Number((tax / 2).toFixed(2));
  const sgst = Number((tax - cgst).toFixed(2));
  const lineTotal = Number((taxable + tax).toFixed(2));
  return {
    gross,
    discount,
    taxable,
    cgst,
    sgst,
    igst: 0,
    cess: 0,
    tax,
    lineTotal,
  };
}

export function calculateInvoiceTotals(lines: Array<{
  quantity: number;
  unit_price: number;
  discount?: number;
  tax_rate?: number;
}>) {
  let subtotal = 0;
  let discountTotal = 0;
  let taxTotal = 0;
  let cgstTotal = 0;
  let sgstTotal = 0;

  for (const line of lines) {
    const calc = calculateLinePreview(line);
    subtotal += calc.gross;
    discountTotal += calc.discount;
    taxTotal += calc.tax;
    cgstTotal += calc.cgst;
    sgstTotal += calc.sgst;
  }

  const taxableAmount = Number((subtotal - discountTotal).toFixed(2));
  const totalAmount = Number((taxableAmount + taxTotal).toFixed(2));

  return {
    subtotal: Number(subtotal.toFixed(2)),
    discount_amount: Number(discountTotal.toFixed(2)),
    taxable_amount: taxableAmount,
    cgst_amount: Number(cgstTotal.toFixed(2)),
    sgst_amount: Number(sgstTotal.toFixed(2)),
    tax_amount: Number(taxTotal.toFixed(2)),
    total_amount: totalAmount,
  };
}

const defaultLine = {
  catalog_item_id: null,
  warehouse_id: null,
  description: "",
  quantity: 1,
  unit_price: 0,
  discount: 0,
  tax_rate: 18,
  cgst_amount: 0,
  sgst_amount: 0,
  igst_amount: 0,
  cess_amount: 0,
  line_total: 0,
};

export function InvoiceForm() {
  const { activeBusinessId } = useBusiness();
  const customers = useCustomers(activeBusinessId ?? "", 1, 100);
  const catalogQuery = useCatalogItems(activeBusinessId ?? "", { status: "ACTIVE" });
  const warehousesQuery = useWarehouses(activeBusinessId ?? "", { page: 1, pageSize: 100 });
  const catalogItems = catalogQuery.data ?? [];
  const warehouses = warehousesQuery.data?.data ?? [];
  const mutations = useSalesMutations();
  const router = useRouter();

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const form = useForm<InvoiceCreateFormValues>({
    resolver: zodResolver(invoiceCreateSchema),
    defaultValues: {
      customer_id: "",
      invoice_number: "",
      invoice_date: today,
      due_date: null,
      notes: null,
      lines: [defaultLine],
    },
  });

  const fields = useFieldArray({
    control: form.control,
    name: "lines",
  });

  const watchedLines = form.watch("lines");
  const totals = useMemo(() => calculateInvoiceTotals(watchedLines || []), [watchedLines]);

  const submit = form.handleSubmit(async (values) => {
    if (!activeBusinessId) {
      form.setError("root", { message: "No active business selected." });
      return;
    }
    try {
      const parsed = invoiceCreateSchema.parse(values);
      const preparedLines: InvoiceLineInput[] = parsed.lines.map((line) => {
        const calc = calculateLinePreview(line);
        return {
          catalog_item_id: line.catalog_item_id || null,
          warehouse_id: line.warehouse_id || null,
          description: line.description,
          quantity: line.quantity,
          unit_price: line.unit_price,
          discount: line.discount ?? 0,
          tax_rate: line.tax_rate ?? 0,
          cgst_amount: calc.cgst,
          sgst_amount: calc.sgst,
          igst_amount: 0,
          cess_amount: 0,
          line_total: calc.lineTotal,
        };
      });
      const calcTotals = calculateInvoiceTotals(parsed.lines);
      const payload: InvoiceCreateInput = {
        business_id: activeBusinessId,
        customer_id: parsed.customer_id,
        invoice_number: parsed.invoice_number,
        invoice_date: parsed.invoice_date,
        due_date: parsed.due_date || null,
        notes: parsed.notes || null,
        status: "draft",
        subtotal: calcTotals.subtotal,
        discount_amount: calcTotals.discount_amount,
        taxable_amount: calcTotals.taxable_amount,
        tax_amount: calcTotals.tax_amount,
        total_amount: calcTotals.total_amount,
        lines: preparedLines,
      };

      const result = await mutations.createInvoice.mutateAsync(payload);
      toast.success("Draft invoice created successfully");
      router.push(`/sales/invoices/${result.id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invoice could not be created.";
      form.setError("root", { message });
      toast.error(message);
    }
  });

  if (customers.isLoading) return <SalesLoading rows={4} />;

  const activeCustomers = (customers.data?.data ?? []).filter((c) => c.is_active);

  return (
    <div className="space-y-5">
      <Link
        href="/sales/invoices"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to Invoices
      </Link>

      <form onSubmit={submit} noValidate className="space-y-6">
        <section className="rounded-xl border bg-card p-5">
          <header className="border-b pb-4">
            <h2 className="text-xl font-semibold tracking-tight">New Sales Invoice</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Create a new draft sales invoice for verified customers of the active business.
            </p>
          </header>

          {form.formState.errors.root?.message && (
            <div role="alert" className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {form.formState.errors.root.message}
            </div>
          )}

          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Customer" error={form.formState.errors.customer_id?.message} required>
              <select
                {...form.register("customer_id")}
                aria-label="Select customer"
                className="h-10 w-full rounded-lg border bg-background px-3 text-sm shadow-sm outline-none transition focus:border-primary/60 focus:ring-3 focus:ring-primary/10"
              >
                <option value="">Select customer</option>
                {activeCustomers.map((cust) => (
                  <option key={cust.id} value={cust.id}>
                    {cust.name} ({cust.customer_code})
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Invoice Number" error={form.formState.errors.invoice_number?.message} required>
              <Input
                {...form.register("invoice_number")}
                placeholder="e.g. INV-2026-0001"
                aria-label="Invoice number"
              />
            </Field>

            <Field label="Invoice Date" error={form.formState.errors.invoice_date?.message} required>
              <Input
                type="date"
                {...form.register("invoice_date")}
                aria-label="Invoice date"
              />
            </Field>

            <Field label="Due Date" error={form.formState.errors.due_date?.message}>
              <Input
                type="date"
                {...form.register("due_date")}
                aria-label="Due date"
              />
            </Field>
          </div>
        </section>

        <section className="rounded-xl border bg-card p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
            <div>
              <h3 className="text-lg font-semibold">Line Items</h3>
              <p className="text-sm text-muted-foreground">
                Add products or services with quantity, unit price, and applicable GST rate.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fields.append(defaultLine)}
              aria-label="Add line item"
            >
              <Plus className="mr-1 size-4" />
              Add line item
            </Button>
          </div>

          {form.formState.errors.lines?.message && (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {form.formState.errors.lines.message}
            </p>
          )}

          <div className="mt-4 space-y-4">
            {fields.fields.map((field, index) => {
              const lineValues = watchedLines?.[index] || defaultLine;
              const lineCalc = calculateLinePreview(lineValues);

              return (
                <div
                  key={field.id}
                  className="rounded-lg border bg-muted/10 p-4 transition hover:border-primary/30 space-y-3"
                >
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12 items-start">
                    <div className="lg:col-span-4">
                      <Label className="text-xs text-muted-foreground">Catalog Item</Label>
                      <select
                        value={form.watch(`lines.${index}.catalog_item_id`) ?? ""}
                        onChange={(e) => {
                          const selectedId = e.target.value;
                          form.setValue(`lines.${index}.catalog_item_id`, selectedId || null);
                          if (selectedId) {
                            const item = catalogItems.find((it) => it.id === selectedId);
                            if (item) {
                              form.setValue(`lines.${index}.description`, item.name);
                              form.setValue(`lines.${index}.unit_price`, Number(item.base_price) || 0);
                              form.setValue(`lines.${index}.tax_rate`, Number(item.tax_rate) || 0);
                              if (item.inventory_profile?.default_warehouse_id) {
                                form.setValue(`lines.${index}.warehouse_id`, item.inventory_profile.default_warehouse_id);
                              }
                            }
                          }
                        }}
                        aria-label={`Line ${index + 1} catalog item`}
                        className="mt-1 h-10 w-full rounded-lg border bg-background px-2 text-sm shadow-sm outline-none transition focus:border-primary/60 focus:ring-3 focus:ring-primary/10"
                      >
                        <option value="">
                          {catalogQuery.isLoading
                            ? "Loading catalog items..."
                            : catalogQuery.isError
                            ? "Failed to load catalog items"
                            : catalogItems.length === 0
                            ? "No active catalog items"
                            : "Select catalog item (optional)"}
                        </option>
                        {catalogItems.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name} ({item.code}) - {item.item_type}
                          </option>
                        ))}
                      </select>
                    </div>

                    {(() => {
                      const selectedItemId = form.watch(`lines.${index}.catalog_item_id`);
                      const selectedItem = catalogItems.find((it) => it.id === selectedItemId);
                      const isStockTracked =
                        selectedItem?.item_type === "PRODUCT" &&
                        Boolean(selectedItem?.inventory_profile?.stock_tracking);

                      return (
                        <>
                          <div className={isStockTracked ? "lg:col-span-5" : "lg:col-span-8"}>
                            <Label className="text-xs text-muted-foreground">Description *</Label>
                            <Input
                              {...form.register(`lines.${index}.description`)}
                              placeholder="Description of goods or services"
                              aria-label={`Line ${index + 1} description`}
                              className="mt-1"
                            />
                            {form.formState.errors.lines?.[index]?.description && (
                              <span role="alert" className="mt-1 block text-xs text-destructive">
                                {form.formState.errors.lines[index]?.description?.message}
                              </span>
                            )}
                          </div>

                          {isStockTracked && (
                            <div className="lg:col-span-3">
                              <Label className="text-xs text-muted-foreground">Warehouse</Label>
                              <select
                                {...form.register(`lines.${index}.warehouse_id`)}
                                aria-label={`Line ${index + 1} warehouse`}
                                className="mt-1 h-10 w-full rounded-lg border bg-background px-2 text-sm shadow-sm outline-none transition focus:border-primary/60 focus:ring-3 focus:ring-primary/10"
                              >
                                <option value="">
                                  {warehousesQuery.isLoading
                                    ? "Loading warehouses..."
                                    : "Select warehouse"}
                                </option>
                                {warehouses.map((wh) => (
                                  <option key={wh.id} value={wh.id}>
                                    {wh.name} ({wh.code})
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12 items-start">
                    <div className="lg:col-span-3">
                      <Label className="text-xs text-muted-foreground">Quantity *</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0.01"
                        {...form.register(`lines.${index}.quantity`, { valueAsNumber: true })}
                        aria-label={`Line ${index + 1} quantity`}
                        className="mt-1"
                      />
                      {form.formState.errors.lines?.[index]?.quantity && (
                        <span role="alert" className="mt-1 block text-xs text-destructive">
                          {form.formState.errors.lines[index]?.quantity?.message}
                        </span>
                      )}
                    </div>

                    <div className="lg:col-span-3">
                      <Label className="text-xs text-muted-foreground">Unit Price (₹) *</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0.01"
                        {...form.register(`lines.${index}.unit_price`, { valueAsNumber: true })}
                        aria-label={`Line ${index + 1} unit price`}
                        className="mt-1"
                      />
                      {form.formState.errors.lines?.[index]?.unit_price && (
                        <span role="alert" className="mt-1 block text-xs text-destructive">
                          {form.formState.errors.lines[index]?.unit_price?.message}
                        </span>
                      )}
                    </div>

                    <div className="lg:col-span-2">
                      <Label className="text-xs text-muted-foreground">Disc (₹)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        {...form.register(`lines.${index}.discount`, { valueAsNumber: true })}
                        aria-label={`Line ${index + 1} discount`}
                        className="mt-1"
                      />
                    </div>

                    <div className="lg:col-span-2">
                      <Label className="text-xs text-muted-foreground">GST %</Label>
                      <select
                        {...form.register(`lines.${index}.tax_rate`, { valueAsNumber: true })}
                        aria-label={`Line ${index + 1} tax rate`}
                        className="mt-1 h-10 w-full rounded-lg border bg-background px-2 text-sm shadow-sm outline-none transition focus:border-primary/60 focus:ring-3 focus:ring-primary/10"
                      >
                        {standardGSTRates.map((rate) => (
                          <option key={rate} value={rate}>
                            {rate}%
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="lg:col-span-1 text-right pt-6">
                      <p className="text-xs text-muted-foreground">Total</p>
                      <p className="font-semibold text-sm tabular-nums">
                        {formatMoney(lineCalc.lineTotal)}
                      </p>
                    </div>

                    <div className="lg:col-span-1 pt-6 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        disabled={fields.fields.length === 1}
                        onClick={() => fields.remove(index)}
                        aria-label={`Remove line ${index + 1}`}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="mt-2 text-xs text-muted-foreground flex flex-wrap gap-4 pt-2 border-t border-muted/20">
                    <span>Taxable: {formatMoney(lineCalc.taxable)}</span>
                    <span>CGST: {formatMoney(lineCalc.cgst)}</span>
                    <span>SGST: {formatMoney(lineCalc.sgst)}</span>
                    <span>GST Rate: {lineValues.tax_rate ?? 0}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2 items-start">
          <section className="rounded-xl border bg-card p-5">
            <h3 className="font-semibold mb-2">Invoice Notes & Terms</h3>
            <textarea
              {...form.register("notes")}
              rows={4}
              placeholder="Optional notes or terms for the customer..."
              aria-label="Invoice notes"
              className="w-full rounded-lg border bg-background p-3 text-sm shadow-sm outline-none transition placeholder:text-muted-foreground focus:border-primary/60 focus:ring-3 focus:ring-primary/10"
            />
          </section>

          <section className="rounded-xl border bg-card p-5">
            <div className="flex items-center gap-2 border-b pb-3">
              <Calculator className="size-4 text-primary" />
              <h3 className="font-semibold">Calculated Summary Preview</h3>
            </div>
            <dl className="mt-4 space-y-2.5 text-sm">
              <SummaryRow label="Gross Subtotal" value={formatMoney(totals.subtotal)} />
              <SummaryRow label="Discount Amount" value={formatMoney(totals.discount_amount)} />
              <SummaryRow label="Taxable Amount" value={formatMoney(totals.taxable_amount)} />
              <SummaryRow label="CGST" value={formatMoney(totals.cgst_amount)} />
              <SummaryRow label="SGST" value={formatMoney(totals.sgst_amount)} />
              <SummaryRow label="Total GST" value={formatMoney(totals.tax_amount)} />
              <div className="border-t pt-2 mt-2">
                <SummaryRow label="Total Amount" value={formatMoney(totals.total_amount)} strong />
              </div>
            </dl>
            <p className="mt-4 text-xs text-muted-foreground bg-muted/40 p-2.5 rounded-lg border border-dashed">
              Notice: The amounts displayed above are client preview values computed in agreement with intra-state GST rules. The backend authoritative engine performs official calculation and ledger verification upon save.
            </p>
          </section>
        </div>

        <div className="flex items-center justify-end gap-3 border-t pt-5">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={form.formState.isSubmitting || mutations.createInvoice.isPending}
            className="min-w-32"
          >
            {form.formState.isSubmitting || mutations.createInvoice.isPending
              ? "Saving draft..."
              : "Save draft invoice"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  error,
  required,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="ml-1 text-destructive">*</span>}
      </Label>
      {children}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function SummaryRow({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex justify-between items-center">
      <dt className={strong ? "font-semibold text-foreground" : "text-muted-foreground"}>
        {label}
      </dt>
      <dd className={`tabular-nums ${strong ? "font-bold text-lg text-primary" : "font-medium"}`}>
        {value}
      </dd>
    </div>
  );
}
