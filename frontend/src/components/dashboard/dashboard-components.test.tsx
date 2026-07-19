import { render, screen } from "@testing-library/react";
import { TrendingUp, ReceiptText } from "lucide-react";
import { describe, expect, it } from "vitest";
import { MetricCard } from "./metric-card";
import { ChartCard } from "./chart-card";
import { RecentActivityCard } from "./recent-activity-card";
import { QuickActionsCard } from "./quick-actions-card";
describe("dashboard components", () => { it("marks unsupported metrics unavailable instead of showing zero", () => { render(<MetricCard label="Revenue" icon={TrendingUp} />); expect(screen.getByLabelText("Revenue: data unavailable")).toHaveTextContent("—"); expect(screen.queryByText("₹0")).not.toBeInTheDocument(); }); it("shows a truthful chart empty state", () => { render(<ChartCard title="Cash Flow" description="A cash-flow endpoint is not currently available." />); expect(screen.getByText("Trend data unavailable")).toBeVisible(); expect(screen.getByText(/cash-flow endpoint/i)).toBeVisible(); }); it("renders API-backed activity records", () => { render(<RecentActivityCard title="Recent Expenses" icon={ReceiptText} items={[{ id: "1", title: "EXP-001", subtitle: "18 Jul 2026", amount: "₹1,000.00", status: "paid" }]} />); expect(screen.getByText("EXP-001")).toBeVisible(); expect(screen.getByText("₹1,000.00")).toBeVisible(); }); it("keeps all unimplemented ERP actions disabled", () => { render(<QuickActionsCard />); for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled(); }); });
