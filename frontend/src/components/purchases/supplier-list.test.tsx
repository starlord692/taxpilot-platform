import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SupplierList } from "./supplier-list";

const mocks = vi.hoisted(() => ({ useSuppliers: vi.fn() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/purchases/suppliers", useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ activeBusinessId: "b1" }) }));
vi.mock("@/features/purchases/hooks/use-purchases", () => ({ useSuppliers: mocks.useSuppliers }));

describe("SupplierList", () => {
  beforeEach(() => mocks.useSuppliers.mockReset());
  it("shows loading and error states", () => { mocks.useSuppliers.mockReturnValue({ isLoading: true }); const { rerender } = render(<SupplierList />); expect(screen.getByLabelText("Loading purchases")).toBeVisible(); mocks.useSuppliers.mockReturnValue({ isLoading: false, isError: true, refetch: vi.fn() }); rerender(<SupplierList />); expect(screen.getByRole("alert")).toBeVisible(); });
  it("shows an actionable empty state", () => { mocks.useSuppliers.mockReturnValue({ isLoading: false, isError: false, data: { data: [], meta: { page: 1, size: 20, total: 0, pages: 0 } } }); render(<SupplierList />); expect(screen.getByRole("link", { name: /add your first supplier/i })).toHaveAttribute("href", "/purchases/suppliers/new"); });
  it("renders supplier records", () => { mocks.useSuppliers.mockReturnValue({ isLoading: false, isError: false, data: { data: [{ id: "s1", business_id: "b1", supplier_code: "SUP-1", name: "Aarav Wholesale", email: null, phone: null, payment_terms: "Net 30", is_active: true }], meta: { page: 1, size: 20, total: 1, pages: 1 } } }); render(<SupplierList />); expect(screen.getByText("Aarav Wholesale")).toBeVisible(); expect(screen.getByText(/GSTIN is available on supplier details/)).toBeVisible(); });
});
