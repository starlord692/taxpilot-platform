"use client";

import { useEffect, useMemo } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { reviewSchema, type ReviewValues } from "@/features/documents/schemas/review-schema";
import { useDocumentMutations } from "@/features/documents/hooks/use-documents";
import type { Extraction, Validation } from "@/features/documents/types/documents.types";
import { ExtractedFieldsPanel } from "./extracted-fields-panel";
import { ValidationIssuesPanel } from "./validation-issues-panel";

export function ReviewDecisionPanel({ id, businessId, extraction, validation }: { id: string; businessId: string; extraction: Extraction; validation: Validation | null }) {
  const mutations = useDocumentMutations();
  const defaults = useMemo<ReviewValues>(() => ({ decision: "approve", notes: null, corrections: extraction.fields.map(field => ({ field_name: field.field_name, new_value: field.field_value, reason: "Manual review" })) }), [extraction.fields]);
  const form = useForm<ReviewValues>({ resolver: zodResolver(reviewSchema), defaultValues: defaults });
  useEffect(() => form.reset(defaults), [defaults, form]);
  useEffect(() => { const protect = (event: BeforeUnloadEvent) => { if (form.formState.isDirty) event.preventDefault(); }; window.addEventListener("beforeunload", protect); return () => window.removeEventListener("beforeunload", protect); }, [form.formState.isDirty]);
  const save = form.handleSubmit(values => mutations.review.mutate({ businessId, id, input: { ...values, corrections: values.corrections.filter((correction, index) => correction.new_value !== extraction.fields[index]?.field_value) } }, { onSuccess: () => { form.reset(values); toast.success(values.decision === "approve" ? "Document approved" : "Review saved"); }, onError: () => toast.error("Review could not be saved") }));

  return <form onSubmit={save} className="space-y-5"><ValidationIssuesPanel issues={validation?.issues ?? []} /><ExtractedFieldsPanel fields={extraction.fields} register={form.register} /><fieldset className="space-y-3 rounded-xl border bg-muted/20 p-4"><legend className="px-1 text-sm font-semibold">Your decision</legend><label className="block text-sm font-medium">Decision<select className="mt-1 h-10 w-full rounded-lg border bg-background px-3 outline-none focus-visible:ring-2 focus-visible:ring-ring" {...form.register("decision")}><option value="approve">Approve information</option><option value="request_correction">Needs correction</option><option value="reject">Reject document</option></select></label><label className="block text-sm font-medium">Notes<textarea className="mt-1 min-h-20 w-full rounded-lg border bg-background p-3 outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Optional note for this decision" {...form.register("notes", { setValueAs: value => value || null })} /></label><Button className="w-full" disabled={mutations.review.isPending}>{mutations.review.isPending ? "Saving decision…" : "Save decision"}</Button>{form.formState.isDirty ? <p aria-live="polite" className="text-center text-xs text-amber-700 dark:text-amber-400">You have unsaved changes.</p> : null}</fieldset></form>;
}
