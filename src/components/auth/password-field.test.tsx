import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PasswordField } from "./password-field";
describe("PasswordField", () => { it("toggles password visibility accessibly", async () => { const user = userEvent.setup(); render(<PasswordField label="Password" id="password" />); const input = screen.getByLabelText("Password"); expect(input).toHaveAttribute("type", "password"); await user.click(screen.getByRole("button", { name: "Show password" })); expect(input).toHaveAttribute("type", "text"); expect(screen.getByRole("button", { name: "Hide password" })).toBeVisible(); }); it("associates validation errors", () => { render(<PasswordField label="Password" id="password" error="Required" />); expect(screen.getByLabelText("Password")).toHaveAccessibleDescription("Required"); }); });
