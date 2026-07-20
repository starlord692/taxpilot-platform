"use client";

import { ArrowRight, CircleAlert } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBusiness } from "@/contexts/business-context";
import { useAutomation, useDocument, useDocumentMutations, useExtraction, useValidation } from "@/features/documents/hooks/use-documents";
import { businessDocumentStatus, bytes, title } from "@/features/documents/utils/document-utils";
import { documentLifecycle } from "@/features/documents/utils/document-lifecycle";
import { AutomationPanel } from "./automation-panel";
import { DocumentActivityPanel } from "./document-activity-panel";
import { DocumentError } from "./document-states";
import { DocumentInformationPanel } from "./document-information-panel";
import { DocumentLifecycleStepper } from "./document-lifecycle-stepper";
import { DocumentWorkspaceSkeleton } from "./document-workspace-skeleton";
import { ReviewDecisionPanel } from "./review-decision-panel";

export function DocumentDetail({ id }: { id: string }) {
  const { activeBusinessId } = useBusiness();
  const businessId = activeBusinessId ?? "";
  const documentQuery = useDocument(businessId, id);
  const extractionQuery = useExtraction(businessId, id);
  const validationQuery = useValidation(businessId, id);
  const automationQuery = useAutomation(businessId, id);
  const mutations = useDocumentMutations();

  if (documentQuery.isLoading) return <DocumentWorkspaceSkeleton />;
  if (documentQuery.isError || !documentQuery.data) return <DocumentError retry={() => void documentQuery.refetch()} />;

  const document = documentQuery.data;
  const extraction = extractionQuery.data ?? null;
  const validation = validationQuery.data ?? null;
  const automation = automationQuery.data ?? null;
  const stages = documentLifecycle({ documentStatus: document.status, hasExtraction: Boolean(extraction), validation, automation });
  const optionalError = extractionQuery.isError || validationQuery.isError || automationQuery.isError;

  const run = (action: "read" | "extract" | "check") => {
    const args = { businessId, id };
    const request = action === "read" ? mutations.ocr.mutateAsync(args) : action === "extract" ? mutations.extract.mutateAsync({ ...args, useAi: true }) : mutations.validate.mutateAsync(args);
    const success = action === "read" ? "Document read successfully" : action === "extract" ? "Information prepared for review" : "Information checked";
    void request.then(() => toast.success(success)).catch(error => toast.error(error instanceof Error ? error.message : "The action could not be completed"));
  };

  const nextAction = document.status === "ocr_running"
    ? null
    : document.status !== "ocr_completed"
    ? { label: document.status === "ocr_failed" ? "Try reading again" : "Read document", action: "read" as const, pending: mutations.ocr.isPending }
    : !extraction
      ? { label: "Continue processing", action: "extract" as const, pending: mutations.extract.isPending }
      : !validation
        ? { label: "Check information", action: "check" as const, pending: mutations.validate.isPending }
        : null;

  return <div className="space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="mb-2 flex flex-wrap items-center gap-2"><Badge tone={document.status === "ocr_failed" ? "danger" : "info"}>{businessDocumentStatus(document.status)}</Badge><span className="text-xs text-muted-foreground">{title(document.document_type)}</span></div><h2 className="break-words text-xl font-semibold sm:text-2xl">{document.original_filename}</h2><p className="mt-1 text-sm text-muted-foreground">{bytes(document.file_size)} · {document.page_count} {document.page_count === 1 ? "page" : "pages"}</p></div>{document.status === "ocr_running" ? <Button disabled>Reading document…</Button> : nextAction ? <Button onClick={() => run(nextAction.action)} disabled={nextAction.pending}>{nextAction.pending ? "Working…" : nextAction.label}<ArrowRight aria-hidden="true" /></Button> : null}</header>
    <DocumentLifecycleStepper steps={stages} />
    {optionalError ? <div role="alert" className="flex gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><CircleAlert className="size-5 shrink-0 text-destructive" /><div><p className="font-medium">Some document information could not be loaded</p><p className="mt-1 text-xs text-muted-foreground">Refresh the page before continuing. Missing stages are shown separately from connection or permission errors.</p></div></div> : null}
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(28rem,1.1fr)]"><DocumentInformationPanel document={document} /><section className="space-y-5 rounded-2xl border bg-card p-5" aria-labelledby="review-information-title"><div><h3 id="review-information-title" className="font-semibold">Review information</h3><p className="mt-1 text-sm text-muted-foreground">Confirm what TaxPilot found before creating a business record.</p></div>{extractionQuery.isLoading || validationQuery.isLoading ? <DocumentWorkspaceSkeleton /> : extraction && validation ? <ReviewDecisionPanel id={id} businessId={businessId} extraction={extraction} validation={validation} /> : <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">Continue the current processing step to prepare this information for review.</p>}</section></div>
    <div className="grid items-start gap-5 lg:grid-cols-2"><AutomationPanel id={id} businessId={businessId} eligible={Boolean(validation?.ready_for_automation)} run={automation} /><DocumentActivityPanel validation={validation} /></div>
  </div>;
}
