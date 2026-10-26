"use client";
import { useBusiness } from "@/contexts/business-context";
import { useBusinessTax } from "@/features/business/hooks/use-business-tax";
import { BusinessProfileCard } from "@/components/business/business-profile-card";
import { Skeleton } from "@/components/ui/skeleton";
export default function BusinessProfilePage() { const { activeBusiness } = useBusiness(); const tax = useBusinessTax(activeBusiness?.id); if (!activeBusiness) return null; if (tax.isLoading) return <Skeleton className="h-[520px] rounded-xl" />; return <BusinessProfileCard business={activeBusiness} gst={tax.data?.data.find((item) => item.is_active)} />; }
