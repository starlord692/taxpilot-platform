"use client";
import { useBusiness } from "@/contexts/business-context";
import { useAuth } from "@/contexts/auth-context";
import { useBusinessTax } from "@/features/business/hooks/use-business-tax";
import { BusinessCard } from "@/components/business/business-card";
import { TaxProfileCard } from "@/components/business/tax-profile-card";
import { SettingsCard } from "@/components/business/settings-card";
import { PermissionCard } from "@/components/business/permission-card";
import { Skeleton } from "@/components/ui/skeleton";
export default function BusinessOverviewPage() { const { activeBusiness } = useBusiness(); const { user } = useAuth(); const tax = useBusinessTax(activeBusiness?.id); if (!activeBusiness) return null; return <div className="space-y-4"><BusinessCard business={activeBusiness} /><div className="grid gap-4 lg:grid-cols-2">{tax.isLoading ? <Skeleton className="h-64 rounded-xl" /> : tax.isError ? <section className="rounded-xl border bg-card p-6 text-sm text-destructive">Tax profile could not be loaded.</section> : <TaxProfileCard registrations={tax.data?.data ?? []} />}<SettingsCard /></div><PermissionCard roles={user?.roles} permissions={user?.permissions} /></div>; }
