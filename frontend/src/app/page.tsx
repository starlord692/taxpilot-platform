"use client";

import { Banknote, CalendarDays, CircleDollarSign, HandCoins, ReceiptIndianRupee, ShoppingBag, TrendingUp, WalletCards } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardViewModel } from "@/features/dashboard/hooks/use-dashboard-view-model";
import { formatCurrency, formatDate } from "@/features/dashboard/utils/dashboard-formatters";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { BusinessHealthCard } from "@/components/dashboard/business-health-card";
import { DashboardLayout } from "@/components/dashboard/dashboard-layout";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { EmptyState } from "@/components/dashboard/empty-state";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PendingTasksCard } from "@/components/dashboard/pending-tasks-card";
import { QuickActionsCard } from "@/components/dashboard/quick-actions-card";
import { RecentActivityCard, type ActivityItem } from "@/components/dashboard/recent-activity-card";
import { WorkspaceInsightsCard } from "@/components/dashboard/workspace-insights-card";

const metrics = [
  { label: "Sales", icon: TrendingUp },
  { label: "Purchases", icon: ShoppingBag },
  { label: "Expenses", icon: ReceiptIndianRupee },
  { label: "Collections", icon: HandCoins },
  { label: "Outstanding", icon: CircleDollarSign },
  { label: "Cash Balance", icon: Banknote },
];

export default function BusinessWorkspacePage() {
  const { user } = useAuth();
  const model = useDashboardViewModel();
  const { context, business, activity, pendingReviews } = model;

  if (context.contextStatus === "loading") return <DashboardLayout><DashboardSkeleton /></DashboardLayout>;
  if (context.contextStatus === "error") return <DashboardLayout><PageHeader title="Business Workspace" description="Your business context could not be loaded." /><Alert><div><p className="font-medium">Business context could not be loaded</p><p className="mt-1 text-xs text-muted-foreground">An accessible business is required before the workspace can load operational data.</p><Button variant="outline" size="sm" className="mt-3" onClick={() => context.refetch()}>Try again</Button></div></Alert></DashboardLayout>;
  if (context.contextStatus === "none" || context.contextStatus === "selection-required") return <DashboardLayout><PageHeader title="Business Workspace" description="Select an accessible business to view its workspace." /><section className="rounded-2xl border bg-card"><EmptyState title={context.contextStatus === "none" ? "No business available" : "Choose a business to continue"} description={context.contextStatus === "none" ? "Workspace information will appear after a business membership is added." : "Choose an accessible business from the application navigation to continue."} /></section></DashboardLayout>;

  const expenseItems: ActivityItem[] = (activity.expenses.data?.data ?? []).map((item) => ({ id: item.id, title: item.expense_number, subtitle: formatDate(item.expense_date), amount: formatCurrency(item.total_amount), status: item.status }));
  const purchaseItems: ActivityItem[] = (activity.purchases.data?.data ?? []).map((item) => ({ id: item.id, title: item.purchase_number, subtitle: `${item.invoice_number} · ${formatDate(item.invoice_date)}`, amount: formatCurrency(item.total_amount), status: item.status }));
  const pendingCount = pendingReviews.data?.meta.total;
  const businessName = business?.trade_name || business?.legal_name || "Business";

  return <DashboardLayout>
    <PageHeader title={`Welcome back${user?.first_name ? `, ${user.first_name}` : ""}`} description={`${businessName} · Here is what is available across your business today.`} actions={<div className="flex h-9 items-center gap-2 rounded-lg border bg-card px-3 text-xs text-muted-foreground"><CalendarDays className="size-4" aria-hidden="true" /><time dateTime={new Date().toISOString().slice(0, 10)}>{formatDate(new Date())}</time></div>} />
    <section className="grid gap-4 lg:grid-cols-2" aria-label="Business status and insights"><BusinessHealthCard /><WorkspaceInsightsCard pendingReviews={pendingCount} loading={pendingReviews.isLoading} error={pendingReviews.isError} /></section>
    <section aria-labelledby="today-metrics-title"><div className="mb-3"><h2 id="today-metrics-title" className="text-base font-semibold">Today&apos;s metrics</h2><p className="mt-1 text-sm text-muted-foreground">Financial values remain unavailable until authoritative daily summary APIs are provided.</p></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">{metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}</div></section>
    <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]" aria-label="Tasks and quick actions"><PendingTasksCard pendingReviews={pendingCount} loading={pendingReviews.isLoading} error={pendingReviews.isError} /><QuickActionsCard /></section>
    <section aria-labelledby="recent-activity-title"><div className="mb-3"><h2 id="recent-activity-title" className="text-base font-semibold">Recent activity</h2><p className="mt-1 text-sm text-muted-foreground">Verified records from supported, ordered activity sources.</p></div><div className="grid gap-4 lg:grid-cols-2"><RecentActivityCard title="Recent Expenses" icon={ReceiptIndianRupee} items={expenseItems} isLoading={activity.expenses.isLoading} isError={activity.expenses.isError} onRetry={() => activity.expenses.refetch()} /><RecentActivityCard title="Recent Purchases" icon={WalletCards} items={purchaseItems} isLoading={activity.purchases.isLoading} isError={activity.purchases.isError} onRetry={() => activity.purchases.refetch()} /></div></section>
  </DashboardLayout>;
}
