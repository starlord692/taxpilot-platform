import { describe, expect, it } from "vitest";
import { getInitials } from "./user-avatar";
describe("getInitials", () => { it("uses first and last names", () => expect(getInitials("Ada Lovelace", "ada@example.com")).toBe("AL")); it("falls back to email", () => expect(getInitials("", "taxpilot@example.com")).toBe("TA")); });
