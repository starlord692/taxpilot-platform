export type OpportunityStatus = "eligible" | "ineligible" | "unavailable";

export type AuthoritativeInput = {
  source: string;
  capability: string;
  reference_id: string;
  field: string;
  value_type: string;
  value: unknown;
};

export type UnavailableOpportunityInformation = {
  source: string;
  capability: string;
  reference_id: string | null;
  field: string;
  reason: string;
};

export type BusinessOpportunity = {
  opportunity_id: string;
  business_id: string;
  status: OpportunityStatus;
  assessment_time: string;
  opportunity_type: string;
  canonical_subject: string;
  policy_id: string;
  policy_version: string;
  eligibility_result: OpportunityStatus;
  source_references: AuthoritativeInput[];
  evidence: AuthoritativeInput[];
  limitations: string[];
  input_traceability: AuthoritativeInput[];
  provenance: string;
  temporal_context: string;
  unavailable_information: UnavailableOpportunityInformation[];
};

export type OpportunityCollectionResponse = {
  success: boolean;
  message: string;
  data: BusinessOpportunity[];
};
