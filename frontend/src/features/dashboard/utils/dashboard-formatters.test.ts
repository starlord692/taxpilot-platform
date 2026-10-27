import { describe, expect, it } from "vitest";
import { formatCurrency, formatDate, formatSyncTime } from "./dashboard-formatters";
describe("dashboard formatters", () => { it("formats INR without inventing values", () => expect(formatCurrency("1234.50")).toContain("1,234.50")); it("formats activity dates", () => expect(formatDate("2026-07-18")).toMatch(/18 Jul 2026/)); it("labels a missing synchronization", () => expect(formatSyncTime(null)).toBe("Not synchronized")); });
