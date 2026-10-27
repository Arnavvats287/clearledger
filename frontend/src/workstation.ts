import type { Bundle, Invoice, Receipt, Customer, Doc } from "./api";
export type Loaded = {
  b: Bundle;
  invoices: Invoice[];
  receipts: Receipt[];
  customer?: Customer;
  docs: Doc[];
};
