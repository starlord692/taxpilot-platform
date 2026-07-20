import { describe, expect, it } from "vitest";
import { businessDocumentStatus, confidence, page, size, status, type } from "./document-utils";

describe("document utilities", () => {
  it("sanitizes backend list state", () => { expect(page("0")).toBe(1); expect(size("99")).toBe(20); expect(type("sales_invoice")).toBe("sales_invoice"); expect(type("invoice")).toBeUndefined(); expect(status("ocr_completed")).toBe("ocr_completed"); expect(status("done")).toBeUndefined(); });
  it("supports backend and legacy normalized confidence scales", () => { expect(confidence("87.4")).toBe(87); expect(confidence("0.874")).toBe(87); });
  it("translates technical states into business language", () => { expect(businessDocumentStatus("ocr_running")).toBe("Reading document"); expect(businessDocumentStatus("ocr_failed")).toBe("Reading failed"); });
});
