import { describe, expect, it } from "vitest";
import { customerSchema } from "./customer-schema";

const valid = { customer_code: " C-001 ", name: " Aarav Traders ", email: "billing@example.com", phone: "+919876543210", gstin: "29abcde1234f1z5", pan: "abcde1234f", billing_address: " Bengaluru ", shipping_address: "" };
describe("customerSchema", () => {
  it("trims fields and normalizes Indian tax identifiers", () => { expect(customerSchema.parse(valid)).toMatchObject({ customer_code: "C-001", name: "Aarav Traders", gstin: "29ABCDE1234F1Z5", pan: "ABCDE1234F" }); });
  it.each([["email", "invalid"], ["phone", "9876543210"], ["gstin", "wrong"], ["pan", "wrong"]])("rejects invalid %s", (field, value) => { expect(customerSchema.safeParse({ ...valid, [field]: value }).success).toBe(false); });
});
