import { describe, expect, it } from "vitest";
import { supplierSchema } from "./purchase-schemas";

const valid = { name: " Aarav Wholesale ", email: "billing@example.com", phone: "+919876543210", gstin: "29abcde1234f1z5", pan: "abcde1234f", address: " Bengaluru ", payment_terms: " Net 30 ", is_active: true };
describe("supplierSchema", () => {
  it("trims fields and normalizes tax identifiers", () => { expect(supplierSchema.parse(valid)).toMatchObject({ name: "Aarav Wholesale", gstin: "29ABCDE1234F1Z5", pan: "ABCDE1234F", payment_terms: "Net 30" }); });
  it.each([["email", "invalid"], ["phone", "9876543210"], ["gstin", "invalid"], ["pan", "invalid"]])("rejects invalid %s", (field, value) => { expect(supplierSchema.safeParse({ ...valid, [field]: value }).success).toBe(false); });
});
