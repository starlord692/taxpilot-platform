import{ProductForm}from"@/components/inventory/product-form";export default async function Page({params}:{params:Promise<{productId:string}>}){return <ProductForm id={(await params).productId}/>}
