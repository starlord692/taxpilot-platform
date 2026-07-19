import { z } from "zod";
export const loginSchema = z.object({ email: z.string().trim().email("Enter a valid email address").transform((value) => value.toLowerCase()), password: z.string().min(1, "Enter your password") });
export type LoginFormValues = z.input<typeof loginSchema>;
