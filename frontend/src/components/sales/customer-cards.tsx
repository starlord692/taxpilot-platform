import { BusinessEntityInformationCard, BusinessEntityUnavailableCard } from "@/components/entities/business-entity-cards";
import type { Customer } from "@/features/sales/types/sales.types";

export function CustomerInformationCard({ customer }: { customer: Customer }) { return <BusinessEntityInformationCard title="Customer information" description="Identity used across sales records" fields={[["Customer code", customer.customer_code], ["Status", customer.is_active ? "Active" : "Archived"]]} />; }
export function ContactInformationCard({ customer }: { customer: Customer }) { return <BusinessEntityInformationCard title="Contact information" description="Ways to contact this customer" fields={[["Email", customer.email], ["Phone", customer.phone]]} />; }
export function GSTInformationCard({ customer }: { customer: Customer }) { return <BusinessEntityInformationCard title="GST information" description="Verified fields stored on the customer record" fields={[["GSTIN", customer.gstin], ["PAN", customer.pan]]} />; }
export function AddressCard({ customer }: { customer: Customer }) { return <BusinessEntityInformationCard title="Addresses" description="Billing and shipping details" fields={[["Billing address", customer.billing_address], ["Shipping address", customer.shipping_address]]} />; }
export function CustomerActivityCard() { return <BusinessEntityUnavailableCard title="Customer activity" description="Last activity, payments, outstanding balances, and GST history are not available from the current customer API." />; }
