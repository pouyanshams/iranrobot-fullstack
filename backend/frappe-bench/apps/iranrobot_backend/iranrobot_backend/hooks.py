app_name = "iranrobot_backend"
app_title = "IranRobot Backend"
app_publisher = "IranRobot"
app_description = "Product catalog + commerce backend for IranRobot."
app_email = "team@iranrobot.example"
app_license = "MIT"

# Public whitelisted methods (discovered by dotted module path, not
# hook-registered):
#
#   Phase 2 -- catalog (guest-readable):
#     iranrobot_backend.api.catalog.get_categories
#     iranrobot_backend.api.catalog.get_products
#     iranrobot_backend.api.catalog.get_product_detail
#     iranrobot_backend.api.catalog.get_featured_product
#     iranrobot_backend.api.catalog.get_homepage_catalog
#
#   Phase 4 -- authentication (mixed guest / auth-required):
#     iranrobot_backend.api.auth.whoami         GET   allow_guest=True
#     iranrobot_backend.api.auth.login          POST  allow_guest=True
#     iranrobot_backend.api.auth.logout         POST  auth required
#     iranrobot_backend.api.auth.update_profile POST  auth required
#
#   Phase 4.5 -- signup (guest, creates Website User):
#     iranrobot_backend.api.auth.signup         POST  allow_guest=True
#
#   Phase 5 -- request intake (mixed guest / auth-required):
#     iranrobot_backend.api.requests.submit_quote_request       POST  allow_guest=True
#     iranrobot_backend.api.requests.submit_procurement_request POST  allow_guest=True
#     iranrobot_backend.api.requests.submit_support_ticket      POST  allow_guest=True
#
#   Phase 6 -- customer dashboard reads (auth required at app level):
#     iranrobot_backend.api.requests.get_my_requests            GET
#     iranrobot_backend.api.requests.get_my_request_detail      GET
#
#   Phase 7A -- staff-only Quote Request -> ERPNext Quotation bridge:
#     iranrobot_backend.api.requests.convert_quote_request_to_quotation POST (Sales role)
#
#   Phase 7A.1 -- customer address management + quotation autofill:
#     iranrobot_backend.api.account.get_my_addresses    GET   auth required
#     iranrobot_backend.api.account.save_my_address     POST  auth required
#     iranrobot_backend.api.account.delete_my_address   POST  auth required
#   (the convert endpoint now autofills contact_person / customer_address /
#    shipping_address_name on new Quotations when they're available)
#
#   Phase 7B -- customer Accept / Reject on a Sent ERPNext Quotation:
#     iranrobot_backend.api.requests.respond_to_quotation POST  auth required
#   (records the decision on Robot Quote Request only; does NOT create a Sales
#    Order or touch ERPNext Quotation.docstatus -- that's deferred to 7C)
#
#   Phase 7C -- staff Accepted Quotation -> ERPNext Sales Order + customer reads:
#     iranrobot_backend.api.requests.convert_accepted_quote_to_sales_order POST  Sales role
#     iranrobot_backend.api.orders.get_my_orders                            GET   auth required
#     iranrobot_backend.api.orders.get_my_order_detail                      GET   auth required
#   (Sales Order is created in Draft; staff still submits in Desk.)
#
#   Phase 7D -- staff Sales Order -> ERPNext Sales Invoice + read-only payment view:
#     iranrobot_backend.api.requests.convert_sales_order_to_sales_invoice   POST  Sales/Accounts role
#     iranrobot_backend.api.invoices.get_my_invoices                        GET   auth required
#     iranrobot_backend.api.invoices.get_my_invoice_detail                  GET   auth required
#   (Sales Invoice is created in Draft; staff submits + records Payment Entry
#    manually in Desk. The customer dashboard surfaces invoice + paid /
#    outstanding / payment summary read-only -- no Pay Now button is added.)
#
#   Phase 8A -- customer wallet read foundation (ledger DocTypes + lazy creation):
#     iranrobot_backend.api.wallet.get_wallet_summary       GET   auth required
#     iranrobot_backend.api.wallet.get_wallet_transactions  GET   auth required
#   (8A is read-only; balance is derived from submitted Robot Wallet Transaction
#    rows and cached on Robot Wallet Account.)
#
#   Phase 8B -- manual/offline top-up flow (customer create + staff approve/reject):
#     iranrobot_backend.api.wallet.get_my_top_up_requests        GET   auth required
#     iranrobot_backend.api.wallet.create_top_up_request         POST  auth required, customer
#     iranrobot_backend.api.wallet.cancel_top_up_request         POST  auth required, customer (own Pending only)
#     iranrobot_backend.api.wallet.staff_approve_top_up_request  POST  Accounts/System Manager role
#     iranrobot_backend.api.wallet.staff_reject_top_up_request   POST  Accounts/System Manager role
#   (Approval creates exactly one submitted Robot Wallet Transaction of type
#    Top Up via the idempotency_key `topup-request:<request_name>`. Phase 8B
#    deliberately does NOT create ERPNext Payment Entry, Mode of Payment, or
#    "Customer Wallet Liability" account -- the wallet ledger is the sole
#    source of truth. ERPNext accounting integration lands in a later
#    accounting-hardening phase after Company defaults, Accounts, and Mode of
#    Payment are explicitly configured.)
#
#   `get_wallet_summary` (extended in 8B): now returns `pending_top_ups` and
#   `can_top_up: true`. `can_spend` remains False until Phase 8D.
#
#   Phase 8D-3 -- invoice detail extended with `wallet_payments`:
#     `iranrobot_backend.api.invoices.get_my_invoice_detail` response now
#     additionally returns `wallet_payments` -- a list of Robot Wallet
#     Transaction (Spend) rows targeting the invoice, with `journal_entry`
#     derived from JE.user_remark. The Phase 7D `payments` field (PE-based)
#     is unchanged.
#
#   Phase 8D-2 -- customer-facing Pay-Sales-Invoice-with-Wallet:
#     iranrobot_backend.api.wallet.get_wallet_payment_status     GET   auth required, customer
#     iranrobot_backend.api.wallet.pay_invoice_with_wallet       POST  auth required, customer
#   (Settlement uses a Journal Entry, NOT a Payment Entry, because the 8D-0
#    spike proved PE rejects when both legs hit Receivable accounts. The JE
#    debits Customer Wallet Liability and credits the SI's debit_to with the
#    Sales Invoice reference -- ERPNext's JE→SI allocator then reduces
#    outstanding_amount and flips status. Because SI is updated via direct
#    SQL inside the JE submit, SI.on_update doesn't fire; we sync the linked
#    Robot Quote Request explicitly via _sync_qr_after_wallet_settlement.
#    Atomic: TX + JE + QR sync all in one transaction, rollback on any
#    exception. Idempotency key `invoice-pay:<si>:<cents>` -- duplicate calls
#    with the same amount return the existing TX+JE.)
#
# Wallet gateway / refund / reconciliation APIs remain deferred to
# 8F / 8G.

