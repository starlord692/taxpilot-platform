"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/dashboard/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { useBusiness } from "@/contexts/business-context";
import { ApiClientError } from "@/lib/api/errors";
import { useOpportunities } from "../hooks/use-opportunities";
import type { BusinessOpportunity } from "../types/opportunity.types";

const statusLabels = {
  eligible: "Eligible",
  ineligible: "Ineligible",
  unavailable: "Unavailable",
} as const;

function OpportunityArtifact({ opportunity }: { opportunity: BusinessOpportunity }) {
  return (
    <article className="rounded-xl border bg-card p-5" aria-label={opportunity.canonical_subject}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium">{opportunity.canonical_subject}</p>
          <p className="text-xs text-muted-foreground">{opportunity.opportunity_type}</p>
        </div>
        <span className="text-sm font-medium">{statusLabels[opportunity.status]}</span>
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-muted-foreground">Assessment time</dt><dd>{opportunity.assessment_time}</dd></div>
        <div><dt className="text-muted-foreground">Policy</dt><dd>{opportunity.policy_id} · {opportunity.policy_version}</dd></div>
        <div><dt className="text-muted-foreground">Provenance</dt><dd>{opportunity.provenance}</dd></div>
        <div><dt className="text-muted-foreground">Temporal context</dt><dd>{opportunity.temporal_context}</dd></div>
      </dl>
      {opportunity.limitations.length > 0 ? <section className="mt-4" aria-label="Limitations"><h3 className="text-sm font-medium">Limitations</h3><ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">{opportunity.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></section> : null}
      {opportunity.unavailable_information.length > 0 ? <section className="mt-4" aria-label="Unavailable information"><h3 className="text-sm font-medium">Unavailable information</h3><ul className="mt-1 space-y-1 text-sm text-muted-foreground">{opportunity.unavailable_information.map((information) => <li key={`${information.source}:${information.capability}:${information.reference_id}:${information.field}`}>{information.source} / {information.capability} / {information.field}: {information.reason}</li>)}</ul></section> : null}
      <p className="mt-4 text-xs text-muted-foreground">Evidence: {opportunity.evidence.length} · Source references: {opportunity.source_references.length} · Input traceability: {opportunity.input_traceability.length}</p>
    </article>
  );
}

export function OpportunityCenter() {
  const { activeBusinessId, status } = useBusiness();
  const query = useOpportunities(activeBusinessId);

  if (status === "initializing") return <main className="p-6"><PageHeader title="Opportunity Center" description="Loading your business context." /></main>;
  if (status !== "ready" || !activeBusinessId) return <main className="p-6"><PageHeader title="Opportunity Center" description="An authorized business context is required." /><EmptyState title="Business context unavailable" description="Select an accessible business to explore authoritative opportunities." /></main>;
  if (query.isLoading) return <main className="p-6"><PageHeader title="Opportunity Center" description="Retrieving authoritative opportunities." /></main>;
  if (query.isError) {
    const accessDenied = query.error instanceof ApiClientError && [403, 404].includes(query.error.status ?? 0);
    if (accessDenied) return <main className="p-6"><PageHeader title="Opportunity Center" description="The requested business context is unavailable." /><EmptyState title="Access unavailable" description="No opportunity information can be shown for this business context." /></main>;
    return <main className="p-6"><PageHeader title="Opportunity Center" description="Authoritative opportunity information could not be delivered." /><Alert><div><p className="font-medium">Opportunity Center is unavailable</p><p className="mt-1 text-sm text-muted-foreground">No opportunity meaning has been inferred.</p><Button className="mt-3" onClick={() => query.refetch()}>Try again</Button></div></Alert></main>;
  }

  const opportunities = query.data?.data ?? [];
  return <main className="p-6"><PageHeader title="Opportunity Center" description="Authoritative Business Opportunity information for the active business." />{opportunities.length === 0 ? <section className="mt-6 rounded-xl border bg-card"><EmptyState title="No authoritative opportunities available" description="No opportunity artifact has been supplied for this business context." /></section> : <section className="mt-6 grid gap-4" aria-label="Authoritative opportunities">{opportunities.map((opportunity) => <OpportunityArtifact key={opportunity.opportunity_id} opportunity={opportunity} />)}</section>}</main>;
}
