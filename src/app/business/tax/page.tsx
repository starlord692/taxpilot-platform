"use client";
import { useBusiness } from "@/contexts/business-context";
import { useBusinessTax } from "@/features/business/hooks/use-business-tax";
import { TaxProfileCard } from "@/components/business/tax-profile-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
export default function BusinessTaxPage() { const { activeBusiness } = useBusiness(); const tax = useBusinessTax(activeBusiness?.id); if (tax.isLoading) return <Skeleton className="h-72 rounded-xl" />; if (tax.isError) return <section className="rounded-xl border bg-card p-6 text-center" role="alert"><p className="text-sm font-medium">Tax profile could not be loaded</p><Button variant="outline" className="mt-4" onClick={() => void tax.refetch()}>Try again</Button></section>; return <TaxProfileCard registrations={tax.data?.data ?? []} />; }
