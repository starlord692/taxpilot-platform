import { PageContainer } from "@/components/layout/page-container";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <PageContainer className="space-y-8 sm:py-8">{children}</PageContainer>;
}
