import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BusinessSwitcher } from "./business-switcher";
const selectBusiness = vi.fn();
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ businesses: [{ id: "b1", legal_name: "One Ltd", trade_name: "One" }, { id: "b2", legal_name: "Two Ltd", trade_name: "Two" }], activeBusiness: null, activeBusinessId: null, status: "selection-required", selectBusiness }) }));
describe("BusinessSwitcher", () => { it("requires explicit choice for multiple businesses", async () => { const user = userEvent.setup(); render(<BusinessSwitcher />); const select = screen.getByLabelText("Active business"); await user.selectOptions(select, "b2"); expect(selectBusiness).toHaveBeenCalledWith("b2"); }); });
