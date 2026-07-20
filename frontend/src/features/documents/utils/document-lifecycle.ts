import type { AutomationRun, DocumentStatus, Validation } from "../types/documents.types";

export type LifecycleState = "complete" | "current" | "upcoming" | "error";
export interface LifecycleStep { id: "upload" | "read" | "check" | "review" | "create" | "complete"; label: string; state: LifecycleState; description: string; }

export function documentLifecycle(input: { documentStatus: DocumentStatus; hasExtraction: boolean; validation: Validation | null; automation: AutomationRun | null }): LifecycleStep[] {
  const readComplete = input.documentStatus === "ocr_completed";
  const readFailed = input.documentStatus === "ocr_failed";
  const prepared = input.hasExtraction;
  const checked = Boolean(input.validation);
  const approved = input.validation?.review?.review_status === "approved" && input.validation.ready_for_automation;
  const created = input.automation?.status === "completed";
  const creating = input.automation?.status === "running";
  const createFailed = input.automation?.status === "failed" || input.automation?.status === "rolled_back";
  return [
    { id: "upload", label: "Uploaded", state: "complete", description: "Document received by TaxPilot." },
    { id: "read", label: "Read document", state: readFailed ? "error" : readComplete ? "complete" : "current", description: readFailed ? "TaxPilot could not read this document." : readComplete ? "Document information was read." : "Ready for TaxPilot to read." },
    { id: "check", label: "Check information", state: checked ? "complete" : prepared ? "current" : "upcoming", description: checked ? "Information was checked." : prepared ? "Confirm the information TaxPilot found." : "Continue processing before checking information." },
    { id: "review", label: "Approve", state: approved ? "complete" : checked ? "current" : "upcoming", description: approved ? "Document approved." : checked ? "Review and approve when ready." : "Approval follows the information check." },
    { id: "create", label: "Create record", state: createFailed ? "error" : created ? "complete" : creating ? "current" : approved ? "current" : "upcoming", description: createFailed ? "Record creation needs attention." : created ? "Business record created." : "Create the matching business record." },
    { id: "complete", label: "Completed", state: created ? "complete" : "upcoming", description: created ? "Document workflow completed." : "Completion follows record creation." },
  ];
}
