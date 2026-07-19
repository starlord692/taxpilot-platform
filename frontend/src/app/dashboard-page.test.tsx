import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BusinessWorkspacePage from "./page";

vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ user: { first_name: "Jane" }, isAuthenticated: true }) }));
vi.mock("@/features/dashboard/hooks/use-dashboard-view-model", () => ({ useDashboardViewModel: () => ({
  context: { contextStatus: "ready" },
  business: { id: "b1", legal_name: "TaxPilot Labs", trade_name: "TaxPilot", business_type: "private_limited", status: "active" },
  gst: { data: { data: [] }, isLoading: false, isError: false },
  activity: { expenses: { data: { data: [] }, isLoading: false, isError: false, refetch: vi.fn() }, purchases: { data: { data: [] }, isLoading: false, isError: false, refetch: vi.fn() } },
  pendingReviews: { data: { data: [], meta: { page: 1, size: 5, total: 3, pages: 1 } }, isLoading: false, isError: false },
  health: { data: { data: { status: "UP", version: "1.0.0" } }, isLoading: false }, lastSync: 1_752_800_000_000,
}) }));

describe("business workspace page", () => {
  it("renders verified workspace signals without fabricated financial values", () => {
    render(<BusinessWorkspacePage />);
    expect(screen.getByRole("heading", { name: /welcome back, jane/i })).toBeVisible();
    expect(screen.getByText(/TaxPilot ·/)).toBeVisible();
    expect(screen.getAllByLabelText(/data unavailable/)).toHaveLength(6);
    expect(screen.queryByText("₹0")).not.toBeInTheDocument();
    expect(screen.getByText(/3 documents require review/i)).toBeVisible();
    expect(screen.getByText(/3 pending reviews/i)).toBeVisible();
    expect(screen.getByText("Assessment unavailable")).toBeVisible();
  });
});
