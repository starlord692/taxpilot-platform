"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { useBusiness } from "@/contexts/business-context";
import { useCustomer, useInvoice, useSalesMutations } from "@/features/sales/hooks/use-sales";
import { formatDate, formatMoney, paymentState, titleCase } from "@/features/sales/utils/sales-format";
import { InvoiceStatusBadge, PaymentBadge } from "./sales-badges";
import { SalesError, SalesLoading } from "./sales-states";
import { Button } from "@/components/ui/button";
import { InvoiceConfirmationDialog } from "./invoice-confirmation-dialog";

export function InvoiceDetail({ id }: { id: string }) {
  const { activeBusinessId } = useBusiness();
  const query = useInvoice(id);
  const customer = useCustomer(query.data?.customer_id ?? "");
  const mutations = useSalesMutations();

  const [actionDialog, setActionDialog] = useState<{
    mode: "issue" | "cancel";
    isOpen: boolean;
  }>({
    mode: "issue",
    isOpen: false,
  });

  if (query.isLoading) return <SalesLoading />;
  if (query.isError) return <SalesError retry={() => void query.refetch()} />;

  const invoice = query.data!;
  if (invoice.business_id !== activeBusinessId) {
    return (
      <div role="alert" className="rounded-xl border p-8 text-center">
        <h2 className="font-semibold">Invoice unavailable</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This invoice does not belong to the active business.
        </p>
      </div>
    );
  }

  const payment = paymentState(invoice);
  const isDraft = invoice.status === "draft";
  const isPending =
    (actionDialog.mode === "issue" && mutations.issueInvoice.isPending) ||
    (actionDialog.mode === "cancel" && mutations.cancelInvoice.isPending);

  const handleConfirm = async () => {
    if (actionDialog.mode === "issue") {
      try {
        await mutations.issueInvoice.mutateAsync(invoice.id);
        toast.success(`Invoice ${invoice.invoice_number} issued successfully`);
        setActionDialog((prev) => ({ ...prev, isOpen: false }));
        await query.refetch();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to issue invoice";
        toast.error(message);
        await query.refetch();
      }
    } else {
      try {
        await mutations.cancelInvoice.mutateAsync(invoice.id);
        toast.success(`Draft invoice ${invoice.invoice_number} cancelled`);
        setActionDialog((prev) => ({ ...prev, isOpen: false }));
        await query.refetch();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to cancel draft invoice";
        toast.error(message);
        await query.refetch();
      }
    }
  };

  return (
    <div className="space-y-5">
      <Link
        href="/sales/invoices"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Invoices
      </Link>

      <section className="rounded-xl border bg-card p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Invoice</p>
            <h2 className="text-2xl font-semibold">{invoice.invoice_number}</h2>
            <p className="mt-1 text-sm">{customer.data?.name ?? invoice.customer_id}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <InvoiceStatusBadge status={invoice.status} />
            <PaymentBadge label={payment.label} />
            {isDraft && (
              <div className="flex items-center gap-2 sm:ml-2">
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => setActionDialog({ mode: "issue", isOpen: true })}
                >
                  Issue invoice
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setActionDialog({ mode: "cancel", isOpen: true })}
                >
                  Cancel draft
                </Button>
              </div>
            )}
          </div>
        </div>

        <dl className="mt-6 grid gap-4 border-t pt-5 sm:grid-cols-3">
          <Data label="Invoice date" value={formatDate(invoice.invoice_date)} />
          <Data label="Due date" value={formatDate(invoice.due_date)} />
          <Data label="Total" value={formatMoney(invoice.total_amount)} />
        </dl>
      </section>

      {isDraft && invoice.lines.some((l) => !l.catalog_item_id) && (
        <section
          role="status"
          aria-label="unclassified-lines-recovery-notice"
          className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm"
        >
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-amber-600" />
          <div>
            <p className="font-medium text-amber-900 dark:text-amber-200">
              Catalog classification required
            </p>
            <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
              This draft contains lines without linked catalog items. Invoices require catalog items for GST tax classification and stock management. Please edit or re-create this draft with catalog-linked items prior to issuance.
            </p>
          </div>
        </section>
      )}

      {!isDraft && (
        <section
          role="status"
          aria-label="cancellation-policy-notice"
          className="flex items-start gap-3 rounded-xl border border-muted-foreground/20 bg-muted/30 p-4 text-sm"
        >
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div>
            <p className="font-medium text-foreground">Cancellation not available for issued invoices</p>
            <p className="mt-1 text-xs text-muted-foreground">
              This screen does not support cancellation of an issued invoice. The appropriate correction workflow for issued invoices is not yet available in TaxPilot.
            </p>
          </div>
        </section>
      )}

      <section className="overflow-hidden rounded-xl border bg-card">
        <div className="border-b p-5">
          <h3 className="font-semibold">Line items</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-4">Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Tax rate</th>
                <th>Tax</th>
                <th className="pr-4 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line) => (
                <tr key={line.id} className="border-t">
                  <td className="p-4 font-medium">{line.description}</td>
                  <td>{line.quantity}</td>
                  <td>{formatMoney(line.unit_price)}</td>
                  <td>{line.tax_rate}%</td>
                  <td>
                    {formatMoney(
                      Number(line.cgst_amount) +
                        Number(line.sgst_amount) +
                        Number(line.igst_amount) +
                        Number(line.cess_amount)
                    )}
                  </td>
                  <td className="pr-4 text-right">{formatMoney(line.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="ml-auto grid max-w-sm gap-2 border-t p-5 text-sm">
          <Row label="Subtotal" value={formatMoney(invoice.subtotal)} />
          <Row label="Discount" value={formatMoney(invoice.discount_amount)} />
          <Row label="Taxable amount" value={formatMoney(invoice.taxable_amount)} />
          <Row label="Tax" value={formatMoney(invoice.tax_amount)} />
          <Row label="Total" value={formatMoney(invoice.total_amount)} strong />
        </dl>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-xl border bg-card p-5">
          <h3 className="font-semibold">Payment summary</h3>
          <dl className="mt-4 space-y-2">
            <Row label="Paid" value={formatMoney(payment.paid)} />
            <Row label="Balance" value={formatMoney(payment.balance)} strong />
          </dl>
          <div className="mt-5 space-y-3">
            {invoice.payments.length ? (
              invoice.payments.map((item) => (
                <div key={item.id} className="rounded-lg border p-3 text-sm">
                  <div className="flex justify-between">
                    <span>{formatDate(item.payment_date)}</span>
                    <strong>{formatMoney(item.amount)}</strong>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {titleCase(item.payment_method)}
                    {item.reference_number ? ` · ${item.reference_number}` : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No payments are included with this invoice.</p>
            )}
          </div>
        </section>

        <section className="rounded-xl border bg-card p-5">
          <h3 className="font-semibold">Invoice timeline</h3>
          <div className="mt-4 border-l pl-4 space-y-3">
            <div>
              <p className="text-sm font-medium">Current status: {titleCase(invoice.status)}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Event history is not exposed by the verified API, so lifecycle events are not inferred.
              </p>
            </div>
            <div className="flex items-start gap-2 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-2.5 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <span>
                <strong>Accounting scope note:</strong> Supported accounting behavior records commercial billing (AR, Revenue, and Output GST) and physical stock movements. Perpetual-inventory Cost of Goods Sold (COGS) and inventory asset valuation (1030) entries are not posted.
              </span>
            </div>
          </div>
        </section>
      </div>

      {invoice.notes && (
        <section className="rounded-xl border bg-card p-5">
          <h3 className="font-semibold">Notes</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{invoice.notes}</p>
        </section>
      )}

      <InvoiceConfirmationDialog
        mode={actionDialog.mode}
        invoiceNumber={invoice.invoice_number}
        isOpen={actionDialog.isOpen}
        isPending={isPending}
        onClose={() => setActionDialog((prev) => ({ ...prev, isOpen: false }))}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

function Data({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-6">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={strong ? "font-semibold" : ""}>{value}</dd>
    </div>
  );
}
