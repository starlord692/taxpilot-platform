import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChartOfAccountsTable } from "./chart-of-accounts-table";
import { GeneralLedgerTable } from "./general-ledger-table";
import { TrialBalanceView } from "./trial-balance-view";
import { AccountingShell } from "./accounting-shell";
import type {
  ChartAccount,
  GeneralLedgerEntry,
  TrialBalance,
} from "../types/accounting.types";

// State trackers for mock hooks
let activeBusinessId: string | null = "b1";
let searchParamsMock: Record<string, string> = {};
let currentPathname = "/accounting/chart-of-accounts";

let chartData: { data: ChartAccount[] } | undefined = undefined;
let isChartLoading = false;
let isChartError = false;
const mockChartRefetch = vi.fn();

let glData: {
  data: GeneralLedgerEntry[];
  meta: { page: number; size: number; total: number; pages: number };
} | undefined = undefined;
let isGlLoading = false;
let isGlError = false;
const mockGlRefetch = vi.fn();

let tbData: { data: TrialBalance } | undefined = undefined;
let isTbLoading = false;
let isTbError = false;
const mockTbRefetch = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
  useSearchParams: () => ({
    get: (key: string) => searchParamsMock[key] || null,
  }),
}));

vi.mock("@/contexts/business-context", () => ({
  useBusiness: () => ({
    activeBusinessId,
    businesses: [
      { id: "b1", name: "Alpha Technologies" },
      { id: "b2", name: "Beta Enterprises" },
    ],
  }),
}));

vi.mock("@/components/business/business-route-shell", () => ({
  BusinessRouteShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="business-route-shell">{children}</div>
  ),
}));

vi.mock("@/components/business/business-switcher", () => ({
  BusinessSwitcher: () => <div data-testid="business-switcher">Switcher</div>,
}));

vi.mock("../hooks/use-accounting", () => ({
  useChartOfAccounts: () => ({
    data: chartData,
    isLoading: isChartLoading,
    isError: isChartError,
    refetch: mockChartRefetch,
  }),
  useGeneralLedger: () => ({
    data: glData,
    isLoading: isGlLoading,
    isError: isGlError,
    refetch: mockGlRefetch,
  }),
  useTrialBalance: () => ({
    data: tbData,
    isLoading: isTbLoading,
    isError: isTbError,
    refetch: mockTbRefetch,
  }),
}));

