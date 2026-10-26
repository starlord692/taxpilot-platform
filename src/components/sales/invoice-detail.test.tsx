import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InvoiceDetail } from "./invoice-detail";
import { toast } from "sonner";
import type { Customer, Invoice } from "@/features/sales/types/sales.types";

const mockIssueMutateAsync = vi.fn();
const mockCancelMutateAsync = vi.fn();
const mockRefetch = vi.fn();

let activeBusinessId = "b1";
let mockInvoice: Invoice | null = null;
let mockCustomer: Customer | null = null;
let isInvoiceLoading = false;
let isInvoiceError = false;
let isIssuePending = false;
let isCancelPending = false;

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/contexts/business-context", () => ({
  useBusiness: () => ({
    activeBusinessId,
    businesses: [{ id: "b1", name: "Acme Corp" }],
  }),
}));

vi.mock("@/features/sales/hooks/use-sales", () => ({
  useInvoice: () => ({
    data: mockInvoice,
    isLoading: isInvoiceLoading,
    isError: isInvoiceError,
    refetch: mockRefetch,
  }),
  useCustomer: () => ({
    data: mockCustomer,
    isLoading: false,
    isError: false,
  }),
  useSalesMutations: () => ({
    createInvoice: {
      mutateAsync: vi.fn(),
      isPending: false,
    },
    issueInvoice: {
      mutateAsync: mockIssueMutateAsync,
      isPending: isIssuePending,
    },
    cancelInvoice: {
      mutateAsync: mockCancelMutateAsync,
      isPending: isCancelPending,
    },
  }),
}));

const draftInvoice: Invoice = {
  id: "inv-1",
  business_id: "b1",
  customer_id: "c1",
  invoice_number: "INV-2026-0001",
  invoice_date: "2026-04-01",
  due_date: "2026-04-30",
  status: "draft",
  subtotal: 1000,
  discount_amount: 50,
  taxable_amount: 950,
  tax_amount: 171,
  total_amount: 1121,
  notes: "Draft review note",
  lines: [
    {
      id: "l1",
      invoice_id: "inv-1",
      description: "Cloud Consulting",
      quantity: 2,
      unit_price: 500,
      discount: 50,
      tax_rate: 18,
      cgst_amount: 85.5,
      sgst_amount: 85.5,
      igst_amount: 0,
      cess_amount: 0,
      line_total: 1121,
    },
  ],
  payments: [],
};

const issuedInvoice: Invoice = {
  ...draftInvoice,
  id: "inv-2",
  invoice_number: "INV-2026-0002",
  status: "issued",
};

const testCustomer: Customer = {
  id: "c1",
  business_id: "b1",
  customer_code: "CUST-0001",
  name: "Aarav Enterprises",
  email: "aarav@example.com",
  phone: "+91 98765 43210",
  gstin: "27AAAAA0000A1Z5",
  pan: "AAAAA0000A",
  billing_address: "123 Business Way, Mumbai",
  shipping_address: "123 Business Way, Mumbai",
  is_active: true,
};

