import { describe, expect, it } from "vitest";
import { loginSchema } from "./login-schema";
import { registerSchema } from "./register-schema";
describe("authentication schemas", () => {
  it("normalizes a valid login email", () => { expect(loginSchema.parse({ email: " USER@Example.com ", password: "secret" }).email).toBe("user@example.com"); });
  it("rejects weak registration passwords", () => { const result = registerSchema.safeParse({ first_name: "Ada", last_name: "Lovelace", display_name: "", email: "ada@example.com", password: "short", confirm_password: "short" }); expect(result.success).toBe(false); });
  it("accepts matching strong registration credentials", () => { const result = registerSchema.safeParse({ first_name: "Ada", last_name: "Lovelace", display_name: "Ada", email: "ada@example.com", password: "StrongPass123!", confirm_password: "StrongPass123!" }); expect(result.success).toBe(true); });
});
