import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReceiptText, TrendingUp } from "lucide-react";
import { ChartCard } from "./chart-card";
import { MetricCard } from "./metric-card";
import { QuickActionsCard } from "./quick-actions-card";
import { RecentActivityCard } from "./recent-activity-card";

describe("workspace components", () => {
  it("marks unsupported metrics unavailable instead of showing zero", () => { render(<MetricCard label="Sales" icon={TrendingUp} />); expect(screen.getByLabelText("Sales: data unavailable")).toHaveTextContent("—"); expect(screen.queryByText("₹0")).not.toBeInTheDocument(); });
  it("shows a truthful chart empty state", () => { render(<ChartCard title="Cash Flow" description="A cash-flow endpoint is not currently available." />); expect(screen.getByText("Trend data unavailable")).toBeVisible(); });
  it("renders API-backed activity records", () => { render(<RecentActivityCard title="Recent Expenses" icon={ReceiptText} items={[{ id: "1", title: "EXP-001", subtitle: "18 Jul 2026", amount: "₹1,000.00", status: "paid" }]} />); expect(screen.getByText("EXP-001")).toBeVisible(); expect(screen.getByText("₹1,000.00")).toBeVisible(); });
  it("links quick actions to existing workflows", () => { render(<QuickActionsCard />); expect(screen.getByRole("link", { name: /upload document/i })).toHaveAttribute("href", "/documents/upload"); expect(screen.getByRole("link", { name: /record expense/i })).toHaveAttribute("href", "/expenses/new"); expect(screen.getByRole("link", { name: /create purchase/i })).toHaveAttribute("href", "/purchases/invoices/new"); });
});
