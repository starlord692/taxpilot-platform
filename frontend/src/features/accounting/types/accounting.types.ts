export type PaginatedEnvelope<T> = {
  success: boolean;
  message: string;
  data: T[];
  meta: {
    page: number;
    size: number;
    total: number;
    pages: number;
  };
};

export type SuccessEnvelope<T> = {
  success: boolean;
  message: string;
  data: T;
};

export type ChartAccount = {
  id: string;
  account_code: string;
  account_name: string;
  category_name: string;
  account_type_name: string;
  normal_balance: "debit" | "credit";
  current_debit: string | number;
  current_credit: string | number;
  current_balance: string | number;
  is_system: boolean;
  is_active: boolean;
  parent_account_id: string | null;
  description: string | null;
};

export type GeneralLedgerEntry = {
  id: string;
  transaction_date: string;
  posting_date: string;
  journal_entry_id: string;
  journal_number: string;
  journal_reference: string | null;
  account_id: string;
  account_code: string;
  account_name: string;
  debit: string | number;
  credit: string | number;
  running_balance: string | number | null;
  description: string | null;
  source_module: string | null;
  source_entity: string | null;
  source_entity_id: string | null;
  source_document_url: string | null;
};

export type TrialBalanceAccount = {
  account_id: string;
  account_code: string;
  account_name: string;
  account_category: string;
  account_type: string;
  normal_balance: "debit" | "credit";
  debit: string | number;
  credit: string | number;
  balance: string | number;
};

export type TrialBalance = {
  business_id: string;
  generated_at: string;
  as_of_date: string;
  total_debit: string | number;
  total_credit: string | number;
  discrepancy: string | number;
  is_balanced: boolean;
  historical_mode: string;
  opening_balances_present: boolean;
  fiscal_period_closed: boolean;
  reporting_limitations: string[];
  accounts: TrialBalanceAccount[];
};

export type ChartOfAccountsFilter = {
  category?: string;
  is_active?: boolean;
  search?: string;
};

export type GeneralLedgerFilter = {
  account_id?: string;
  account_code?: string;
  date_from?: string;
  date_to?: string;
  source_module?: string;
  page?: number;
  size?: number;
};

export type TrialBalanceFilter = {
  as_of_date?: string;
  include_zero_balances?: boolean;
};
