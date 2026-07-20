import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SupplierDetail } from "./supplier-detail";

const mocks = vi.hoisted(() => ({ useSupplier: vi.fn(), deactivate: vi.fn(), reactivate: vi.fn(), refetch: vi.fn() }));
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ activeBusinessId: "b1" }) }));
vi.mock("@/features/purchases/hooks/use-purchases", () => ({ useSupplier: mocks.useSupplier, usePurchaseMutations: () => ({ deactivateSupplier: { mutateAsync: mocks.deactivate, isPending: false }, reactivateSupplier: { mutateAsync: mocks.reactivate, isPending: false } }) }));

const supplier = { id: "s1", business_id: "b1", supplier_code: "SUP-1", name: "Aarav Wholesale", email: "billing@example.com", phone: "+919876543210", payment_terms: "Net 30", gstin: "29ABCDE1234F1Z5", pan: "ABCDE1234F", address: "Bengaluru", is_active: true };
describe("SupplierDetail", () => {
  beforeEach(() => { mocks.deactivate.mockReset(); mocks.reactivate.mockReset(); mocks.refetch.mockReset(); });
  it("renders supplier details and archives through the verified mutation", async () => { mocks.deactivate.mockResolvedValue(undefined); mocks.refetch.mockResolvedValue(undefined); mocks.useSupplier.mockReturnValue({ isLoading: false, isError: false, data: supplier, refetch: mocks.refetch }); render(<SupplierDetail id="s1" />); expect(screen.getByText("29ABCDE1234F1Z5")).toBeVisible(); await userEvent.click(screen.getByRole("button", { name: "Archive" })); expect(mocks.deactivate).toHaveBeenCalledWith("s1"); });
  it("restores an archived supplier", async () => { mocks.reactivate.mockResolvedValue({ ...supplier, is_active: true }); mocks.refetch.mockResolvedValue(undefined); mocks.useSupplier.mockReturnValue({ isLoading: false, isError: false, data: { ...supplier, is_active: false }, refetch: mocks.refetch }); render(<SupplierDetail id="s1" />); await userEvent.click(screen.getByRole("button", { name: "Restore" })); expect(mocks.reactivate).toHaveBeenCalledWith("s1"); });
});
