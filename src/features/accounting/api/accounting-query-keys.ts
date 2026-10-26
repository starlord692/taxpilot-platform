import type {
  ChartOfAccountsFilter,
  GeneralLedgerFilter,
  TrialBalanceFilter,
} from "../types/accounting.types";

export const accountingKeys = {
  all: ["accounting"] as const,
  chartOfAccounts: (businessId: string, filter?: ChartOfAccountsFilter) =>
    [...accountingKeys.all, "chart-of-accounts", businessId, filter] as const,
  accountDetail: (accountId: string, businessId: string) =>
    [...accountingKeys.all, "account-detail", accountId, businessId] as const,
  generalLedger: (businessId: string, filter?: GeneralLedgerFilter) =>
    [...accountingKeys.all, "general-ledger", businessId, filter] as const,
  trialBalance: (businessId: string, filter?: TrialBalanceFilter) =>
    [...accountingKeys.all, "trial-balance", businessId, filter] as const,
};
