"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { List, PackageOpen, Plus } from "lucide-react";
import { BusinessRouteShell } from "@/components/business/business-route-shell";
import { BusinessSwitcher } from "@/components/business/business-switcher";
import { EntityWorkspaceHeader } from "@/components/entities/entity-workspace";
import { useBusiness } from "@/contexts/business-context";
import { cn } from "@/lib/utils";

const links = [{ href: "/catalog", label: "Catalog", icon: List }, { href: "/catalog/new", label: "New item", icon: Plus }];
export function CatalogShell({ children }: { children: React.ReactNode }) { const pathname=usePathname(); const {businesses}=useBusiness(); return <BusinessRouteShell><div className="space-y-6"><EntityWorkspaceHeader eyebrow="Catalog" title="Products & services" description="A canonical catalog for commercial, tax, and shared item information." action={pathname==="/catalog"?{href:"/catalog/new",label:"New item",icon:PackageOpen}:undefined}/>{businesses.length>1&&<div className="max-w-sm"><BusinessSwitcher/></div>}<nav aria-label="Catalog sections" className="flex gap-1 overflow-x-auto border-b">{links.map(({href,label,icon:Icon})=><Link key={href} href={href} className={cn("flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium",pathname===href?"border-primary":"border-transparent text-muted-foreground")}><Icon className="size-4" aria-hidden="true"/>{label}</Link>)}</nav>{children}</div></BusinessRouteShell>; }
