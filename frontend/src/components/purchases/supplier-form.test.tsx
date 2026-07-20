import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SupplierForm } from "./supplier-form";

const mocks = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), push: vi.fn(), useSupplier: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push, back: vi.fn() }) }));
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ activeBusinessId: "b1" }) }));
vi.mock("@/features/purchases/hooks/use-purchases", () => ({ useSupplier: mocks.useSupplier, usePurchaseMutations: () => ({ createSupplier: { mutateAsync: mocks.create, isPending: false }, updateSupplier: { mutateAsync: mocks.update, isPending: false } }) }));

const supplier = { id: "s1", business_id: "b1", supplier_code: "SUP-1", name: "Aarav Wholesale", email: null, phone: null, gstin: null, pan: null, address: null, payment_terms: null, is_active: true };
describe("SupplierForm", () => {
  beforeEach(() => { mocks.create.mockReset(); mocks.update.mockReset(); mocks.push.mockReset(); mocks.useSupplier.mockReturnValue({ isLoading: false, isError: false, data: undefined }); });
  it("creates a valid supplier once", async () => { mocks.create.mockResolvedValue(supplier); render(<SupplierForm />); await userEvent.type(screen.getByLabelText("Supplier name"), "Aarav Wholesale"); await userEvent.click(screen.getByRole("button", { name: "Save supplier" })); await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1)); expect(mocks.create.mock.calls[0][0]).toMatchObject({ businessId: "b1", input: { name: "Aarav Wholesale", email: null } }); });
  it("loads and updates an existing supplier", async () => { mocks.useSupplier.mockReturnValue({ isLoading: false, isError: false, data: supplier }); mocks.update.mockResolvedValue({ ...supplier, name: "Aarav Wholesale India" }); render(<SupplierForm id="s1" />); const name = screen.getByLabelText("Supplier name"); await userEvent.clear(name); await userEvent.type(name, "Aarav Wholesale India"); await userEvent.click(screen.getByRole("button", { name: "Save supplier" })); await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(expect.objectContaining({ id: "s1", input: expect.objectContaining({ name: "Aarav Wholesale India" }) }))); });
});