describe("Accounting Inspection Components", () => {
  beforeEach(() => {
    activeBusinessId = "b1";
    searchParamsMock = {};
    currentPathname = "/accounting/chart-of-accounts";
    isChartLoading = false;
    isChartError = false;
    isGlLoading = false;
    isGlError = false;
    isTbLoading = false;
    isTbError = false;
    vi.clearAllMocks();
  });

  describe("ChartOfAccountsTable", () => {
    it("renders unselected business prompt when activeBusinessId is missing", () => {
      activeBusinessId = null;
      render(<ChartOfAccountsTable />);
      expect(
        screen.getByText("Select a business to inspect the Chart of Accounts.")
      ).toBeVisible();
    });

    it("renders loading skeleton when loading", () => {
      isChartLoading = true;
      const { container } = render(<ChartOfAccountsTable />);
      expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    });

    it("renders error state with retry action", async () => {
      isChartError = true;
      render(<ChartOfAccountsTable />);
      expect(screen.getByText("Failed to load Chart of Accounts.")).toBeVisible();
      const retryBtn = screen.getByRole("button", { name: /retry/i });
      fireEvent.click(retryBtn);
      expect(mockChartRefetch).toHaveBeenCalled();
    });

    it("renders empty state when no accounts exist", () => {
      chartData = { data: [] };
      render(<ChartOfAccountsTable />);
      expect(screen.getByText("No accounts found")).toBeVisible();
      expect(
        screen.getByText("No chart accounts match the selected filters for this business.")
      ).toBeVisible();
    });

    it("renders account rows with codes, names, categories, and balances", () => {
      chartData = {
        data: [
          {
            id: "acc-1000",
            account_code: "1000",
            account_name: "Cash on Hand",
            category_name: "Asset",
            account_type_name: "Current Asset",
            normal_balance: "debit",
            current_debit: "25000.00",
            current_credit: "0.00",
            current_balance: "25000.00",
            is_system: true,
            is_active: true,
            parent_account_id: null,
            description: "Main petty cash drawer",
          },
          {
            id: "acc-2000",
            account_code: "2000",
            account_name: "Accounts Payable",
            category_name: "Liability",
            account_type_name: "Current Liability",
            normal_balance: "credit",
            current_debit: "0.00",
            current_credit: "12000.00",
            current_balance: "12000.00",
            is_system: true,
            is_active: false,
            parent_account_id: null,
            description: null,
          },
        ],
      };

      render(<ChartOfAccountsTable />);

      expect(screen.getByText("1000")).toBeVisible();
      expect(screen.getByText("Cash on Hand")).toBeVisible();
      expect(screen.getByText("Main petty cash drawer")).toBeVisible();
      // "Asset" and "Liability" appear in category select options as well
      expect(screen.getAllByText("Asset").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("2000")).toBeVisible();
      expect(screen.getByText("Accounts Payable")).toBeVisible();
      expect(screen.getAllByText("Liability").length).toBeGreaterThanOrEqual(1);

      expect(screen.getByText("Active")).toBeVisible();
      expect(screen.getByText("Inactive")).toBeVisible();

      const viewGlLinks = screen.getAllByRole("link", { name: /view gl/i });
      expect(viewGlLinks).toHaveLength(2);
      expect(viewGlLinks[0]).toHaveAttribute(
        "href",
        "/accounting/general-ledger?account_id=acc-1000"
      );
    });

    it("allows searching and category filtering", async () => {
      const user = userEvent.setup();
      chartData = { data: [] };
      render(<ChartOfAccountsTable />);

      const searchInput = screen.getByPlaceholderText("Search code or name...");
      await user.type(searchInput, "Cash");
      expect(searchInput).toHaveValue("Cash");

      const categorySelect = screen.getByDisplayValue("All Categories");
      await user.selectOptions(categorySelect, "Asset");
      expect(categorySelect).toHaveValue("Asset");
    });
  });

  describe("GeneralLedgerTable", () => {
    it("renders unselected business prompt when activeBusinessId is missing", () => {
      activeBusinessId = null;
      render(<GeneralLedgerTable />);
      expect(
        screen.getByText("Select a business to inspect the General Ledger.")
      ).toBeVisible();
    });

    it("renders loading state when fetching ledger entries", () => {
      isGlLoading = true;
      const { container } = render(<GeneralLedgerTable />);
      expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    });

    it("renders error state with retry button", () => {
      isGlError = true;
      render(<GeneralLedgerTable />);
      expect(screen.getByText("Failed to load General Ledger entries.")).toBeVisible();
      const retryBtn = screen.getByRole("button", { name: /retry/i });
      fireEvent.click(retryBtn);
      expect(mockGlRefetch).toHaveBeenCalled();
    });

    it("renders empty state when no entries exist", () => {
      glData = {
        data: [],
        meta: { page: 1, size: 20, total: 0, pages: 0 },
      };
      render(<GeneralLedgerTable />);
      expect(screen.getByText("No ledger entries recorded")).toBeVisible();
    });

    it("renders multi-account view without running balance column by default", () => {
      glData = {
        data: [
          {
            id: "gle-1",
            transaction_date: "2026-10-15",
            posting_date: "2026-10-15T10:00:00Z",
            journal_entry_id: "je-1",
            journal_number: "JE-2026-0001",
            journal_reference: "INV-001",
            account_id: "acc-1000",
            account_code: "1000",
            account_name: "Cash",
            debit: "5000.00",
            credit: "0.00",
            running_balance: "5000.00",
            description: "Invoice payment received",
            source_module: "sales",
            source_entity: "sales_invoice",
            source_entity_id: "inv-1",
            source_document_url: "/sales/invoices/inv-1",
          },
        ],
        meta: { page: 1, size: 20, total: 1, pages: 1 },
      };

      render(<GeneralLedgerTable />);

      expect(screen.getByText("JE-2026-0001")).toBeVisible();
      expect(screen.getByText("Invoice payment received")).toBeVisible();
      expect(screen.getByText("Cash")).toBeVisible();
      // Multi-account view should NOT display the Running Balance header
      expect(screen.queryByText("Running Balance")).not.toBeInTheDocument();

      // Source document link
      const sourceLink = screen.getByRole("link", { name: /sales invoice/i });
      expect(sourceLink).toHaveAttribute("href", "/sales/invoices/inv-1");
    });

    it("renders running balance column when single account is selected via query param", () => {
      searchParamsMock = { account_id: "acc-1000" };
      glData = {
        data: [
          {
            id: "gle-1",
            transaction_date: "2026-10-15",
            posting_date: "2026-10-15T10:00:00Z",
            journal_entry_id: "je-1",
            journal_number: "JE-2026-0001",
            journal_reference: "INV-001",
            account_id: "acc-1000",
            account_code: "1000",
            account_name: "Cash",
            debit: "5000.00",
            credit: "0.00",
            running_balance: "5000.00",
            description: "Opening cash receipt",
            source_module: "sales",
            source_entity: "sales_invoice",
            source_entity_id: "inv-1",
            source_document_url: "/sales/invoices/inv-1",
          },
        ],
        meta: { page: 1, size: 20, total: 1, pages: 1 },
      };

      render(<GeneralLedgerTable />);
      // Single-account view MUST display the Running Balance header and value
      expect(screen.getByText("Running Balance")).toBeVisible();
    });

    it("displays pagination controls and entry counts", () => {
      glData = {
        data: [
          {
            id: "gle-1",
            transaction_date: "2026-10-15",
            posting_date: "2026-10-15T10:00:00Z",
            journal_entry_id: "je-1",
            journal_number: "JE-2026-0001",
            journal_reference: "INV-001",
            account_id: "acc-1000",
            account_code: "1000",
            account_name: "Cash",
            debit: "5000.00",
            credit: "0.00",
            running_balance: null,
            description: "Opening cash receipt",
            source_module: "sales",
            source_entity: "sales_invoice",
            source_entity_id: "inv-1",
            source_document_url: null,
          },
        ],
        meta: { page: 1, size: 20, total: 55, pages: 3 },
      };
      render(<GeneralLedgerTable />);
      expect(screen.getByText(/Showing 1–20 of 55 entries/)).toBeVisible();
      expect(screen.getByText("Page 1 of 3")).toBeVisible();
      const prevBtn = screen.getByRole("button", { name: /previous/i });
      const nextBtn = screen.getByRole("button", { name: /next/i });
      expect(prevBtn).toBeDisabled();
      expect(nextBtn).toBeEnabled();
    });
  });

  describe("TrialBalanceView", () => {
    it("renders unselected business prompt when activeBusinessId is missing", () => {
      activeBusinessId = null;
      render(<TrialBalanceView />);
      expect(
        screen.getByText("Select a business to inspect the Trial Balance.")
      ).toBeVisible();
    });

    it("renders loading state", () => {
      isTbLoading = true;
      const { container } = render(<TrialBalanceView />);
      expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    });

    it("renders error state with retry", () => {
      isTbError = true;
      render(<TrialBalanceView />);
      expect(screen.getByText("Failed to generate Trial Balance.")).toBeVisible();
      const retryBtn = screen.getByRole("button", { name: /retry/i });
      fireEvent.click(retryBtn);
      expect(mockTbRefetch).toHaveBeenCalled();
    });

    it("renders balanced reconciliation banner and reporting disclosure banner", () => {
      tbData = {
        data: {
          business_id: "b1",
          generated_at: "2026-10-24T00:00:00Z",
          as_of_date: "2026-10-24",
          total_debit: "50000.00",
          total_credit: "50000.00",
          discrepancy: "0.00",
          is_balanced: true,
          historical_mode: "ledger_derived_cumulative",
          opening_balances_present: false,
          fiscal_period_closed: false,
          reporting_limitations: ["Notice"],
          accounts: [
            {
              account_id: "acc-1000",
              account_code: "1000",
              account_name: "Cash",
              account_category: "Asset",
              account_type: "Current Asset",
              normal_balance: "debit",
              debit: "50000.00",
              credit: "0.00",
              balance: "50000.00",
            },
            {
              account_id: "acc-3000",
              account_code: "3000",
              account_name: "Owner Equity",
              account_category: "Equity",
              account_type: "Equity",
              normal_balance: "credit",
              debit: "0.00",
              credit: "50000.00",
              balance: "50000.00",
            },
          ],
        },
      };

      render(<TrialBalanceView />);

      // Balanced banner
      expect(
        screen.getByText(/LEDGER RECONCILIATION: Total Debits equal Total Credits/)
      ).toBeVisible();
      expect(
        screen.getByText(/Net discrepancy is ₹0.00 under defined double-entry ledger calculation./)
      ).toBeVisible();

      // Disclosure banner
      expect(
        screen.getByText("REPORTING DISCLOSURE: Cumulative Ledger-Derived Balances")
      ).toBeVisible();

      // Table accounts
      expect(screen.getByText("1000")).toBeVisible();
      expect(screen.getByText("Cash")).toBeVisible();
      expect(screen.getByText("3000")).toBeVisible();
      expect(screen.getByText("Owner Equity")).toBeVisible();

      // Totals in footer
      expect(screen.getByText("TOTALS")).toBeVisible();
      expect(screen.getByText("NET DISCREPANCY")).toBeVisible();

      // Audit boundary statement
      expect(screen.getByText("Audit & Certification Boundaries")).toBeVisible();
    });

    it("renders critical warning banner when trial balance is unbalanced", () => {
      tbData = {
        data: {
          business_id: "b1",
          generated_at: "2026-10-24T00:00:00Z",
          as_of_date: "2026-10-24",
          total_debit: "50000.00",
          total_credit: "48000.00",
          discrepancy: "2000.00",
          is_balanced: false,
          historical_mode: "ledger_derived_cumulative",
          opening_balances_present: true,
          fiscal_period_closed: true,
          reporting_limitations: [],
          accounts: [],
        },
      };

      render(<TrialBalanceView />);

      expect(
        screen.getByText(/CRITICAL INVARIANT WARNING/)
      ).toBeVisible();
      expect(screen.getByText(/Contact technical support/)).toBeVisible();
    });
  });

  describe("AccountingShell", () => {
    it("renders header, description, and navigation tabs", () => {
      render(
        <AccountingShell>
          <div data-testid="child-content">Content</div>
        </AccountingShell>
      );

      expect(screen.getByText("Accounting")).toBeVisible();
      expect(screen.getByText("Financial System of Record")).toBeVisible();
      expect(
        screen.getByText(
          "Deterministic double-entry inspection, chart of accounts, and ledger reconciliation."
        )
      ).toBeVisible();

      expect(screen.getByRole("link", { name: /chart of accounts/i })).toBeVisible();
      expect(screen.getByRole("link", { name: /general ledger/i })).toBeVisible();
      expect(screen.getByRole("link", { name: /trial balance/i })).toBeVisible();
      expect(screen.getByTestId("child-content")).toBeVisible();
    });
  });
});
