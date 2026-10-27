import { describe, expect, it } from "vitest";
import { navigation } from "./navigation";

describe("application navigation", () => {
  it("enables the verified Settings workspace", () => {
    expect(navigation.find((x) => x.href === "/settings")).toMatchObject({
      label: "Settings",
      disabled: false,
    });
  });

  it("enables the verified Accounting workspace", () => {
    expect(navigation.find((x) => x.href === "/accounting")).toMatchObject({
      label: "Accounting",
      disabled: false,
    });
  });

  it("keeps unsupported clients disabled", () => {
    expect(navigation.find((x) => x.href === "/clients")?.disabled).toBe(true);
  });
});

