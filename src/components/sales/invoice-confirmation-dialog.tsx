"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, Info, LoaderCircle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface InvoiceConfirmationDialogProps {
  mode: "issue" | "cancel";
  invoiceNumber: string;
  isOpen: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function InvoiceConfirmationDialog({
  mode,
  invoiceNumber,
  isOpen,
  isPending,
  onClose,
  onConfirm,
}: InvoiceConfirmationDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    // Focus the safe cancel button by default to prevent accidental confirmation
    cancelButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isPending) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isPending, onClose]);

  if (!isOpen) return null;

  const isIssue = mode === "issue";

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-xs animate-in fade-in-0"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isPending) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-action-dialog-title"
        aria-describedby="invoice-action-dialog-description"
        className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl animate-in zoom-in-95"
      >
        <div className="flex items-start gap-4">
          <div
            className={`rounded-full p-2.5 ${
              isIssue
                ? "bg-primary/10 text-primary"
                : "bg-destructive/10 text-destructive"
            }`}
          >
            {isIssue ? (
              <ShieldAlert className="size-6" />
            ) : (
              <AlertTriangle className="size-6" />
            )}
          </div>
          <div className="flex-1">
            <h2
              id="invoice-action-dialog-title"
              className="text-lg font-semibold tracking-tight"
            >
              {isIssue ? "Confirm Invoice Issuance" : "Confirm Draft Cancellation"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Invoice <strong className="text-foreground">{invoiceNumber}</strong>
            </p>
          </div>
        </div>

        <div
          id="invoice-action-dialog-description"
          className="mt-4 space-y-3 text-sm text-muted-foreground"
        >
          {isIssue ? (
            <>
              <p>
                Issuing this invoice records the transaction and triggers the application&apos;s existing accounting and stock operations. Please review the following effects:
              </p>
              <ul className="space-y-2 rounded-lg border bg-muted/20 p-3 text-xs text-foreground list-disc pl-5">
                <li>
                  <strong>Status Transition:</strong> The invoice status will transition from <span className="font-semibold text-primary">Draft</span> to <span className="font-semibold text-primary">Issued</span>.
                </li>
                <li>
                  <strong>Inventory Decrement:</strong> The stock engine will execute physical quantity decrements for all product line items.
                </li>
                <li>
                  <strong>General Ledger Postings:</strong> Double-entry journal entries will post to Accounts Receivable (1020), Sales Revenue (4000), and Output Tax Payable (2010).
                </li>
                <li>
                  <strong>Cancellation Limitation:</strong> This screen does not support cancellation of an issued invoice. The appropriate correction workflow for issued invoices is not yet available in TaxPilot.
                </li>
              </ul>
              <div className="flex items-start gap-2 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/40 p-2.5 text-xs text-muted-foreground">
                <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <span>
                  <strong>Accounting scope note:</strong> Supported accounting behavior records commercial billing and physical stock movements. Perpetual-inventory Cost of Goods Sold (COGS) and inventory valuation asset entries are not posted.
                </span>
              </div>
            </>
          ) : (
            <>
              <p>
                Are you sure you want to cancel this draft invoice?
              </p>
              <ul className="space-y-2 rounded-lg border bg-muted/20 p-3 text-xs text-foreground list-disc pl-5">
                <li>
                  <strong>Draft Cancellation:</strong> The invoice will transition to <span className="font-semibold text-destructive">Cancelled</span> status.
                </li>
                <li>
                  <strong>Zero Accounting Impact:</strong> Because this invoice is in draft status, no inventory decrements and no accounting journal entries were posted.
                </li>
                <li>
                  <strong>Cancellation Restriction:</strong> Cancellation is restricted strictly to draft documents. This screen does not support cancellation of an issued invoice.
                </li>
              </ul>
            </>
          )}
        </div>

        <div className="mt-6 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2.5">
          <Button
            ref={cancelButtonRef}
            type="button"
            variant="outline"
            disabled={isPending}
            onClick={onClose}
          >
            {isIssue ? "Cancel" : "Keep draft"}
          </Button>
          <Button
            type="button"
            variant={isIssue ? "default" : "destructive"}
            disabled={isPending}
            onClick={onConfirm}
          >
            {isPending ? (
              <>
                <LoaderCircle className="mr-1.5 size-4 animate-spin" />
                {isIssue ? "Issuing invoice..." : "Cancelling draft..."}
              </>
            ) : isIssue ? (
              "Confirm & issue invoice"
            ) : (
              "Confirm cancellation"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
