import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InvoiceForm, calculateInvoiceTotals, calculateLinePreview } from "./invoice-form";

const mockPush = vi.fn();
const mockBack = vi.fn();
const mockMutateAsync = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    back: mockBack,
  }),
}));

vi.mock("@/contexts/business-context", () => ({
  useBusiness: () => ({
    activeBusinessId: "b1",
    businesses: [{ id: "b1", name: "Acme Corp" }],
  }),
}));

const mockCustomers = [
  {
    id: "c1",
    business_id: "b1",
    customer_code: "CUST-0001",
    name: "Aarav Enterprises",
    is_active: true,
  },
  {
    id: "c2",
    business_id: "b1",
    customer_code: "CUST-0002",
    name: "Beta Solutions",
    is_active: false,
  },
];

vi.mock("@/features/sales/hooks/use-sales", () => ({
  useCustomers: () => ({
    data: { data: mockCustomers },
    isLoading: false,
    isError: false,
  }),
  useSalesMutations: () => ({
    createInvoice: {
      mutateAsync: mockMutateAsync,
      isPending: false,
    },
  }),
}));

const mockCatalogItems = [
  {
    id: "cat-1",
    business_id: "b1",
    name: "Consulting Service",
    code: "SRV-001",
    item_type: "SERVICE",
    status: "ACTIVE",
    hsn_sac_code: "998311",
    tax_rate: 18,
    base_price: 1000,
    unit: "HOUR",
    description: "IT Consulting",
    inventory_profile: null,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
  },
  {
    id: "cat-2",
    business_id: "b1",
    name: "Widget Pro",
    code: "WGT-001",
    item_type: "PRODUCT",
    status: "ACTIVE",
    hsn_sac_code: "847130",
    tax_rate: 18,
    base_price: 500,
    unit: "PCS",
    description: "Physical Widget",
    inventory_profile: {
      stock_tracking: true,
      legacy_product_id: "prod-1",
      default_warehouse_id: "wh-1",
      reorder_point: 10,
      safety_stock: 5,
    },
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
  },
];

const mockWarehouses = [
  {
    id: "wh-1",
    business_id: "b1",
    code: "WH-BLR",
    name: "Bangalore Main",
    is_active: true,
  },
];

