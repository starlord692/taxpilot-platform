import { BusinessEntityInformationCard, BusinessEntityUnavailableCard } from "@/components/entities/business-entity-cards";
import type { Supplier } from "@/features/purchases/types/purchases.types";

export function SupplierInformationCard({ supplier }: { supplier: Supplier }) { return <BusinessEntityInformationCard title="Supplier information" description="Identity used across procurement records" fields={[["Supplier code", supplier.supplier_code], ["Status", supplier.is_active ? "Active" : "Archived"], ["Payment terms", supplier.payment_terms]]} />; }
export function SupplierContactCard({ supplier }: { supplier: Supplier }) { return <BusinessEntityInformationCard title="Contact information" description="Ways to contact this supplier" fields={[["Email", supplier.email], ["Phone", supplier.phone]]} />; }
export function SupplierGSTCard({ supplier }: { supplier: Supplier }) { return <BusinessEntityInformationCard title="GST information" description="Verified fields stored on the supplier record" fields={[["GSTIN", supplier.gstin], ["PAN", supplier.pan]]} />; }
export function SupplierAddressCard({ supplier }: { supplier: Supplier }) { return <BusinessEntityInformationCard title="Address" description="Supplier location and correspondence details" fields={[["Address", supplier.address]]} />; }
export function SupplierActivityCard() { return <BusinessEntityUnavailableCard title="Supplier activity" description="Purchase summaries, outstanding balances, supplier history, and analytics are not available from the current backend." />; }
