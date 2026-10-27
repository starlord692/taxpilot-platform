import{VendorDetail}from"@/components/expenses/vendor-pages";export default async function Page({params}:{params:Promise<{vendorId:string}>}){return <VendorDetail id={(await params).vendorId}/>}
