import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OpportunityCenter } from "./opportunity-center";
import { ApiClientError } from "@/lib/api/errors";

const useBusiness = vi.fn();
const useOpportunities = vi.fn();

vi.mock("@/contexts/business-context", () => ({ useBusiness: () => useBusiness() }));
vi.mock("../hooks/use-opportunities", () => ({ useOpportunities: (id: string | null) => useOpportunities(id) }));

function renderCenter() {
  return render(<QueryClientProvider client={new QueryClient()}><OpportunityCenter /></QueryClientProvider>);
}

describe("OpportunityCenter", () => {
  it("preserves owner-published collection order without adding an ordering", () => {
    useBusiness.mockReturnValue({ activeBusinessId: "business-1", status: "ready" });
    useOpportunities.mockReturnValue({ isLoading: false, isError: false, data: { data: [
      { opportunity_id: "2", business_id: "business-1", status: "eligible", assessment_time: "2026-08-17T00:00:00Z", opportunity_type: "growth", canonical_subject: "Second", policy_id: "p", policy_version: "1", eligibility_result: "eligible", source_references: [], evidence: [], limitations: [], input_traceability: [], provenance: "approved", temporal_context: "2026-08-17T00:00:00Z", unavailable_information: [] },
      { opportunity_id: "1", business_id: "business-1", status: "unavailable", assessment_time: "2026-08-17T00:00:00Z", opportunity_type: "growth", canonical_subject: "First", policy_id: "p", policy_version: "1", eligibility_result: "unavailable", source_references: [], evidence: [], limitations: ["Input unavailable"], input_traceability: [], provenance: "approved", temporal_context: "2026-08-17T00:00:00Z", unavailable_information: [{ source: "PublishedForecast", capability: "Business Health", reference_id: "input-1", field: "state", reason: "missing" }] },
    ] } });

    renderCenter();

    expect(screen.getAllByRole("article").map((item) => item.getAttribute("aria-label"))).toEqual(["Second", "First"]);
    expect(screen.getByText(/PublishedForecast \/ Business Health \/ state: missing/)).toBeVisible();
  });

  it("renders an honest absence state when no artifact is supplied", () => {
    useBusiness.mockReturnValue({ activeBusinessId: "business-1", status: "ready" });
    useOpportunities.mockReturnValue({ isLoading: false, isError: false, data: { data: [] } });

    renderCenter();

    expect(screen.getByText("No authoritative opportunities available")).toBeVisible();
  });

  it("withholds the experience when the business context is denied", () => {
    useBusiness.mockReturnValue({ activeBusinessId: "business-1", status: "ready" });
    useOpportunities.mockReturnValue({ isLoading: false, isError: true, error: new ApiClientError("Denied", 403) });

    renderCenter();

    expect(screen.getByText("Access unavailable")).toBeVisible();
  });
});
