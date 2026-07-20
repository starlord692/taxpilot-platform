import { z } from "zod";

const optional = (schema: z.ZodString) => z.union([z.literal(""), schema]);
export const customerSchema = z.object({
  customer_code: z.string().trim().min(1, "Customer code is required").max(50),
  name: z.string().trim().min(2, "Customer name must be at least 2 characters").max(150),
  email: optional(z.string().trim().email("Enter a valid email address")),
  phone: optional(z.string().trim().regex(/^\+[1-9]\d{7,14}$/, "Use international format, for example +919876543210")),
  gstin: optional(z.string().trim().toUpperCase().regex(/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, "Enter a valid Indian GSTIN")),
  pan: optional(z.string().trim().toUpperCase().regex(/^[A-Z]{5}\d{4}[A-Z]$/, "Enter a valid PAN")),
  billing_address: optional(z.string().trim().max(1000)),
  shipping_address: optional(z.string().trim().max(1000)),
});
export type CustomerFormValues = z.input<typeof customerSchema>;
