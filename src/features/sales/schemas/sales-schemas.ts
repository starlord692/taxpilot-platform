import { z } from "zod";

export const invoiceLineSchema = z.object({
  catalog_item_id: z.string().nullable().optional(),
  warehouse_id: z.string().nullable().optional(),
  description: z.string().trim().min(1, "Description is required").max(255, "Description cannot exceed 255 characters"),
  quantity: z.number().positive("Quantity must be greater than zero"),
  unit_price: z.number().positive("Unit price must be greater than zero"),
  discount: z.number().min(0, "Discount cannot be negative"),
  tax_rate: z.number().min(0, "Tax rate cannot be negative"),
  cgst_amount: z.number().min(0),
  sgst_amount: z.number().min(0),
  igst_amount: z.number().min(0),
  cess_amount: z.number().min(0),
  line_total: z.number().min(0),
});

export type InvoiceLineFormValues = z.infer<typeof invoiceLineSchema>;

export const invoiceCreateSchema = z
  .object({
    customer_id: z.string().min(1, "Customer is required"),
    invoice_number: z.string().trim().min(1, "Invoice number is required").max(50, "Invoice number cannot exceed 50 characters"),
    invoice_date: z.string().min(1, "Invoice date is required"),
    due_date: z.string().nullable().optional(),
    notes: z.string().nullable().optional(),
    lines: z.array(invoiceLineSchema).min(1, "At least one line item is required"),
  })
  .refine(
    (value) => !value.due_date || value.due_date >= value.invoice_date,
    {
      path: ["due_date"],
      message: "Due date cannot be before invoice date.",
    }
  )
  .refine(
    (value) =>
      value.lines.every(
        (line) => (line.discount || 0) <= line.quantity * line.unit_price
      ),
    {
      path: ["lines"],
      message: "Line discount cannot exceed gross line amount.",
    }
  );

export type InvoiceCreateFormValues = z.infer<typeof invoiceCreateSchema>;
