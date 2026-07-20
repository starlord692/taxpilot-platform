import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { documentLifecycle } from "@/features/documents/utils/document-lifecycle";
import { DocumentLifecycleStepper } from "./document-lifecycle-stepper";

describe("DocumentLifecycleStepper", () => {
  it("presents business language and confirmed states", () => {
    render(<DocumentLifecycleStepper steps={documentLifecycle({ documentStatus: "ocr_completed", hasExtraction: false, validation: null, automation: null })} />);
    expect(screen.getByRole("navigation", { name: "Document progress" })).toBeVisible();
    expect(screen.getByText("Read document")).toBeVisible();
    expect(screen.getByText("Check information")).toBeVisible();
    expect(screen.queryByText(/OCR|Extraction|Validation|Automation/i)).not.toBeInTheDocument();
  });
});
