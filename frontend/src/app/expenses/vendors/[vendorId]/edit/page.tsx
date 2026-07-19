import{VendorForm}from"@/components/expenses/vendor-form";export default async function Page({params}:{params:Promise<{vendorId:string}>}){return <VendorForm id={(await params).vendorId}/>}
