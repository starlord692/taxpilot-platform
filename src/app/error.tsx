"use client";
import { ErrorState } from "@/components/feedback/error-state";
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) { return <ErrorState title="This view could not be loaded" description={error.message} onRetry={reset} />; }
