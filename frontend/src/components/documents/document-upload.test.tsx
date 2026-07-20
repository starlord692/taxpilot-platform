import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentUpload } from "./document-upload";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/contexts/business-context", () => ({ useBusiness: () => ({ activeBusinessId: "b1" }) }));
vi.mock("@/features/documents/hooks/use-documents", () => ({ useDocumentMutations: () => ({ upload: { mutate: vi.fn(), isPending: false } }) }));

describe("DocumentUpload", () => {
  it("rejects unsupported files before calling the backend", async () => {
    render(<DocumentUpload />);
    fireEvent.change(screen.getByLabelText("Choose document"), { target: { files: [new File(["text"], "notes.txt", { type: "text/plain" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF, PNG, JPEG, WebP, or TIFF file.");
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
  });
});