# Phase 7A -- keep Robot Quote Request.quotation_status and proposal_amount_usd
# in sync when staff edits / submits / cancels the linked Quotation in Desk.
# The handler silently no-ops for Quotations that aren't back-linked, so it's
# safe to register globally.
doc_events = {
    "Quotation": {
        "on_update": "iranrobot_backend.api.requests.sync_quotation_back_to_quote_request",
        "on_submit": "iranrobot_backend.api.requests.sync_quotation_back_to_quote_request",
        "on_cancel": "iranrobot_backend.api.requests.sync_quotation_back_to_quote_request",
    },
    # Phase 7C -- keep Robot Quote Request.sales_order_status +
    # sales_order_grand_total_usd in sync with the linked Sales Order as staff
    # progresses it through the ERPNext lifecycle. The handler silently no-ops
    # for Sales Orders that aren't back-linked, so it's safe to register
    # globally.
    "Sales Order": {
        "on_update": "iranrobot_backend.api.requests.sync_sales_order_back_to_quote_request",
        "on_submit": "iranrobot_backend.api.requests.sync_sales_order_back_to_quote_request",
        "on_cancel": "iranrobot_backend.api.requests.sync_sales_order_back_to_quote_request",
    },
    # Phase 7D -- keep Robot Quote Request's invoice + payment snapshot fields
    # current. Sales Invoice fires on every staff edit; Payment Entry fires
    # only on submit / cancel because Draft PEs don't update the invoice's
    # outstanding amount in ERPNext.
    "Sales Invoice": {
        "on_update": "iranrobot_backend.api.requests.sync_sales_invoice_back_to_quote_request",
        "on_submit": "iranrobot_backend.api.requests.sync_sales_invoice_back_to_quote_request",
        "on_cancel": "iranrobot_backend.api.requests.sync_sales_invoice_back_to_quote_request",
    },
    "Payment Entry": {
        "on_submit": "iranrobot_backend.api.requests.sync_payment_entry_back_to_quote_request",
        "on_cancel": "iranrobot_backend.api.requests.sync_payment_entry_back_to_quote_request",
    },
}

  # Phase 8E -- reconcile every wallet once a day:
#   compares Robot Wallet Account.balance_usd vs the submitted ledger SUM
#   vs the Customer Wallet Liability partywise GL balance. Mismatches above
#   the threshold auto-freeze the wallet; sub-threshold drift is logged.
scheduler_events = {
    "daily": [
        "iranrobot_backend.wallet.reconciliation.reconcile_all_daily",
    ],
}

# No fixtures yet — Phase 1 only ships schema. Seeding from
# ../iranrobot/src/data/robots.ts is a separate Phase 1.5 task.
fixtures = []

# Phase 4 hotfix -- divert Website-User customers away from the legacy
# ERPNext portal (which renders a sidebar full of Not-Permitted links)
# and toward the React SPA where the real customer surface lives.
# See iranrobot_backend/website.py for the full rationale + skip-list.
before_request = [
    "iranrobot_backend.website.before_request_redirect_customers",
]
