import Link from "next/link";
import { FilePlus2, ReceiptText, ShoppingCart, Upload, UserPlus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const actions = [
  { label: "Upload Document", href: "/documents/upload", icon: Upload },
  { label: "Create Invoice", href: "/sales/invoices", icon: FilePlus2, note: "Open invoices" },
  { label: "Record Expense", href: "/expenses/new", icon: ReceiptText },
  { label: "Add Customer", href: "/sales/customers", icon: UserPlus, note: "Open customers" },
  { label: "Create Purchase", href: "/purchases/invoices/new", icon: ShoppingCart },
] as const;

export function QuickActionsCard() {
  return <Card aria-labelledby="quick-actions-title"><CardHeader><CardTitle id="quick-actions-title">Quick actions</CardTitle><CardDescription>Jump into an existing TaxPilot workflow.</CardDescription></CardHeader><CardContent><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">{actions.map(({ label, href, icon: Icon, ...action }) => <Link key={label} href={href} className="group flex min-h-11 items-center gap-3 rounded-xl border bg-background px-3 py-2.5 text-sm font-medium outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"><span className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary"><Icon className="size-4" aria-hidden="true" /></span><span>{label}{"note" in action ? <small className="block text-[10px] font-normal text-muted-foreground">{action.note}</small> : null}</span><span className="ml-auto text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden="true">→</span></Link>)}</div></CardContent></Card>;
}
