/**
 * Phase 5 -- typed wrappers around the Frappe request intake APIs.
 *
 * Endpoints:
 *   POST iranrobot_backend.api.requests.submit_quote_request       allow_guest
 *   POST iranrobot_backend.api.requests.submit_procurement_request allow_guest
 *   POST iranrobot_backend.api.requests.submit_support_ticket      allow_guest
 *   GET  iranrobot_backend.api.requests.get_my_requests            requires auth
 *
 * Calls return only the customer-safe fields the backend project; never expect
 * internal_notes / audit fields from these helpers.
 */

import { frappeFetch, frappePost } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.requests'

// ---------- Quote Request ----------

export type QuoteMode = 'buy' | 'rent' | 'procure'

export interface QuoteItemInput {
  robot_product: string
  quantity: number
  mode: QuoteMode
  requested_days?: number
  notes?: string
}

export interface QuoteRequestInput {
  items: QuoteItemInput[]
  customer_name?: string
  email?: string
  phone?: string
  message?: string
  language?: 'fa' | 'en'
}

export interface QuoteRequestResult {
  request_id: string
  status: string
  total_estimate_usd: number
}

export async function submitQuoteRequest(
  input: QuoteRequestInput,
  signal?: AbortSignal,
): Promise<QuoteRequestResult> {
  return frappePost<QuoteRequestResult>(
    `${BASE}.submit_quote_request`,
    {
      items: JSON.stringify(input.items),
      customer_name: input.customer_name ?? '',
      email: input.email ?? '',
      phone: input.phone ?? '',
      message: input.message ?? '',
      language: input.language ?? 'fa',
    },
    signal,
  )
}

// ---------- Procurement Request ----------

export interface ProcurementRequestInput {
  product_name: string
  brand?: string
  quantity?: number
  origin_country?: string
  destination_city?: string
  target_budget_usd?: number
  timeline?: string
  message?: string
  company?: string
  contact_name?: string
  email?: string
  phone?: string
  language?: 'fa' | 'en'
}

export interface ProcurementRequestResult {
  request_id: string
  status: string
}

export async function submitProcurementRequest(
  input: ProcurementRequestInput,
  signal?: AbortSignal,
): Promise<ProcurementRequestResult> {
  return frappePost<ProcurementRequestResult>(
    `${BASE}.submit_procurement_request`,
    {
      product_name: input.product_name,
      brand: input.brand ?? '',
      quantity: input.quantity ?? 1,
      origin_country: input.origin_country ?? '',
      destination_city: input.destination_city ?? '',
      target_budget_usd: input.target_budget_usd ?? '',
      timeline: input.timeline ?? '',
      message: input.message ?? '',
      company: input.company ?? '',
      contact_name: input.contact_name ?? '',
      email: input.email ?? '',
      phone: input.phone ?? '',
      language: input.language ?? 'fa',
    },
    signal,
  )
}

// ---------- Support Ticket ----------

export interface SupportTicketInput {
  name?: string
  email?: string
  phone?: string
  topic?: string
  subject?: string
  message: string
  language?: 'fa' | 'en'
}

export interface SupportTicketResult {
  ticket_id: string
  status: string
}

export async function submitSupportTicket(
  input: SupportTicketInput,
  signal?: AbortSignal,
): Promise<SupportTicketResult> {
  return frappePost<SupportTicketResult>(
    `${BASE}.submit_support_ticket`,
    {
      name: input.name ?? '',
      email: input.email ?? '',
      phone: input.phone ?? '',
      topic: input.topic ?? '',
      subject: input.subject ?? '',
      message: input.message,
      language: input.language ?? 'fa',
    },
    signal,
  )
}

// ---------- get_my_requests ----------

export interface MyQuoteRequest {
  name: string
  status: string
  submitted_at: string | null
  customer_name: string | null
  total_estimate_usd: number | null
  language: 'fa' | 'en' | null
  creation: string
  /** Number of line items on the parent. */
  item_count: number
  /** First few product names for the list preview. */
  item_preview: string[]
}

export interface MyProcurementRequest {
  name: string
  status: string
  submitted_at: string | null
  product_name: string | null
  brand: string | null
  quantity: number | null
  target_budget_usd: number | null
  language: 'fa' | 'en' | null
  creation: string
}

export interface MySupportTicket {
  name: string
  status: string
  subject: string | null
  creation: string
}

