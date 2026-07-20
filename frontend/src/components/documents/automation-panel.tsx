"use client";

import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useDocumentMutations } from "@/features/documents/hooks/use-documents";
import { title } from "@/features/documents/utils/document-utils";
import type { AutomationRun } from "@/features/documents/types/documents.types";
import { DocumentBadge } from "./document-badge";

export function AutomationPanel({ id, businessId, eligible, run }: { id: string; businessId: string; eligible: boolean; run: AutomationRun | null }) {
  const mutations = useDocumentMutations();
  const execute = () => mutations.automate.mutate({ businessId, id, key: `document-${id}-${crypto.randomUUID()}` }, { onSuccess: result => toast.success(result.reused_existing ? "Existing business record found" : "Business record created"), onError: error => toast.error(error instanceof Error ? error.message : "Business record could not be created") });
  const complete = run?.status === "completed";
  return <section className="rounded-2xl border bg-card p-5" aria-labelledby="create-record-title"><div className="flex items-start justify-between gap-3"><div><h3 id="create-record-title" className="font-semibold">Create business record</h3><p className="mt-1 text-sm text-muted-foreground">Use the approved information to create its matching TaxPilot record.</p></div>{run ? <DocumentBadge value={run.status} tone={complete ? "good" : run.status === "failed" ? "bad" : "warn"} /> : null}</div>{run ? <dl className="mt-4 grid gap-3 rounded-xl bg-muted/30 p-4 text-sm sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Record type</dt><dd className="mt-1 font-medium">{title(run.automation_type)}</dd></div>{run.erp_record_id ? <div><dt className="text-xs text-muted-foreground">Record reference</dt><dd className="mt-1 break-all font-mono text-xs">{run.erp_record_id}</dd></div> : null}{run.failure_reason ? <div role="alert" className="text-destructive sm:col-span-2">{run.failure_reason}</div> : null}</dl> : <p className="mt-4 rounded-xl border border-dashed p-4 text-sm text-muted-foreground">No business record has been created from this document.</p>}<Button className="mt-4 w-full" onClick={execute} disabled={!eligible || complete || mutations.automate.isPending}>{mutations.automate.isPending ? "Creating record…" : complete ? "Record created" : "Create business record"}</Button>{!eligible && !complete ? <p className="mt-2 text-xs text-muted-foreground">Approve the checked information before creating a record.</p> : null}<p className="mt-2 text-xs text-muted-foreground">Only the latest result is available. Complete history is not provided by the backend.</p></section>;
}