describe("InvoiceDetail component (Phase 2 Issuance & Draft Cancellation)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    activeBusinessId = "b1";
    mockInvoice = { ...draftInvoice };
    mockCustomer = { ...testCustomer };
    isInvoiceLoading = false;
    isInvoiceError = false;
    isIssuePending = false;
    isCancelPending = false;
  });

  it("renders draft invoice with Issue and Cancel draft action buttons", () => {
    render(<InvoiceDetail id="inv-1" />);

    expect(screen.getByRole("heading", { name: "INV-2026-0001" })).toBeVisible();
    expect(screen.getByText("Aarav Enterprises")).toBeVisible();
    expect(screen.getByRole("button", { name: /issue invoice/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /cancel draft/i })).toBeVisible();

    // Cancellation policy warning banner should NOT be present for drafts
    expect(
      screen.queryByLabelText("cancellation-policy-notice")
    ).not.toBeInTheDocument();

    // Accounting scope disclosure must be visible in timeline section
    expect(
      screen.getByText(/perpetual-inventory cost of goods sold/i)
    ).toBeVisible();
  });

  it("hides action buttons and shows cancellation policy notice for non-draft invoices", () => {
    mockInvoice = { ...issuedInvoice };
    render(<InvoiceDetail id="inv-2" />);

    expect(screen.getByRole("heading", { name: "INV-2026-0002" })).toBeVisible();

    // Neither Issue nor Cancel buttons should exist
    expect(
      screen.queryByRole("button", { name: /issue invoice/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /cancel draft/i })
    ).not.toBeInTheDocument();

    // Cancellation restriction notice must be prominently displayed with accurate wording
    expect(screen.getByLabelText("cancellation-policy-notice")).toBeVisible();
    expect(
      screen.getByText("Cancellation not available for issued invoices")
    ).toBeVisible();
    expect(
      screen.getByText(
        /this screen does not support cancellation of an issued invoice/i
      )
    ).toBeVisible();
    expect(
      screen.getByText(
        /the appropriate correction workflow for issued invoices is not yet available in TaxPilot/i
      )
    ).toBeVisible();

    // Verify blanket or unsupported statements are absent
    expect(
      screen.queryByText(/legally irrevocable/i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/credit notes/i)
    ).not.toBeInTheDocument();
  });

  it("opens issuance dialog, displays accounting disclosures, and allows safe cancellation", async () => {
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /issue invoice/i }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /confirm invoice issuance/i })
    ).toBeVisible();
    expect(
      screen.getByText(
        /triggers the application's existing accounting and stock operations/i
      )
    ).toBeVisible();
    expect(screen.getByText(/inventory decrement/i)).toBeVisible();
    expect(screen.getByText(/general ledger postings/i)).toBeVisible();
    expect(
      screen.getByText(/Output Tax Payable \(2010\)/i)
    ).toBeVisible();
    expect(screen.getByText(/cancellation limitation/i)).toBeVisible();
    expect(
      screen.getByText(
        /the appropriate correction workflow for issued invoices is not yet available in TaxPilot/i
      )
    ).toBeVisible();

    // Verify broad legal claims and blanket irrevocable statements are absent
    expect(
      screen.queryByText(/irreversible financial action/i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/commits business and legal facts under GST/i)
    ).not.toBeInTheDocument();

    // Clicking Cancel closes dialog without dispatching mutation
    await user.click(screen.getByRole("button", { name: /cancel$/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mockIssueMutateAsync).not.toHaveBeenCalled();
  });

  it("confirms issuance, calls API, displays success toast, and refetches", async () => {
    mockIssueMutateAsync.mockResolvedValueOnce({
      ...draftInvoice,
      status: "issued",
    });
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /issue invoice/i }));
    await user.click(
      screen.getByRole("button", { name: /confirm & issue invoice/i })
    );

    await waitFor(() => {
      expect(mockIssueMutateAsync).toHaveBeenCalledWith("inv-1");
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Invoice INV-2026-0001 issued successfully"
    );
    expect(mockRefetch).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens draft cancellation dialog, displays policy details, and allows safe dismissal", async () => {
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /cancel draft/i }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /confirm draft cancellation/i })
    ).toBeVisible();
    expect(screen.getByText(/zero accounting impact/i)).toBeVisible();
    expect(screen.getByText(/cancellation restriction/i)).toBeVisible();
    expect(
      screen.getByText(
        /this screen does not support cancellation of an issued invoice/i
      )
    ).toBeVisible();

    // Clicking "Keep draft" closes dialog without dispatching mutation
    await user.click(screen.getByRole("button", { name: /keep draft/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mockCancelMutateAsync).not.toHaveBeenCalled();
  });

  it("confirms draft cancellation, calls API, displays toast, and refetches", async () => {
    mockCancelMutateAsync.mockResolvedValueOnce({
      ...draftInvoice,
      status: "cancelled",
    });
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /cancel draft/i }));
    await user.click(
      screen.getByRole("button", { name: /confirm cancellation/i })
    );

    await waitFor(() => {
      expect(mockCancelMutateAsync).toHaveBeenCalledWith("inv-1");
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Draft invoice INV-2026-0001 cancelled"
    );
    expect(mockRefetch).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("handles issuance failure with error toast and query refetch", async () => {
    mockIssueMutateAsync.mockRejectedValueOnce(
      new Error("Invoice already issued or in conflict")
    );
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /issue invoice/i }));
    await user.click(
      screen.getByRole("button", { name: /confirm & issue invoice/i })
    );

    await waitFor(() => {
      expect(mockIssueMutateAsync).toHaveBeenCalledWith("inv-1");
    });
    expect(toast.error).toHaveBeenCalledWith(
      "Invoice already issued or in conflict"
    );
    expect(mockRefetch).toHaveBeenCalled();
  });

  it("handles cancellation failure with error toast and query refetch", async () => {
    mockCancelMutateAsync.mockRejectedValueOnce(
      new Error("Only draft invoices can be cancelled")
    );
    const user = userEvent.setup();
    render(<InvoiceDetail id="inv-1" />);

    await user.click(screen.getByRole("button", { name: /cancel draft/i }));
    await user.click(
      screen.getByRole("button", { name: /confirm cancellation/i })
    );

    await waitFor(() => {
      expect(mockCancelMutateAsync).toHaveBeenCalledWith("inv-1");
    });
    expect(toast.error).toHaveBeenCalledWith(
      "Only draft invoices can be cancelled"
    );
    expect(mockRefetch).toHaveBeenCalled();
  });

  it("blocks display and alerts if invoice belongs to another business", () => {
    activeBusinessId = "b2"; // Different active business
    render(<InvoiceDetail id="inv-1" />);

    expect(screen.getByRole("alert")).toBeVisible();
    expect(screen.getByText(/invoice unavailable/i)).toBeVisible();
    expect(
      screen.getByText(/does not belong to the active business/i)
    ).toBeVisible();
    expect(screen.queryByText("INV-2026-0001")).not.toBeInTheDocument();
  });
});
