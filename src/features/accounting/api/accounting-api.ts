import { apiClient } from "@/lib/api/client";
import type {
  ChartAccount,
  ChartOfAccountsFilter,
  GeneralLedgerEntry,
  GeneralLedgerFilter,
  PaginatedEnvelope,
  SuccessEnvelope,
  TrialBalance,
  TrialBalanceFilter,
} from "../types/accounting.types";
import { isPreviewMode } from "@/lib/env";

export const accountingApi = {
  async chartOfAccounts(businessId: string, filter?: ChartOfAccountsFilter) {
    if (isPreviewMode) {
      return {
        success: true,
        message: "Preview mode",
        data: [],
      } satisfies SuccessEnvelope<ChartAccount[]>;
    }
    const response = await apiClient.get<SuccessEnvelope<ChartAccount[]>>(
      "/accounting/chart-of-accounts",
      {
        params: {
          business_id: businessId,
          category: filter?.category || undefined,
          is_active: filter?.is_active,
          search: filter?.search || undefined,
        },
      }
    );
    return response.data;
  },

  async accountDetail(accountId: string, businessId: string) {
    const response = await apiClient.get<SuccessEnvelope<ChartAccount>>(
      `/accounting/chart-of-accounts/${accountId}`,
      {
        params: { business_id: businessId },
      }
    );
    return response.data.data;
  },

  async generalLedger(businessId: string, filter?: GeneralLedgerFilter) {
    if (isPreviewMode) {
      return {
        success: true,
        message: "Preview mode",
        data: [],
        meta: { page: filter?.page ?? 1, size: filter?.size ?? 20, total: 0, pages: 0 },
      } satisfies PaginatedEnvelope<GeneralLedgerEntry>;
    }
    const response = await apiClient.get<PaginatedEnvelope<GeneralLedgerEntry>>(
      "/accounting/general-ledger",
      {
        params: {
          business_id: businessId,
          account_id: filter?.account_id || undefined,
          account_code: filter?.account_code || undefined,
          date_from: filter?.date_from || undefined,
          date_to: filter?.date_to || undefined,
          source_module: filter?.source_module || undefined,
          page: filter?.page ?? 1,
          size: filter?.size ?? 20,
        },
      }
    );
    return response.data;
  },

  async trialBalance(businessId: string, filter?: TrialBalanceFilter) {
    if (isPreviewMode) {
      return {
        success: true,
        message: "Preview mode",
        data: {
          business_id: businessId,
          generated_at: new Date().toISOString(),
          as_of_date: filter?.as_of_date || new Date().toISOString().split("T")[0],
          total_debit: "0.00",
          total_credit: "0.00",
          discrepancy: "0.00",
          is_balanced: true,
          historical_mode: "ledger_derived_cumulative",
          opening_balances_present: false,
          fiscal_period_closed: false,
          reporting_limitations: [],
          accounts: [],
        },
      } satisfies SuccessEnvelope<TrialBalance>;
    }
    const response = await apiClient.get<SuccessEnvelope<TrialBalance>>(
      "/accounting/trial-balance",
      {
        params: {
          business_id: businessId,
          as_of_date: filter?.as_of_date || undefined,
          include_zero_balances: filter?.include_zero_balances ?? false,
        },
      }
    );
    return response.data;
  },
};
