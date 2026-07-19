import { BusinessPageHeader } from "@/components/business/business-page-header";
import { BusinessRouteShell } from "@/components/business/business-route-shell";
import { BusinessSectionNavigation } from "@/components/business/business-section-navigation";
export default function BusinessLayout({ children }: { children: React.ReactNode }) { return <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8 lg:px-8"><BusinessPageHeader title="Business Management" description="Manage verified business context, tax information, settings availability, and account permissions." /><BusinessSectionNavigation /><BusinessRouteShell>{children}</BusinessRouteShell></div>; }