export interface MyRequestsPayload {
  quote_requests: MyQuoteRequest[]
  procurement_requests: MyProcurementRequest[]
  support_tickets: MySupportTicket[]
}

export async function getMyRequests(
  limit = 20,
  signal?: AbortSignal,
): Promise<MyRequestsPayload> {
  return frappeFetch<MyRequestsPayload>(`${BASE}.get_my_requests`, { limit }, signal)
}

// ---------- get_my_request_detail ----------

export type RequestKind = 'quote' | 'procurement' | 'support'

export interface QuoteItemDetail {
  idx: number
  robot_product: string
  erpnext_item: string | null
  product_name: string
  quantity: number
  mode: QuoteMode
  requested_days: number | null
  unit_price_usd: number | null
  line_total_usd: number | null
  notes: string | null
}

export interface QuoteRequestDetail {
  name: string
  status: string
  submitted_at: string | null
  language: 'fa' | 'en' | null
  message: string | null
  customer_name: string | null
  total_estimate_usd: number | null
  creation: string
  items: QuoteItemDetail[]
  /** Phase 7A -- set when Sales staff has issued an ERPNext Quotation from
   * this request. Customer dashboard displays a read-only summary. */
  erpnext_quotation?: string | null
  quotation_status?: QuotationStatus | null
  proposal_amount_usd?: number | null
  quotation?: QuotationBlock | null
  /** Phase 7B -- customer accept/reject state. The server re-evaluates these
   * conditions on every respond_to_quotation call, so a stale `can_respond:
   * true` cached on the client can't be turned into a state-violating write. */
  customer_response?: '' | 'Accepted' | 'Rejected' | null
  customer_response_at?: string | null
  customer_response_note?: string | null
  can_respond?: boolean
  response_allowed_actions?: QuotationResponseAction[]
}

/** Phase 7A -- Quotation status as projected to the customer. Mirrors the
 * Robot Quote Request.quotation_status Select options. */
export type QuotationStatus = '' | 'Draft' | 'Sent' | 'Accepted' | 'Rejected' | 'Expired'

/** Phase 7A -- customer-safe Quotation projection. Internal notes, taxes,
 * margins, addresses, terms, and base-currency fields are NEVER included. */
export interface QuotationBlock {
  quotation_id: string
  status: string | null
  transaction_date: string | null
  valid_till: string | null
  currency: string | null
  grand_total_usd: number
  customer_name: string | null
  items: QuotationItem[]
}

export interface QuotationItem {
  idx: number
  item_code: string
  item_name: string | null
  description: string | null
  qty: number | null
  uom: string | null
  rate: number | null
  amount: number | null
}

export interface ProcurementRequestDetail {
  name: string
  status: string
  submitted_at: string | null
  language: 'fa' | 'en' | null
  message: string | null
  contact_name: string | null
  company: string | null
  product_name: string | null
  brand: string | null
  quantity: number | null
  origin_country: string | null
  destination_city: string | null
  target_budget_usd: number | null
  timeline: string | null
  creation: string
}

export interface SupportTicketDetail {
  name: string
  status: string
  subject: string | null
  description: string | null
  creation: string
  modified: string | null
}

export type RequestDetailPayload =
  | { kind: 'quote'; record: QuoteRequestDetail }
  | { kind: 'procurement'; record: ProcurementRequestDetail }
  | { kind: 'support'; record: SupportTicketDetail }

export async function getMyRequestDetail(
  kind: RequestKind,
  name: string,
  signal?: AbortSignal,
): Promise<RequestDetailPayload> {
  return frappeFetch<RequestDetailPayload>(
    `${BASE}.get_my_request_detail`,
    { kind, name },
    signal,
  )
}

// ---------- respond_to_quotation (Phase 7B) ----------

export type QuotationResponseAction = 'accept' | 'reject'

export interface RespondToQuotationResult {
  request_id: string
  quotation_status: QuotationStatus
  customer_response: 'Accepted' | 'Rejected'
  customer_response_at: string
  customer_response_note: string
}

export async function respondToQuotation(
  name: string,
  action: QuotationResponseAction,
  note?: string,
  signal?: AbortSignal,
): Promise<RespondToQuotationResult> {
  return frappePost<RespondToQuotationResult>(
    `${BASE}.respond_to_quotation`,
    { name, action, note: note ?? '' },
    signal,
  )
}
