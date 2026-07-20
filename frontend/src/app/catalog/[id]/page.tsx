import { CatalogDetail } from "@/components/catalog/catalog-detail";
export default async function Page({params}:{params:Promise<{id:string}>}){return <CatalogDetail id={(await params).id}/>}
