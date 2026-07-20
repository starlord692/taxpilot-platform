import { CustomerForm } from "@/components/sales/customer-form";
export default async function EditCustomerPage({ params }: { params: Promise<{ id: string }> }) { return <CustomerForm id={(await params).id} />; }
