import { describe, expect, it } from "vitest";
import { catalogSchema } from "./catalog-schema";

const base={code:"ITEM-1",name:"Consulting",description:"",item_type:"service" as const,category:"",purchase_price:0,selling_price:1000,default_unit:"hour",barcode:"",hsn_code:"",sac_code:"998311",gst_rate:18,cess_rate:0};
describe("catalogSchema",()=>{it("accepts a service with SAC classification",()=>{expect(catalogSchema.safeParse(base).success).toBe(true)});it("rejects HSN on a service",()=>{const result=catalogSchema.safeParse({...base,hsn_code:"9988"});expect(result.success).toBe(false)});it("accepts a product with HSN classification",()=>{expect(catalogSchema.safeParse({...base,item_type:"product",sac_code:"",hsn_code:"8471"}).success).toBe(true)});it("requires a name and unit",()=>{expect(catalogSchema.safeParse({...base,name:"",default_unit:""}).success).toBe(false)})});
