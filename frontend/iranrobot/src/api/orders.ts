/**
 * Phase 7C -- typed wrappers around the customer-facing Sales Order APIs.
 *
 *   GET  iranrobot_backend.api.orders.get_my_orders        auth required
 *   GET  iranrobot_backend.api.orders.get_my_order_detail  auth required
 *
 * Both endpoints enforce ownership server-side (filter by the session user's
 * linked ERPNext Customer). Cross-customer access returns NOT_FOUND.
 *
 * The backend projects only an allow-list of customer-safe fields. The types
 * below mirror that projection exactly -- adding a new field on the React side
 * requires adding it to the backend allow-list first.
 */

import { frappeFetch } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.orders'

/**
 * ERPNext Sales Order status values. We type them as a discriminated string
 * union so StatusBadge can map them safely; any unknown status falls back to
 * neutral styling at render time.
 */
export type SalesOrderStatus =
  | 'Draft'
  | 'To Deliver and Bill'
  | 'To Bill'
  | 'To Deliver'
  | 'Completed'
  | 'Closed'
  | 'Cancelled'
  | 'On Hold'

export interface CustomerOrder {
  name: string
  status: SalesOrderStatus | string
  transaction_date: string | null
  delivery_date: string | null
  customer_name: string | null
  grand_total: number | null
  currency: string | null
  creation: string
  items_count: number
  /** Set when the Sales Order was created from a Robot Quote Request via the
   * Phase 7C Desk button. Lets the dashboard back-link to the conversation. */
  linked_quote_request?: string | null
  linked_quotation?: string | null
}

export interface CustomerOrderItem {
  idx: number
  item_code: string
  item_name: string | null
  description: string | null
  qty: number | null
  uom: string | null
  rate: number | null
  amount: number | null
}

export interface CustomerOrderDetail {
  name: string
  status: SalesOrderStatus | string
  transaction_date: string | null
  delivery_date: string | null
  customer_name: string | null
  grand_total: number | null
  total: number | null
  net_total: number | null
  currency: string | null
  po_no: string | null
  creation: string
  modified: string | null
  items: CustomerOrderItem[]
  linked_quote_request?: string | null
  linked_quotation?: string | null
}

export async function fetchMyOrders(
  limit = 20,
  signal?: AbortSignal,
): Promise<CustomerOrder[]> {
  const res = await frappeFetch<{ orders: CustomerOrder[] }>(
    `${BASE}.get_my_orders`,
    { limit },
    signal,
  )
  return res.orders
}

export async function fetchMyOrderDetail(
  name: string,
  signal?: AbortSignal,
): Promise<CustomerOrderDetail> {
  const res = await frappeFetch<{ record: CustomerOrderDetail }>(
    `${BASE}.get_my_order_detail`,
    { name },
    signal,
  )
  return res.record
}
