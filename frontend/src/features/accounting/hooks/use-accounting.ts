"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { accountingApi } from "../api/accounting-api";
import { accountingKeys } from "../api/accounting-query-keys";
import type {
  ChartOfAccountsFilter,
  GeneralLedgerFilter,
  TrialBalanceFilter,
} from "../types/accounting.types";

export const useChartOfAccounts = (
  businessId: string | null | undefined,
  filter?: ChartOfAccountsFilter
) =>
  useQuery({
    queryKey: accountingKeys.chartOfAccounts(businessId ?? "", filter),
    queryFn: () => accountingApi.chartOfAccounts(businessId!, filter),
    enabled: Boolean(businessId),
    placeholderData: keepPreviousData,
  });

export const useAccountDetail = (
  accountId: string | null | undefined,
  businessId: string | null | undefined
) =>
  useQuery({
    queryKey: accountingKeys.accountDetail(accountId ?? "", businessId ?? ""),
    queryFn: () => accountingApi.accountDetail(accountId!, businessId!),
    enabled: Boolean(accountId && businessId),
  });

export const useGeneralLedger = (
  businessId: string | null | undefined,
  filter?: GeneralLedgerFilter
) =>
  useQuery({
    queryKey: accountingKeys.generalLedger(businessId ?? "", filter),
    queryFn: () => accountingApi.generalLedger(businessId!, filter),
    enabled: Boolean(businessId),
    placeholderData: keepPreviousData,
  });

export const useTrialBalance = (
  businessId: string | null | undefined,
  filter?: TrialBalanceFilter
) =>
  useQuery({
    queryKey: accountingKeys.trialBalance(businessId ?? "", filter),
    queryFn: () => accountingApi.trialBalance(businessId!, filter),
    enabled: Boolean(businessId),
    placeholderData: keepPreviousData,
  });
