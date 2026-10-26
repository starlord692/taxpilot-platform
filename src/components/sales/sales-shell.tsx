"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, FileText, Users } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { BusinessRouteShell } from "@/components/business/business-route-shell";
import { BusinessSwitcher } from "@/components/business/business-switcher";
import { cn } from "@/lib/utils";

const links = [{ href: "/sales", label: "Overview", icon: BarChart3 }, { href: "/sales/customers", label: "Customers", icon: Users }, { href: "/sales/invoices", label: "Invoices", icon: FileText }];
export function SalesShell({ children }: { children: React.ReactNode }) {
  const path = usePathname(); const { businesses } = useBusiness();
  return <BusinessRouteShell><div className="space-y-6"><header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-medium text-primary">Sales</p><h1 className="text-2xl font-semibold tracking-tight">Sales management</h1><p className="mt-1 text-sm text-muted-foreground">Verified customers and invoices for the active business.</p></div>{businesses.length > 1 && <div className="w-full sm:w-72"><BusinessSwitcher /></div>}</header><nav aria-label="Sales sections" className="flex gap-1 overflow-x-auto border-b">{links.map(({ href, label, icon: Icon }) => { const active = href === "/sales" ? path === href : path.startsWith(href); return <Link key={href} href={href} className={cn("flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium", active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}><Icon className="size-4" />{label}</Link>; })}</nav>{children}</div></BusinessRouteShell>;
}
