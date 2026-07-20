import { InvoiceForm } from "@/components/sales/invoice-form";
export default async function Page({params}:{params:Promise<{id:string}>}){return <InvoiceForm id={(await params).id}/>}
