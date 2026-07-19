import { describe, expect, it } from "vitest";
import { permissionModules } from "./permission-summary";
describe("permission summary", () => { it("derives only explicit permission prefixes", () => expect(permissionModules(["sales.invoices.read", "sales.customers.read", "gst.registrations.read"])).toEqual(["gst", "sales"])); it("does not fabricate modules", () => expect(permissionModules([])).toEqual([])); });
