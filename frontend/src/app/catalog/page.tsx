import { Suspense } from "react";
import { CatalogList } from "@/components/catalog/catalog-list";
import { CatalogLoading } from "@/components/catalog/catalog-states";
export default function Page(){return <Suspense fallback={<CatalogLoading/>}><CatalogList/></Suspense>}