vi.mock("@/features/catalog/hooks/use-catalog", () => ({
  useCatalogItems: () => ({
    data: mockCatalogItems,
    isLoading: false,
    isError: false,
  }),
  useCatalogItem: () => ({
    data: mockCatalogItems[0],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/inventory/hooks/use-inventory", () => ({
  useWarehouses: () => ({
    data: { data: mockWarehouses },
    isLoading: false,
    isError: false,
  }),
}));

describe("InvoiceForm component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calculates line preview and invoice totals deterministically", () => {
    const line = {
      quantity: 2,
      unit_price: 500,
      discount: 50,
      tax_rate: 18,
    };
    const preview = calculateLinePreview(line);
    expect(preview.gross).toBe(1000);
    expect(preview.discount).toBe(50);
    expect(preview.taxable).toBe(950);
    expect(preview.tax).toBe(171);
    expect(preview.cgst).toBe(85.5);
    expect(preview.sgst).toBe(85.5);
    expect(preview.lineTotal).toBe(1121);

    const totals = calculateInvoiceTotals([line]);
    expect(totals.subtotal).toBe(1000);
    expect(totals.discount_amount).toBe(50);
    expect(totals.taxable_amount).toBe(950);
    expect(totals.tax_amount).toBe(171);
    expect(totals.total_amount).toBe(1121);
  });

  it("renders form fields and active customers only", () => {
    render(<InvoiceForm />);

    expect(screen.getByRole("heading", { name: /new sales invoice/i })).toBeVisible();
    expect(screen.getByLabelText(/select customer/i)).toBeVisible();
    expect(screen.getByText("Aarav Enterprises (CUST-0001)")).toBeVisible();
    // Inactive customer must not be listed
    expect(screen.queryByText("Beta Solutions (CUST-0002)")).not.toBeInTheDocument();

    expect(screen.getByLabelText(/invoice number/i)).toBeVisible();
    expect(screen.getByLabelText(/invoice date/i)).toBeVisible();
    expect(screen.getByLabelText(/due date/i)).toBeVisible();
    expect(screen.getByLabelText(/line 1 description/i)).toBeVisible();
    expect(screen.getByLabelText(/line 1 quantity/i)).toBeVisible();
    expect(screen.getByLabelText(/line 1 unit price/i)).toBeVisible();
  });

  it("allows adding and removing line items", async () => {
    const user = userEvent.setup();
    render(<InvoiceForm />);

    // Initially one line item
    expect(screen.getByLabelText(/line 1 description/i)).toBeVisible();
    expect(screen.queryByLabelText(/line 2 description/i)).not.toBeInTheDocument();

    // The single line remove button should be disabled
    expect(screen.getByLabelText(/remove line 1/i)).toBeDisabled();

    // Click Add line item
    await user.click(screen.getByRole("button", { name: /add line item/i }));

    // Now two line items exist
    expect(screen.getByLabelText(/line 2 description/i)).toBeVisible();
    expect(screen.getByLabelText(/remove line 1/i)).not.toBeDisabled();
    expect(screen.getByLabelText(/remove line 2/i)).not.toBeDisabled();

    // Remove line 2
    await user.click(screen.getByLabelText(/remove line 2/i));
    expect(screen.queryByLabelText(/line 2 description/i)).not.toBeInTheDocument();
  });

  it("displays validation error when required fields are missing", async () => {
    const user = userEvent.setup();
    render(<InvoiceForm />);

    // Attempt to submit without customer or description
    await user.click(screen.getByRole("button", { name: /save draft invoice/i }));

    expect(await screen.findByText("Customer is required")).toBeVisible();
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("submits valid invoice payload and navigates on success", async () => {
    mockMutateAsync.mockResolvedValueOnce({ id: "inv-created-999" });
    const user = userEvent.setup();
    render(<InvoiceForm />);

    // Fill customer
    await user.selectOptions(screen.getByLabelText(/select customer/i), "c1");

    // Fill invoice number
    const numberInput = screen.getByLabelText(/invoice number/i);
    await user.clear(numberInput);
    await user.type(numberInput, "INV-2026-0042");

    // Fill line description
    await user.type(screen.getByLabelText(/line 1 description/i), "Monthly retainer");

    // Fill quantity and price
    const qtyInput = screen.getByLabelText(/line 1 quantity/i);
    await user.clear(qtyInput);
    await user.type(qtyInput, "2");

    const priceInput = screen.getByLabelText(/line 1 unit price/i);
    await user.clear(priceInput);
    await user.type(priceInput, "1000");

    // Submit form
    await user.click(screen.getByRole("button", { name: /save draft invoice/i }));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    });

    const callPayload = mockMutateAsync.mock.calls[0][0];
    expect(callPayload.business_id).toBe("b1");
    expect(callPayload.customer_id).toBe("c1");
    expect(callPayload.invoice_number).toBe("INV-2026-0042");
    expect(callPayload.status).toBe("draft");
    expect(callPayload.subtotal).toBe(2000);
    expect(callPayload.taxable_amount).toBe(2000);
    expect(callPayload.lines[0].description).toBe("Monthly retainer");
    expect(callPayload.lines[0].quantity).toBe(2);
    expect(callPayload.lines[0].unit_price).toBe(1000);

    expect(mockPush).toHaveBeenCalledWith("/sales/invoices/inv-created-999");
  });

  it("autofills description, unit price, tax rate, and warehouse when selecting a catalog item", async () => {
    const user = userEvent.setup();
    render(<InvoiceForm />);

    expect(screen.getByLabelText(/line 1 catalog item/i)).toBeVisible();

    // Select stock-tracked item Widget Pro
    await user.selectOptions(screen.getByLabelText(/line 1 catalog item/i), "cat-2");

    expect(screen.getByLabelText(/line 1 description/i)).toHaveValue("Widget Pro");
    expect(screen.getByLabelText(/line 1 unit price/i)).toHaveValue(500);
    expect(screen.getByLabelText(/line 1 tax rate/i)).toHaveValue("18");

    // Warehouse selector should appear for stock-tracked item
    expect(screen.getByLabelText(/line 1 warehouse/i)).toBeVisible();
    expect(screen.getByLabelText(/line 1 warehouse/i)).toHaveValue("wh-1");
  });
});
