import { AccountingShell } from "@/features/accounting/components/accounting-shell";

export default function AccountingLayout({ children }: { children: React.ReactNode }) {
  return <AccountingShell>{children}</AccountingShell>;
}
