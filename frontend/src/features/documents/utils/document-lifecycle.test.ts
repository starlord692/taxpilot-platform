import { describe, expect, it } from "vitest";
import { documentLifecycle } from "./document-lifecycle";

describe("document lifecycle", () => {
  it("makes reading the current step after upload", () => { const steps = documentLifecycle({ documentStatus: "ocr_pending", hasExtraction: false, validation: null, automation: null }); expect(steps.find(step => step.id === "read")?.state).toBe("current"); });
  it("marks completed record creation without exposing technical stages", () => { const steps = documentLifecycle({ documentStatus: "ocr_completed", hasExtraction: true, validation: { document_id: "d1", business_id: "b1", issues: [], review: { id: "r1", document_id: "d1", review_status: "approved", reviewed_by: "u1", reviewed_at: null, review_notes: null, ready_for_automation: true }, revisions: [], decisions: [], ready_for_automation: true }, automation: { id: "a1", document_id: "d1", business_id: "b1", automation_type: "expense", idempotency_key: "key", status: "completed", erp_record_type: "expense", erp_record_id: "e1", started_at: null, completed_at: null, failure_reason: null, retry_count: 0 } }); expect(steps.find(step => step.id === "complete")?.state).toBe("complete"); expect(steps.map(step => step.label)).not.toContain("OCR"); });
});
