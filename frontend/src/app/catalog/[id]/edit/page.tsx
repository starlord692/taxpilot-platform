import { CatalogForm } from "@/components/catalog/catalog-form";
export default async function Page({params}:{params:Promise<{id:string}>}){return <CatalogForm id={(await params).id}/>}
