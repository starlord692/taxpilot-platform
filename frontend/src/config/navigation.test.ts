import { describe, expect, it } from "vitest";
import { activeNavigationHref, navigation } from "./navigation";

describe("application navigation", () => {
  it("contains every application-shell destination", () => {
    expect(navigation.map(({ label }) => label)).toEqual(expect.arrayContaining([
      "Business Workspace", "Documents", "Sales", "Purchases", "Expenses",
      "Customers", "Suppliers", "Inventory", "GST & Tax", "Reports", "Settings",
    ]));
  });

  it("selects the most specific nested route", () => {
    expect(activeNavigationHref("/sales/customers/123")).toBe("/sales/customers");
    expect(activeNavigationHref("/gst/reports")).toBe("/gst/reports");
  });
});
