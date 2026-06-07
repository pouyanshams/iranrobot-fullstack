/**
 * Phase 7D -- typed wrappers around the customer-facing Sales Invoice APIs.
 *
 *   GET  iranrobot_backend.api.invoices.get_my_invoices        auth required
 *   GET  iranrobot_backend.api.invoices.get_my_invoice_detail  auth required
 *
 * Both endpoints filter server-side by the session user's linked ERPNext
 * Customer. Cross-customer access returns NOT_FOUND.
 *
 * Payment Entry visibility: the detail endpoint returns a `payments` array of
 * customer-safe Payment Entry summaries (only submitted PEs are exposed).
 * Bank-account internals, accounting heads, gateway secrets, and owner /
 * modified_by columns are NEVER projected.
 */

import { frappeFetch } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.invoices'

export type SalesInvoiceStatus =
  | 'Draft'
  | 'Unpaid'
  | 'Partly Paid'
  | 'Paid'
  | 'Overdue'
  | 'Return'
  | 'Credit Note Issued'
  | 'Cancelled'

export type CustomerPaymentStatus =
  | 'Unpaid'
  | 'Partly Paid'
  | 'Paid'
  | 'Overdue'
  | 'Cancelled'
  | string

export interface CustomerInvoice {
  name: string
  status: SalesInvoiceStatus | string
  posting_date: string | null
  due_date: string | null
  customer_name: string | null
  grand_total: number | null
  outstanding_amount: number | null
  paid_amount: number | null
  currency: string | null
  creation: string
  items_count: number
  payment_status: CustomerPaymentStatus
  linked_quote_request?: string | null
  linked_quotation?: string | null
  linked_sales_order?: string | null
}

export interface CustomerInvoiceItem {
  idx: number
  item_code: string
  item_name: string | null
  description: string | null
  qty: number | null
  uom: string | null
  rate: number | null
  amount: number | null
}

/** Customer-safe Payment Entry summary. */
export interface CustomerPaymentSummary {
  name: string
  posting_date: string | null
  paid_amount: number | null
  received_amount: number | null
  mode_of_payment: string | null
  reference_no: string | null
  reference_date: string | null
  status: string | null
  docstatus: number
  /** Allocated amount against THIS invoice (a PE may cover several invoices). */
  allocated_amount: number
}

export interface CustomerInvoiceDetail {
  name: string
  status: SalesInvoiceStatus | string
  posting_date: string | null
  due_date: string | null
  customer_name: string | null
  grand_total: number | null
  total: number | null
  net_total: number | null
  outstanding_amount: number | null
  paid_amount: number | null
  currency: string | null
  po_no: string | null
  creation: string
  modified: string | null
  payment_status: CustomerPaymentStatus
  items: CustomerInvoiceItem[]
  payments: CustomerPaymentSummary[]
  linked_quote_request?: string | null
  linked_quotation?: string | null
  linked_sales_order?: string | null
}

export async function fetchMyInvoices(
  limit = 20,
  signal?: AbortSignal,
): Promise<CustomerInvoice[]> {
  const res = await frappeFetch<{ invoices: CustomerInvoice[] }>(
    `${BASE}.get_my_invoices`,
    { limit },
    signal,
  )
  return res.invoices
}

export async function fetchMyInvoiceDetail(
  name: string,
  signal?: AbortSignal,
): Promise<CustomerInvoiceDetail> {
  const res = await frappeFetch<{ record: CustomerInvoiceDetail }>(
    `${BASE}.get_my_invoice_detail`,
    { name },
    signal,
  )
  return res.record
}
