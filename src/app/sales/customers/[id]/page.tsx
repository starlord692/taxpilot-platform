import { CustomerDetail } from "@/components/sales/customer-detail";
export default async function CustomerPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <CustomerDetail id={id} />; }
