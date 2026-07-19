import {
  BadgeIndianRupee,
  Boxes,
  Building2,
  FileBarChart,
  Files,
  Home,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Truck,
  Users,
  WalletCards,
} from "lucide-react";

export const navigation = [
  { label: "Dashboard", href: "/", icon: Home },
  { label: "Business Workspace", href: "/business", icon: Building2 },
  { label: "Documents", href: "/documents", icon: Files },
  { label: "Sales", href: "/sales", icon: ShoppingCart },
  { label: "Purchases", href: "/purchases", icon: ShoppingBag },
  { label: "Expenses", href: "/expenses", icon: WalletCards },
  { label: "Customers", href: "/sales/customers", icon: Users },
  { label: "Suppliers", href: "/purchases/suppliers", icon: Truck },
  { label: "Inventory", href: "/inventory", icon: Boxes },
  { label: "GST & Tax", href: "/gst", icon: BadgeIndianRupee },
  { label: "Reports", href: "/gst/reports", icon: FileBarChart },
  { label: "Settings", href: "/settings", icon: Settings },
] as const;

export function activeNavigationHref(pathname: string) {
  return navigation
    .filter(({ href }) => pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
}
