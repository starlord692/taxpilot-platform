import { describe, expect, it } from "vitest";
import { getExpiresAt, isSessionExpired } from "./token-expiry";
describe("token expiry", () => { it("calculates expiry in milliseconds", () => expect(getExpiresAt(900, 1_000)).toBe(901_000)); it("treats near-expiry tokens as expired", () => expect(isSessionExpired(5_000, 1_000)).toBe(true)); });
