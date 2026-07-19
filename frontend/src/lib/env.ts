import { z } from "zod";
const publicEnvSchema = z.object({ NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000/api/v1"), NEXT_PUBLIC_APP_NAME: z.string().default("TaxPilot"), NEXT_PUBLIC_PREVIEW_MODE: z.enum(["true", "false"]).default("false") });
export const env = publicEnvSchema.parse({ NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL, NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME, NEXT_PUBLIC_PREVIEW_MODE: process.env.NEXT_PUBLIC_PREVIEW_MODE });
export const isPreviewMode = env.NEXT_PUBLIC_PREVIEW_MODE === "true";
