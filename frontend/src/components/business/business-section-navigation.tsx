"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
const sections = [{ label: "Overview", href: "/business" }, { label: "Profile", href: "/business/profile" }, { label: "Tax", href: "/business/tax" }, { label: "Members", href: "/business/members" }, { label: "Settings", href: "/business/settings" }, { label: "Permissions", href: "/business/permissions" }];
export function BusinessSectionNavigation() { const pathname = usePathname(); return <nav className="flex flex-wrap gap-1 border-b pb-3" aria-label="Business sections">{sections.map((item) => <Link key={item.href} href={item.href} aria-current={pathname === item.href ? "page" : undefined} className={cn("rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground", pathname === item.href && "bg-accent font-medium text-foreground")}>{item.label}</Link>)}</nav>; }
