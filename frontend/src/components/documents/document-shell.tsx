"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileSearch, Files, LayoutDashboard, Upload } from "lucide-react";
import { BusinessRouteShell } from "@/components/business/business-route-shell";
import { BusinessSwitcher } from "@/components/business/business-switcher";
import { useBusiness } from "@/contexts/business-context";
import { cn } from "@/lib/utils";

const links = [{ href: "/documents", label: "Overview", icon: LayoutDashboard }, { href: "/documents/list", label: "Document queue", icon: Files }, { href: "/documents/upload", label: "Upload", icon: Upload }, { href: "/documents/review", label: "Needs review", icon: FileSearch }];

export function DocumentShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { businesses } = useBusiness();
  return <BusinessRouteShell><div className="space-y-6"><header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-medium text-primary">Business documents</p><h1 className="text-2xl font-semibold tracking-tight">Documents</h1><p className="mt-1 text-sm text-muted-foreground">Upload, check, approve, and create business records with clear next steps.</p></div>{businesses.length > 1 ? <div className="w-full sm:w-72"><BusinessSwitcher /></div> : null}</header><nav aria-label="Document sections" className="flex gap-1 overflow-x-auto border-b">{links.map(({ href, label, icon: Icon }) => { const active = href === "/documents" ? pathname === href : pathname.startsWith(href); return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}><Icon className="size-4" aria-hidden="true" />{label}</Link>; })}</nav>{children}</div></BusinessRouteShell>;
}
