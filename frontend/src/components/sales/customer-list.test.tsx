import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CustomerList } from "./customer-list";

const mocks = vi.hoisted(() => ({ useCustomers: vi.fn() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/sales/customers", useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ activeBusinessId: "b1" }) }));
vi.mock("@/features/sales/hooks/use-sales", () => ({ useCustomers: mocks.useCustomers }));

describe("CustomerList", () => {
  beforeEach(() => mocks.useCustomers.mockReset());
  it("shows a loading state", () => { mocks.useCustomers.mockReturnValue({ isLoading: true }); render(<CustomerList />); expect(screen.getByLabelText("Loading sales data")).toBeVisible(); });
  it("shows an actionable empty state", () => { mocks.useCustomers.mockReturnValue({ isLoading: false, isError: false, data: { data: [], meta: { page: 1, size: 20, total: 0, pages: 0 } } }); render(<CustomerList />); expect(screen.getByRole("link", { name: /add your first customer/i })).toHaveAttribute("href", "/sales/customers/new"); });
  it("renders customer records without unavailable financial data", () => { mocks.useCustomers.mockReturnValue({ isLoading: false, isError: false, data: { data: [{ id: "c1", business_id: "b1", customer_code: "C-1", name: "Aarav Traders", email: null, phone: null, gstin: null, pan: null, billing_address: null, shipping_address: null, is_active: true }], meta: { page: 1, size: 20, total: 1, pages: 1 } } }); render(<CustomerList />); expect(screen.getByText("Aarav Traders")).toBeVisible(); expect(screen.queryByText(/outstanding/i)).not.toBeInTheDocument(); });
  it("shows a retryable error state", () => { mocks.useCustomers.mockReturnValue({ isLoading: false, isError: true, refetch: vi.fn() }); render(<CustomerList />); expect(screen.getByRole("alert")).toBeVisible(); });
});
