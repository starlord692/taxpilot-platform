import { Activity, ShieldQuestion } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function BusinessHealthCard() {
  return <Card aria-labelledby="business-health-title"><CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle id="business-health-title">Business health</CardTitle><CardDescription>A consolidated health score requires authoritative operational and financial summaries.</CardDescription></div><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground"><Activity className="size-5" aria-hidden="true" /></span></div></CardHeader><CardContent><div className="flex items-center gap-3 rounded-xl border border-dashed bg-muted/30 p-4"><ShieldQuestion className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><Badge>Assessment unavailable</Badge><p className="mt-2 text-xs leading-5 text-muted-foreground">TaxPilot will show Healthy, Needs Attention, or Critical only when the backend can determine that status reliably.</p></div></div></CardContent></Card>;
}
