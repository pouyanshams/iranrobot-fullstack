"""Phase 8A + 8B -- Customer-facing Wallet APIs.

    iranrobot_backend.api.wallet.get_wallet_summary             GET   auth required
    iranrobot_backend.api.wallet.get_wallet_transactions        GET   auth required
    iranrobot_backend.api.wallet.get_my_top_up_requests         GET   auth required          (8B)
    iranrobot_backend.api.wallet.create_top_up_request          POST  auth required, customer (8B)
    iranrobot_backend.api.wallet.cancel_top_up_request          POST  auth required, customer (8B)
    iranrobot_backend.api.wallet.staff_approve_top_up_request   POST  auth required, staff    (8B)
    iranrobot_backend.api.wallet.staff_reject_top_up_request    POST  auth required, staff    (8B)

Phase 8B does NOT create ERPNext Payment Entry, Mode of Payment, or
"Customer Wallet Liability" account. The wallet ledger is the sole source of
truth. ERPNext accounting integration is deferred to a later accounting-
hardening phase.

Identity / ownership:
    Every customer-facing endpoint derives `customer` and `wallet` from
    `frappe.session.user` -- they are NEVER read from the request body. Cross-
    customer reads return NOT_FOUND (no existence leak via id enumeration).
    Staff endpoints require an explicit role check (`_has_accounts_role`).
"""

from __future__ import annotations

import frappe
from frappe import _

from iranrobot_backend.api._response import err, ok
from iranrobot_backend.api._session import (
    get_or_create_customer_for_user,
    get_or_create_wallet_for_customer,
    is_guest,
    is_system_manager,
)
from iranrobot_backend.commands.wallet_accounting_bootstrap import (
    COMPANY as _WALLET_COMPANY,
    WALLET_LIABILITY_ACCOUNT,
    WALLET_MOP,
)


# Phase 8D-1 -- ERPNext accounting constants used by the top-up Payment Entry
# helper. The proven Test A pattern from the 8D-0 spike sets:
#   payment_type=Receive, party_type=Customer
#   paid_from=Customer Wallet Liability - IR  (party_account; credits liability)
#   paid_to  =Cash - IR                       (debits cash)
# Cash account is currently hard-coded; future phases may add a bank account
# selection per top-up method (Bank Transfer vs Cash Deposit).
_WALLET_CASH_ACCOUNT = "Cash - IR"


# ---------- Customer-safe field allow-lists ----------

_WALLET_SUMMARY_FIELDS = (
    "name",
    "customer",
    "currency",
    "status",
    "balance_usd",
    "available_balance_usd",
    "last_transaction_at",
    # Phase 8E: informational reconciliation snapshot. `last_reconciliation_delta_usd`
    # is intentionally NOT included -- the precise delta is staff/audit data.
    "last_reconciliation_status",
    "last_reconciliation_at",
)

_TX_LIST_FIELDS = (
    "name",
    "transaction_type",
    "direction",
    "currency",
    "credit_amount_usd",
    "debit_amount_usd",
    "balance_after_usd",
    "posted_at",
    "linked_top_up_request",
    "linked_sales_invoice",
    "linked_quote_request",
    "notes",
)

_TOPUP_LIST_FIELDS = (
    "name",
    "status",
    "amount_usd",
    "currency",
    "method",
    "submitted_at",
    "approved_at",
    "rejected_at",
    "cancelled_at",
    "customer_note",
    "bank_reference",
    "rejection_reason",
    "linked_transaction",
)


# ---------- Persian-digit normalization (mirrors api/account.py) ----------
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# ---------- Top-up bounds ----------
_MIN_TOPUP_USD = 1.0
_MAX_TOPUP_USD = 50_000.0
_ALLOWED_METHODS = {"Bank Transfer", "Cash Deposit"}
# Phase 8C hardening: cap the per-customer Pending backlog so a runaway client
# can't flood the staff queue.
_MAX_PENDING_PER_WALLET = 5


# ---------- Bank instructions (static for 8B; gateway/dynamic comes in 8F) ----------

_BANK_INSTRUCTIONS = {
    "beneficiary": "IranRobot",
    "bank_name": "Example Bank",
    "iban": "IR-XX-XXXX-XXXX-XXXX-XXXX-XXXX-XX",
    "currency": "USD",
}


# =============================================================== helpers

def _project(doc: dict, allow_list: tuple) -> dict:
    return {k: doc.get(k) for k in allow_list if k in doc}


def _resolve_customer() -> str | None:
    if is_guest():
        return None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(frappe.session.user)
        return cust_id
    except Exception as e:
        frappe.log_error(title="wallet._resolve_customer", message=str(e))
        return None


def _resolve_wallet() -> tuple[str | None, str | None]:
    """Return (customer_name, wallet_name) for the session user. Either may be
    None for staff sessions (Administrator / System Manager) -- those users
    deliberately have no Customer / wallet."""
    cust_id = _resolve_customer()
    if not cust_id:
        return None, None
    try:
        return cust_id, get_or_create_wallet_for_customer(cust_id)
    except Exception as e:
        frappe.log_error(title="wallet._resolve_wallet", message=str(e))
        return cust_id, None


def _wallet_payload(wallet_name: str) -> dict:
    row = frappe.db.get_value(
        "Robot Wallet Account",
        wallet_name,
        list(_WALLET_SUMMARY_FIELDS),
        as_dict=True,
    ) or {}
    return _project(row, _WALLET_SUMMARY_FIELDS)


def _has_accounts_role(user_email: str) -> bool:
    """True iff the user can approve/reject top-ups. Mirrors the role-set we
    use for Phase 7D's `convert_sales_order_to_sales_invoice`."""
    if not user_email or user_email == "Guest":
        return False
    if user_email == "Administrator":
        return True
    roles = set(frappe.get_roles(user_email))
    return bool(roles & {"System Manager", "Accounts Manager", "Accounts User"})


def _normalize_amount(raw) -> float | None:
    """Accept Persian or ASCII digits, return a non-negative float or None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().translate(_PERSIAN_DIGITS)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pending_top_ups_for(wallet_name: str, limit: int = 5) -> list[dict]:
    rows = frappe.get_all(
        "Robot Wallet Top Up Request",
        filters={"wallet": wallet_name, "status": "Pending"},
        fields=list(_TOPUP_LIST_FIELDS),
        order_by="submitted_at desc, creation desc",
        page_length=limit,
        ignore_permissions=True,
    )
    return [_project(r, _TOPUP_LIST_FIELDS) for r in rows]


# =============================================================== GET get_wallet_summary

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_wallet_summary():
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        # Staff session: no wallet, no top-ups.
        return ok({
            "wallet": None,
            "pending_top_ups": [],
            "can_top_up": False,
            "can_spend": False,
        })
    if not wallet_name:
        return err("SERVER_ERROR", _("Could not load your wallet."))

    payload = _wallet_payload(wallet_name)
    try:
        pending = _pending_top_ups_for(wallet_name, limit=5)
    except Exception as e:
        frappe.log_error(title="get_wallet_summary pending", message=str(e))
        pending = []

    return ok({
        "wallet": payload,
        "pending_top_ups": pending,
        # Phase 8B: top-up flow is live; spend lands in 8D.
        "can_top_up": True,
        "can_spend": False,
    })


# =============================================================== GET get_wallet_transactions

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_wallet_transactions(limit: int = 20, offset: int = 0):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        return ok({"transactions": [], "total_count": 0})
    if not wallet_name:
        return err("SERVER_ERROR", _("Could not load your wallet."))

    try:
        limit_n = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_n = 20
    try:
        offset_n = max(0, int(offset))
    except (TypeError, ValueError):
        offset_n = 0

    try:
        rows = frappe.get_all(
            "Robot Wallet Transaction",
            filters={"wallet": wallet_name, "docstatus": 1},
            fields=list(_TX_LIST_FIELDS),
            order_by="posted_at desc, creation desc",
            start=offset_n,
            page_length=limit_n,
            ignore_permissions=True,
        )
        total = frappe.db.count(
            "Robot Wallet Transaction",
            {"wallet": wallet_name, "docstatus": 1},
        )
    except Exception as e:
        frappe.log_error(title="get_wallet_transactions list", message=str(e))
        return err("SERVER_ERROR", _("Could not load your transactions."))

    return ok({
        "transactions": [_project(r, _TX_LIST_FIELDS) for r in rows],
        "total_count": total,
    })


# =============================================================== GET get_my_top_up_requests

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_top_up_requests(limit: int = 20, offset: int = 0, status: str | None = None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id or not wallet_name:
        return ok({"top_up_requests": [], "total_count": 0})

    try:
        limit_n = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_n = 20
    try:
        offset_n = max(0, int(offset))
    except (TypeError, ValueError):
        offset_n = 0

    filters = {"wallet": wallet_name}
    if status and status in {"Pending", "Approved", "Rejected", "Cancelled"}:
        filters["status"] = status

    try:
        rows = frappe.get_all(
            "Robot Wallet Top Up Request",
            filters=filters,
            fields=list(_TOPUP_LIST_FIELDS),
            order_by="submitted_at desc, creation desc",
            start=offset_n,
            page_length=limit_n,
            ignore_permissions=True,
        )
        total = frappe.db.count("Robot Wallet Top Up Request", filters)
    except Exception as e:
        frappe.log_error(title="get_my_top_up_requests", message=str(e))
        return err("SERVER_ERROR", _("Could not load your top-up requests."))

    return ok({
        "top_up_requests": [_project(r, _TOPUP_LIST_FIELDS) for r in rows],
        "total_count": total,
    })


# =============================================================== POST create_top_up_request

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_top_up_request(amount_usd=None, method=None, customer_note=None):
    """Create a Pending top-up request for the session user's wallet.

    The client only sends `amount_usd`, `method`, and `customer_note`. The
    `customer`, `user`, `wallet`, `submitted_at`, and `posted_ip` fields are
    all populated server-side from `frappe.session.user`. Anything else the
    client may send is ignored.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    actor = frappe.session.user
    # Staff users (Administrator / System Manager) have no Customer record and
    # must not create wallet top-ups for themselves. They use the Desk forms
    # or the approval API to act on behalf of customers.
    if actor == "Administrator" or is_system_manager(actor):
        return err("NOT_PERMITTED", _("Staff cannot create wallet top-ups for themselves."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        return err("CUSTOMER_REQUIRED", _("No linked customer found for this session."))
    if not wallet_name:
        return err("SERVER_ERROR", _("Could not load your wallet."))

    # Phase 8E: a Frozen wallet (auto-frozen by reconciliation, or set manually
    # by a System Manager) refuses new top-up requests until an accountant
    # restores it to Active. Read APIs stay open so the customer can still see
    # their balance and history.
    wallet_status = frappe.db.get_value(
        "Robot Wallet Account", wallet_name, "status"
    )
    if wallet_status == "Frozen":
        return err(
            "WALLET_FROZEN",
            _(
                "Your wallet is currently frozen pending accounting review. "
                "Please contact support."
            ),
        )

    amt = _normalize_amount(amount_usd)
    if amt is None:
        return err("VALIDATION_ERROR", _("amount_usd is required and must be a number."))
    if amt <= 0:
        return err("VALIDATION_ERROR", _("amount_usd must be positive."))
    if amt < _MIN_TOPUP_USD:
        return err(
            "VALIDATION_ERROR",
            _("Minimum top-up is ${0:.2f} USD.").format(_MIN_TOPUP_USD),
        )
    if amt > _MAX_TOPUP_USD:
        return err(
            "VALIDATION_ERROR",
            _("Maximum top-up is ${0:.2f} USD per request.").format(_MAX_TOPUP_USD),
        )

    if not method:
        method = "Bank Transfer"
    if method not in _ALLOWED_METHODS:
        return err(
            "VALIDATION_ERROR",
            _("Invalid method. Allowed: {0}.").format(", ".join(sorted(_ALLOWED_METHODS))),
        )

    note = (customer_note or "").strip()[:1000] or None
    posted_ip = (
        getattr(frappe.local, "request_ip", None)
        or getattr(getattr(frappe.local, "request", None), "remote_addr", None)
        or ""
    )

    # Phase 8C hardening: refuse to create a 6th simultaneous Pending row.
    try:
        pending_count = frappe.db.count(
            "Robot Wallet Top Up Request",
            {"wallet": wallet_name, "status": "Pending"},
        )
    except Exception:
        pending_count = 0
    if pending_count >= _MAX_PENDING_PER_WALLET:
        return err(
            "TOO_MANY_PENDING",
            _(
                "You already have {0} pending top-up requests; please wait for "
                "staff to process them before creating a new one."
            ).format(pending_count),
        )

    try:
        doc = frappe.get_doc({
            "doctype": "Robot Wallet Top Up Request",
            "customer": cust_id,
            "user": actor,
            "wallet": wallet_name,
            "amount_usd": amt,
            "currency": "USD",
            "method": method,
            "status": "Pending",
            "submitted_at": frappe.utils.now_datetime(),
            "customer_note": note,
            "posted_ip": posted_ip,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="create_top_up_request", message=str(e))
        return err("SERVER_ERROR", _("Could not create your top-up request."))

    return ok({
        "request_id": doc.name,
        "status": doc.status,
        "amount_usd": float(doc.amount_usd or 0),
        "currency": doc.currency,
        "submitted_at": doc.submitted_at,
        "instructions": {
            **_BANK_INSTRUCTIONS,
            "reference": doc.name,
        },
    })


# =============================================================== POST cancel_top_up_request

@frappe.whitelist(allow_guest=True, methods=["POST"])
def cancel_top_up_request(name=None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))
    if not name:
        return err("VALIDATION_ERROR", _("name is required."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        return err("NOT_FOUND", _("Top-up request not found."))

    row = frappe.db.get_value(
        "Robot Wallet Top Up Request",
        name,
        ["name", "customer", "status"],
        as_dict=True,
    )
    # Cross-customer or non-existent: indistinguishable error (no leak).
    if not row or row.customer != cust_id:
        return err("NOT_FOUND", _("Top-up request not found."))

    if row.status != "Pending":
        return err(
            "STATUS_NOT_CANCELLABLE",
            _("Top-up request is in status {0}; only Pending requests can be cancelled.").format(row.status),
        )

    posted_ip = (
        getattr(frappe.local, "request_ip", None)
        or getattr(getattr(frappe.local, "request", None), "remote_addr", None)
        or ""
    )

    try:
        now = frappe.utils.now_datetime()
        frappe.db.set_value(
            "Robot Wallet Top Up Request",
            name,
            {
                "status": "Cancelled",
                "cancelled_at": now,
                "cancelled_by": frappe.session.user,
                # Phase 8C hardening: snapshot IP at cancel time for audit.
                "cancelled_ip": posted_ip,
            },
            update_modified=True,
        )
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="cancel_top_up_request", message=str(e))
        return err("SERVER_ERROR", _("Could not cancel your top-up request."))

    return ok({
        "request_id": name,
        "status": "Cancelled",
        "cancelled_at": frappe.db.get_value("Robot Wallet Top Up Request", name, "cancelled_at"),
        "cancelled_by": frappe.session.user,
    })


# =============================================================== Phase 8D-1 PE helpers

def _accounting_ready() -> bool:
    """Return True iff the ERPNext objects required by the top-up Payment
    Entry exist.

    The wallet_accounting_bootstrap command creates these in dev. The
    `staff_approve_top_up_request` path refuses to run until they're all
    present so we never increase a customer's wallet balance without also
    creating the matching accounting entry.
    """
    return bool(
        frappe.db.exists("Account", WALLET_LIABILITY_ACCOUNT)
        and frappe.db.exists("Account", _WALLET_CASH_ACCOUNT)
        and frappe.db.exists("Mode of Payment", WALLET_MOP)
    )


def _find_existing_topup_pe(top_up_request_name: str, customer: str) -> str | None:
    """Return the name of a submitted top-up Payment Entry that matches this
    Robot Wallet Top Up Request, or None.

    Match criteria: docstatus=1, party=customer, paid_from=Wallet Liability,
    reference_no=top_up_request_name. The reference_no field is the canonical
    soft idempotency token for top-up PEs in this project.
    """
    return frappe.db.get_value(
        "Payment Entry",
        {
            "reference_no": top_up_request_name,
            "party": customer,
            "party_type": "Customer",
            "paid_from": WALLET_LIABILITY_ACCOUNT,
            "payment_type": "Receive",
            "docstatus": 1,
        },
        "name",
    )


def _create_topup_pe(request_doc) -> str:
    """Create and submit a top-up Payment Entry using the proven Test A
    pattern from the Phase 8D-0 spike. Returns the new PE name.

    The caller is responsible for idempotency -- check
    `_find_existing_topup_pe` first.
    """
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "naming_series": "ACC-PAY-.YYYY.-",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": request_doc.customer,
        "company": _WALLET_COMPANY,
        "posting_date": frappe.utils.today(),
        "mode_of_payment": WALLET_MOP,
        "paid_from": WALLET_LIABILITY_ACCOUNT,
        "paid_from_account_currency": "USD",
        "paid_to": _WALLET_CASH_ACCOUNT,
        "paid_to_account_currency": "USD",
        "paid_amount": float(request_doc.amount_usd or 0),
        "received_amount": float(request_doc.amount_usd or 0),
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": request_doc.name,
        "reference_date": frappe.utils.today(),
    })
    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe.name


# =============================================================== POST staff_approve_top_up_request

@frappe.whitelist(allow_guest=True, methods=["POST"])
def staff_approve_top_up_request(name=None, bank_reference=None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))
    actor = frappe.session.user
    if not _has_accounts_role(actor):
        return err("NOT_PERMITTED", _("Approval requires Accounts User, Accounts Manager, or System Manager role."))
    if not name:
        return err("VALIDATION_ERROR", _("name is required."))

    # Lock the request row to serialize concurrent approvals.
    rows = frappe.db.sql(
        """
        SELECT name, customer, wallet, amount_usd, status,
               linked_transaction, linked_payment_entry,
               approved_at, approved_by, user
          FROM `tabRobot Wallet Top Up Request`
         WHERE name = %s
         FOR UPDATE
        """,
        (name,),
        as_dict=True,
    )
    if not rows:
        return err("NOT_FOUND", _("Top-up request not found."))
    request = rows[0]

    # Self-approve guard (defense-in-depth on top of the role guard above).
    if request.user == actor:
        return err("NOT_PERMITTED", _("You cannot approve your own top-up request."))

    if request.status == "Approved":
        # Idempotent return -- the linked transaction already exists and the
        # wallet balance already reflects this credit.
        balance = frappe.db.get_value("Robot Wallet Account", request.wallet, "balance_usd")
        return ok({
            "request_id": request.name,
            "status": "Approved",
            "transaction_id": request.linked_transaction,
            "payment_entry": request.linked_payment_entry,
            "new_balance_usd": float(balance or 0),
            "approved_at": request.approved_at,
            "approved_by": request.approved_by,
            "bank_reference": frappe.db.get_value(
                "Robot Wallet Top Up Request", request.name, "bank_reference"
            ),
            "idempotent": True,
        })
    if request.status in ("Rejected", "Cancelled"):
        return err(
            "STATUS_NOT_APPROVABLE",
            _("Top-up request is in status {0}; only Pending requests can be approved.").format(request.status),
        )

    # Phase 8D-1: accounting preflight. Refuse to credit the wallet ledger if
    # the matching ERPNext objects do not exist -- we'd be unable to mirror
    # the credit into GL, which would leave the wallet liability account out
    # of sync with the customer's wallet balance.
    if not _accounting_ready():
        return err(
            "ACCOUNTING_NOT_READY",
            _(
                "Wallet accounting setup is missing. Ask an administrator to "
                "run `bench execute iranrobot_backend.commands."
                "wallet_accounting_bootstrap.run` before approving top-ups."
            ),
        )

    # Phase 8E: a Frozen wallet refuses new credits. The previously-approved
    # branch above already short-circuits, so re-running approve on an existing
    # Approved request still works even after the wallet was frozen -- we only
    # block the path that would mint a fresh credit.
    wallet_status = frappe.db.get_value(
        "Robot Wallet Account", request.wallet, "status"
    )
    if wallet_status == "Frozen":
        return err(
            "WALLET_FROZEN",
            _(
                "The customer's wallet is currently frozen pending accounting "
                "review. Resolve the reconciliation mismatch and restore the "
                "wallet to Active before approving new top-ups."
            ),
        )

    idempotency_key = f"topup-request:{request.name}"

    # If a previous run inserted the transaction but failed to flip the
    # request status (crashed between submit and set_value), recover by
    # linking the existing transaction and finalising the status.
    existing_tx = frappe.db.get_value(
        "Robot Wallet Transaction",
        {"idempotency_key": idempotency_key, "docstatus": 1},
        "name",
    )

    pe_name: str | None = None
    try:
        if existing_tx:
            tx_name = existing_tx
        else:
            tx = frappe.get_doc({
                "doctype": "Robot Wallet Transaction",
                "wallet": request.wallet,
                "transaction_type": "Top Up",
                "currency": "USD",
                "credit_amount_usd": float(request.amount_usd or 0),
                "debit_amount_usd": 0,
                "idempotency_key": idempotency_key,
                "linked_top_up_request": request.name,
                "notes": f"Top-up approved by {actor}",
                "posted_at": frappe.utils.now_datetime(),
            })
            tx.insert(ignore_permissions=True)
            tx.submit()
            tx_name = tx.name

        # Phase 8D-1: create + submit the matching ERPNext Payment Entry.
        # The whole block (TX + PE + status flip) is in one MariaDB
        # transaction -- if PE creation throws, rollback reverts the TX too.
        # _find_existing_topup_pe handles the rare recovery case where a
        # previous run committed the TX but crashed before creating the PE.
        existing_pe = _find_existing_topup_pe(request.name, request.customer)
        if existing_pe:
            pe_name = existing_pe
        else:
            request_doc = frappe.get_doc("Robot Wallet Top Up Request", request.name)
            pe_name = _create_topup_pe(request_doc)

        # Invariant check: cache must equal ledger sum, hard-fail otherwise.
        ledger_balance = frappe.db.sql(
            """
            SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0)
              FROM `tabRobot Wallet Transaction`
             WHERE wallet     = %s
               AND docstatus  = 1
            """,
            (request.wallet,),
        )[0][0]
        cached_balance = frappe.db.get_value(
            "Robot Wallet Account", request.wallet, "balance_usd"
        )
        if abs(float(cached_balance or 0) - float(ledger_balance or 0)) > 0.005:
            frappe.db.rollback()
            frappe.log_error(
                title="staff_approve_top_up_request cache drift",
                message=(
                    f"wallet={request.wallet} request={request.name} "
                    f"cached={cached_balance} ledger={ledger_balance}"
                ),
            )
            return err(
                "WALLET_CACHE_DRIFT",
                _("Wallet cached balance does not match the ledger sum; approval aborted."),
            )

        # set_value bypasses the controller's validate() -- the
        # `_block_linked_payment_entry` guard there is by design only a fence
        # for Desk and uncontrolled save() paths. Trusted backend approval +
        # backfill write linked_payment_entry via this set_value bridge.
        now = frappe.utils.now_datetime()
        frappe.db.set_value(
            "Robot Wallet Top Up Request",
            request.name,
            {
                "status": "Approved",
                "approved_at": now,
                "approved_by": actor,
                "linked_transaction": tx_name,
                "linked_payment_entry": pe_name,
                "bank_reference": bank_reference or frappe.db.get_value(
                    "Robot Wallet Top Up Request", request.name, "bank_reference"
                ),
                "approval_idempotency_key": idempotency_key,
            },
            update_modified=True,
        )
        frappe.db.commit()
    except frappe.UniqueValidationError as e:
        # A concurrent approval inserted the transaction first. Recover by
        # reading the existing transaction and finalising on top of it.
        frappe.db.rollback()
        tx_name = frappe.db.get_value(
            "Robot Wallet Transaction",
            {"idempotency_key": idempotency_key, "docstatus": 1},
            "name",
        )
        if not tx_name:
            frappe.log_error(title="staff_approve_top_up_request race", message=str(e))
            return err("SERVER_ERROR", _("Could not approve due to a concurrent write."))
        # The TX exists; the matching PE may or may not. Reuse the existing
        # PE if any, else create one now.
        pe_name = _find_existing_topup_pe(request.name, request.customer)
        if not pe_name:
            try:
                request_doc = frappe.get_doc("Robot Wallet Top Up Request", request.name)
                pe_name = _create_topup_pe(request_doc)
            except Exception as pe_err:
                frappe.db.rollback()
                frappe.log_error(
                    title="staff_approve_top_up_request PE recovery failed",
                    message=str(pe_err),
                )
                return err(
                    "SERVER_ERROR",
                    _("Could not create the matching Payment Entry during recovery."),
                )
        now = frappe.utils.now_datetime()
        frappe.db.set_value(
            "Robot Wallet Top Up Request",
            request.name,
            {
                "status": "Approved",
                "approved_at": now,
                "approved_by": actor,
                "linked_transaction": tx_name,
                "linked_payment_entry": pe_name,
                "bank_reference": bank_reference,
                "approval_idempotency_key": idempotency_key,
            },
            update_modified=True,
        )
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="staff_approve_top_up_request", message=str(e))
        return err("SERVER_ERROR", _("Could not approve your top-up request."))

    new_balance = frappe.db.get_value(
        "Robot Wallet Account", request.wallet, "balance_usd"
    )
    return ok({
        "request_id": request.name,
        "status": "Approved",
        "transaction_id": tx_name,
        "payment_entry": pe_name,
        "new_balance_usd": float(new_balance or 0),
        "approved_at": frappe.db.get_value(
            "Robot Wallet Top Up Request", request.name, "approved_at"
        ),
        "approved_by": actor,
        "bank_reference": frappe.db.get_value(
            "Robot Wallet Top Up Request", request.name, "bank_reference"
        ),
        "idempotent": bool(existing_tx),
    })


# =============================================================== POST staff_reject_top_up_request

@frappe.whitelist(allow_guest=True, methods=["POST"])
def staff_reject_top_up_request(name=None, reason=None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))
    actor = frappe.session.user
    if not _has_accounts_role(actor):
        return err("NOT_PERMITTED", _("Rejection requires Accounts User, Accounts Manager, or System Manager role."))
    if not name:
        return err("VALIDATION_ERROR", _("name is required."))
    reason_clean = (reason or "").strip()
    if not reason_clean:
        return err("VALIDATION_ERROR", _("reason is required."))

    rows = frappe.db.sql(
        """
        SELECT name, customer, status, rejected_at, rejected_by, rejection_reason, user
          FROM `tabRobot Wallet Top Up Request`
         WHERE name = %s
         FOR UPDATE
        """,
        (name,),
        as_dict=True,
    )
    if not rows:
        return err("NOT_FOUND", _("Top-up request not found."))
    request = rows[0]

    if request.user == actor:
        return err("NOT_PERMITTED", _("You cannot reject your own top-up request."))

    if request.status == "Rejected":
        # Idempotent
        return ok({
            "request_id": request.name,
            "status": "Rejected",
            "rejected_at": request.rejected_at,
            "rejected_by": request.rejected_by,
            "rejection_reason": request.rejection_reason,
            "idempotent": True,
        })
    if request.status in ("Approved", "Cancelled"):
        return err(
            "STATUS_NOT_REJECTABLE",
            _("Top-up request is in status {0}; only Pending requests can be rejected.").format(request.status),
        )

    try:
        now = frappe.utils.now_datetime()
        frappe.db.set_value(
            "Robot Wallet Top Up Request",
            request.name,
            {
                "status": "Rejected",
                "rejected_at": now,
                "rejected_by": actor,
                "rejection_reason": reason_clean,
            },
            update_modified=True,
        )
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="staff_reject_top_up_request", message=str(e))
        return err("SERVER_ERROR", _("Could not reject your top-up request."))

    return ok({
        "request_id": request.name,
        "status": "Rejected",
        "rejected_at": frappe.db.get_value(
            "Robot Wallet Top Up Request", request.name, "rejected_at"
        ),
        "rejected_by": actor,
        "rejection_reason": reason_clean,
        "idempotent": False,
    })


# =============================================================== Phase 8D-2 settlement helpers
#
# Pay-Sales-Invoice-with-Wallet uses a Journal Entry to settle the customer's
# invoice from the customer-wallet liability account. This was the only
# settlement shape the Phase 8D-0 spike could submit cleanly -- a Payment
# Entry that hits Receivable accounts on BOTH legs is rejected by ERPNext
# because PE's auto-party logic only sets `party` on the single party_account
# leg. A JE lets us declare `party` on both legs explicitly.


def _find_qr_for_si(sales_invoice_name: str) -> str | None:
    """Return the Robot Quote Request that owns this Sales Invoice, or None.

    The link is the QR.erpnext_sales_invoice field set when staff convert a
    Sales Order to a Sales Invoice (Phase 7D).
    """
    if not sales_invoice_name:
        return None
    return frappe.db.get_value(
        "Robot Quote Request",
        {"erpnext_sales_invoice": sales_invoice_name},
        "name",
    )


def _find_settlement_je_for_tx(wallet_tx_name: str) -> str | None:
    """Find the submitted Journal Entry that backs this Spend transaction.

    No schema-level back-link exists from Robot Wallet Transaction to JE;
    instead the JE's `user_remark` carries a stable marker
    ``wallet_tx=<tx_name>`` which we LIKE-search here. Single-row result by
    design -- the settlement path creates exactly one JE per Spend TX.
    """
    if not wallet_tx_name:
        return None
    return frappe.db.get_value(
        "Journal Entry",
        {
            "user_remark": ["like", f"%wallet_tx={wallet_tx_name}%"],
            "docstatus": 1,
        },
        "name",
    )


def _derive_si_payment_status(si: dict) -> str:
    """Customer-facing 5-value payment status derived from a Sales Invoice
    row dict. Mirrors `api/invoices.py:_payment_status_label` to avoid the
    cross-module import (it would be a fine import but this is hot-path
    code and we already duplicate the small shape elsewhere)."""
    status = (si.get("status") or "").strip()
    docstatus = si.get("docstatus")
    grand_total = float(si.get("grand_total") or 0)
    outstanding = float(si.get("outstanding_amount") or 0)
    if docstatus == 2:
        return "Cancelled"
    if status == "Paid":
        return "Paid"
    if status in ("Partly Paid", "Partly Paid and Discounted"):
        return "Partly Paid"
    if status in ("Overdue", "Overdue and Discounted"):
        return "Overdue"
    if status in ("Unpaid", "Unpaid and Discounted"):
        return "Unpaid"
    if docstatus == 0:
        return "Unpaid"
    if grand_total <= 0 or outstanding <= 0:
        return "Paid"
    if outstanding < grand_total:
        return "Partly Paid"
    return "Unpaid"


def _create_settlement_je(
    customer: str,
    sales_invoice_name: str,
    sales_invoice_debit_to: str,
    amount: float,
    wallet_tx_name: str,
) -> str:
    """Create and submit the settlement Journal Entry. Returns the JE name.

    Two-row JE:
      Row 1: DEBIT Customer Wallet Liability (party=Customer)   -> decreases liability
      Row 2: CREDIT <SI.debit_to> (party=Customer, reference_type=Sales Invoice,
             reference_name=<si>)                               -> decreases receivable
    ERPNext's JE-to-SI allocator updates the invoice's outstanding_amount and
    status on submit. The QR sync helper takes care of the snapshot fields on
    Robot Quote Request because the SI update is SQL-only and does not fire
    SI.on_update.
    """
    debit_to = sales_invoice_debit_to or "Debtors - IR"
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "posting_date": frappe.utils.today(),
        "company": _WALLET_COMPANY,
        "user_remark": (
            f"Phase 8D-2 wallet settlement | "
            f"wallet_tx={wallet_tx_name} | "
            f"sales_invoice={sales_invoice_name}"
        ),
        "accounts": [
            {
                "account": WALLET_LIABILITY_ACCOUNT,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "party_type": "Customer",
                "party": customer,
            },
            {
                "account": debit_to,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": amount,
                "party_type": "Customer",
                "party": customer,
                "reference_type": "Sales Invoice",
                "reference_name": sales_invoice_name,
            },
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


# =============================================================== GET get_wallet_payment_status

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_wallet_payment_status(sales_invoice_name=None):
    """Customer-facing read endpoint: given a Sales Invoice, return whether
    the session customer can pay it from their wallet and how much."""
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))
    actor = frappe.session.user
    if actor == "Administrator" or is_system_manager(actor):
        return err("NOT_PERMITTED", _("Staff cannot use Pay-with-Wallet."))
    if not sales_invoice_name:
        return err("VALIDATION_ERROR", _("sales_invoice_name is required."))

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        return err("NOT_PERMITTED", _("No customer linked to this session."))
    if not wallet_name:
        return err("SERVER_ERROR", _("Could not load your wallet."))

    # SI ownership + state lookup. Cross-customer or missing -> NOT_FOUND.
    si = frappe.db.get_value(
        "Sales Invoice", sales_invoice_name,
        [
            "name", "customer", "docstatus", "status", "currency",
            "outstanding_amount", "grand_total", "debit_to",
        ],
        as_dict=True,
    )
    if not si or si.customer != cust_id:
        return err("NOT_FOUND", _("Invoice not found."))

    wallet = frappe.db.get_value(
        "Robot Wallet Account", wallet_name,
        ["balance_usd", "available_balance_usd", "currency", "status"],
        as_dict=True,
    ) or {}

    outstanding = float(si.outstanding_amount or 0)
    balance = float(wallet.get("balance_usd") or 0)
    available = float(wallet.get("available_balance_usd") or balance)
    payment_status = _derive_si_payment_status(dict(si))

    blocked = None
    if si.currency != "USD":
        blocked = "CURRENCY_MISMATCH"
    elif si.docstatus == 0:
        blocked = "INVOICE_NOT_SUBMITTED"
    elif si.docstatus == 2 or si.status == "Cancelled":
        blocked = "INVOICE_CANCELLED"
    elif outstanding <= 0.005:
        blocked = "ALREADY_PAID"
    elif wallet.get("status") != "Active":
        blocked = "WALLET_FROZEN"
    elif balance <= 0.005:
        blocked = "INSUFFICIENT_FUNDS"

    max_payable = min(outstanding, balance) if blocked is None else 0.0

    response = {
        "invoice": {
            "name": si.name,
            "outstanding_usd": outstanding,
            "currency": si.currency,
            "status": si.status,
            "payment_status": payment_status,
            "grand_total_usd": float(si.grand_total or 0),
            "debit_to": si.debit_to,
        },
        "wallet": {
            "balance_usd": balance,
            "available_balance_usd": available,
            "currency": wallet.get("currency") or "USD",
            "status": wallet.get("status"),
        },
        "max_payable_usd": max_payable,
        "can_pay_with_wallet": blocked is None,
    }
    if blocked:
        response["blocked_reason"] = blocked
    return ok(response)


# =============================================================== POST pay_invoice_with_wallet

@frappe.whitelist(allow_guest=True, methods=["POST"])
def pay_invoice_with_wallet(sales_invoice_name=None, amount_usd=None):
    """Settle a Sales Invoice from the session customer's wallet.

    Creates:
      1. Submitted Robot Wallet Transaction (Spend) -- the ledger debit.
      2. Submitted ERPNext Journal Entry -- the GL movement that decreases
         the customer wallet liability and the SI receivable.
      3. QR snapshot (via _sync_qr_after_wallet_settlement) so the Phase 7D
         dashboard reflects the new outstanding/payment_status.

    Atomic: TX + JE + QR sync + status flip all happen inside one MariaDB
    transaction; commit only after the invariant check passes. On any
    exception, frappe.db.rollback reverts everything.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))
    actor = frappe.session.user
    if actor == "Administrator" or is_system_manager(actor):
        return err("NOT_PERMITTED", _("Staff cannot use Pay-with-Wallet."))
    if not sales_invoice_name:
        return err("VALIDATION_ERROR", _("sales_invoice_name is required."))

    if not _accounting_ready():
        return err(
            "ACCOUNTING_NOT_READY",
            _(
                "Wallet accounting setup is missing. Ask an administrator to "
                "run `bench execute iranrobot_backend.commands."
                "wallet_accounting_bootstrap.run` first."
            ),
        )

    cust_id, wallet_name = _resolve_wallet()
    if not cust_id:
        return err("NOT_PERMITTED", _("No customer linked to this session."))
    if not wallet_name:
        return err("SERVER_ERROR", _("Could not load your wallet."))

    # ---------- ownership + currency check (idempotency runs before state) ----------

    si = frappe.db.get_value(
        "Sales Invoice", sales_invoice_name,
        [
            "name", "customer", "docstatus", "status", "currency",
            "outstanding_amount", "grand_total", "debit_to",
        ],
        as_dict=True,
    )
    if not si or si.customer != cust_id:
        return err("NOT_FOUND", _("Invoice not found."))
    if si.currency != "USD":
        return err(
            "CURRENCY_MISMATCH",
            _("Wallet only supports USD invoices (got {0}).").format(si.currency),
        )

    # ---------- compute requested amount (idempotency key depends on it) ----------

    outstanding_preflight = float(si.outstanding_amount or 0)
    if amount_usd in (None, "",):
        balance_preflight = float(
            frappe.db.get_value("Robot Wallet Account", wallet_name, "balance_usd") or 0
        )
        amount = round(min(outstanding_preflight, balance_preflight), 2)
    else:
        normalized = _normalize_amount(amount_usd)
        if normalized is None:
            return err("VALIDATION_ERROR", _("amount_usd must be a number."))
        amount = round(float(normalized), 2)

    if amount <= 0.005:
        return err("VALIDATION_ERROR", _("amount_usd must be positive."))

    # ---------- idempotency: identical (invoice, amount) returns existing ----------
    # Runs BEFORE the outstanding/status state checks so a duplicate request
    # against an already-settled invoice still returns the existing TX/JE
    # (which is what produced the settled state).

    amount_cents = int(round(amount * 100))
    idempotency_key = f"invoice-pay:{sales_invoice_name}:{amount_cents}"

    existing_tx = frappe.db.get_value(
        "Robot Wallet Transaction",
        {"idempotency_key": idempotency_key, "docstatus": 1},
        "name",
    )
    if existing_tx:
        existing_je = _find_settlement_je_for_tx(existing_tx)
        si_after = frappe.db.get_value(
            "Sales Invoice", sales_invoice_name,
            ["outstanding_amount", "status", "currency",
             "grand_total", "docstatus"],
            as_dict=True,
        ) or {}
        new_balance = frappe.db.get_value(
            "Robot Wallet Account", wallet_name, "balance_usd"
        )
        return ok({
            "transaction_id": existing_tx,
            "journal_entry": existing_je,
            "allocated_usd": amount,
            "new_wallet_balance_usd": float(new_balance or 0),
            "invoice": {
                "outstanding_usd": float(si_after.get("outstanding_amount") or 0),
                "payment_status": _derive_si_payment_status(dict(si_after)),
            },
            "idempotent": True,
        })

    # ---------- post-idempotency state checks ----------

    if si.docstatus != 1:
        return err("INVOICE_NOT_PAYABLE", _("Only submitted invoices can be paid."))
    if si.status == "Cancelled":
        return err("INVOICE_NOT_PAYABLE", _("Cancelled invoices cannot be paid."))
    if outstanding_preflight <= 0.005:
        return err("ALREADY_PAID", _("This invoice has no outstanding balance."))
    if amount > outstanding_preflight + 0.005:
        return err(
            "AMOUNT_EXCEEDS_OUTSTANDING",
            _("Requested {0:.2f} exceeds outstanding {1:.2f}.").format(amount, outstanding_preflight),
        )

    # ---------- locked execution: wallet FOR UPDATE + SI re-read ----------

    je_name = None
    tx_name = None
    # The Spend transaction type is normally Desk-restricted (Phase 8B
    # hardening) -- the flag tells the controller this is a trusted backend
    # settlement path. We clear it in the finally block regardless of
    # success/failure so it never leaks into a later request on the same
    # worker process.
    frappe.flags.wallet_settlement_in_progress = True
    try:
        # Lock wallet row for the duration of the transaction.
        wallet_locked = frappe.db.sql(
            """
            SELECT name, status, balance_usd
              FROM `tabRobot Wallet Account`
             WHERE name = %s
             FOR UPDATE
            """,
            (wallet_name,),
            as_dict=True,
        )
        if not wallet_locked:
            frappe.db.rollback()
            return err("SERVER_ERROR", _("Could not load your wallet."))
        locked_wallet = wallet_locked[0]
        if locked_wallet["status"] != "Active":
            frappe.db.rollback()
            return err("WALLET_FROZEN", _("Wallet is not active."))
        locked_balance = float(locked_wallet["balance_usd"] or 0)
        if amount > locked_balance + 0.005:
            frappe.db.rollback()
            return err(
                "INSUFFICIENT_FUNDS",
                _("Wallet balance {0:.2f} is below requested {1:.2f}.").format(
                    locked_balance, amount,
                ),
            )

        # Re-read SI under the same transaction. (We don't FOR UPDATE the
        # Sales Invoice row because ERPNext itself updates it via direct
        # SQL inside the JE submit hook, and adding our own lock would
        # interleave with that work.)
        si_locked = frappe.db.get_value(
            "Sales Invoice", sales_invoice_name,
            ["docstatus", "status", "currency", "outstanding_amount", "debit_to"],
            as_dict=True,
        )
        if not si_locked:
            frappe.db.rollback()
            return err("NOT_FOUND", _("Invoice not found."))
        if si_locked.docstatus != 1 or si_locked.status == "Cancelled":
            frappe.db.rollback()
            return err("INVOICE_NOT_PAYABLE", _("Invoice is not payable anymore."))
        locked_outstanding = float(si_locked.outstanding_amount or 0)
        if locked_outstanding <= 0.005:
            frappe.db.rollback()
            return err("ALREADY_PAID", _("This invoice has no outstanding balance."))
        if amount > locked_outstanding + 0.005:
            frappe.db.rollback()
            return err(
                "AMOUNT_EXCEEDS_OUTSTANDING",
                _("Requested {0:.2f} exceeds outstanding {1:.2f}.").format(
                    amount, locked_outstanding,
                ),
            )

        linked_qr = _find_qr_for_si(sales_invoice_name)

        # Step 1: Robot Wallet Transaction (Spend)
        tx = frappe.get_doc({
            "doctype": "Robot Wallet Transaction",
            "wallet": wallet_name,
            "transaction_type": "Spend",
            "currency": "USD",
            "credit_amount_usd": 0,
            "debit_amount_usd": amount,
            "idempotency_key": idempotency_key,
            "linked_sales_invoice": sales_invoice_name,
            "linked_quote_request": linked_qr,
            "notes": f"Wallet payment for {sales_invoice_name}",
            "posted_at": frappe.utils.now_datetime(),
        })
        tx.insert(ignore_permissions=True)
        tx.submit()
        tx_name = tx.name

        # Step 2: Journal Entry (the GL movement).
        je_name = _create_settlement_je(
            customer=cust_id,
            sales_invoice_name=sales_invoice_name,
            sales_invoice_debit_to=si_locked.debit_to,
            amount=amount,
            wallet_tx_name=tx_name,
        )

        # Step 3: invariant -- cached wallet balance must equal the SUM of
        # all submitted ledger rows for this wallet. The Spend TX on_submit
        # hook already refreshed the cache; this is the defense-in-depth
        # invariant Phase 8B introduced and 8D-1 carried forward.
        ledger_balance = frappe.db.sql(
            """
            SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0)
              FROM `tabRobot Wallet Transaction`
             WHERE wallet     = %s
               AND docstatus  = 1
            """,
            (wallet_name,),
        )[0][0]
        cached_balance = frappe.db.get_value(
            "Robot Wallet Account", wallet_name, "balance_usd"
        )
        if abs(float(cached_balance or 0) - float(ledger_balance or 0)) > 0.005:
            frappe.db.rollback()
            frappe.log_error(
                title="pay_invoice_with_wallet cache drift",
                message=(
                    f"wallet={wallet_name} tx={tx_name} je={je_name} "
                    f"cached={cached_balance} ledger={ledger_balance}"
                ),
            )
            return err(
                "WALLET_CACHE_DRIFT",
                _("Wallet cached balance does not match the ledger sum; payment aborted."),
            )

        # Step 4: QR snapshot.
        _sync_qr_after_wallet_settlement(
            sales_invoice_name=sales_invoice_name,
            journal_entry_name=je_name,
            wallet_transaction_name=tx_name,
        )

        # Step 5: commit the whole transaction.
        frappe.db.commit()
    except frappe.UniqueValidationError as e:
        # A concurrent settlement got the (idempotency_key) slot before us.
        # Recover by returning the existing tx + je (idempotent path).
        frappe.db.rollback()
        recovered_tx = frappe.db.get_value(
            "Robot Wallet Transaction",
            {"idempotency_key": idempotency_key, "docstatus": 1},
            "name",
        )
        if not recovered_tx:
            frappe.log_error(title="pay_invoice_with_wallet race", message=str(e))
            return err("SERVER_ERROR", _("Concurrent payment race; please retry."))
        recovered_je = _find_settlement_je_for_tx(recovered_tx)
        si_after = frappe.db.get_value(
            "Sales Invoice", sales_invoice_name,
            ["outstanding_amount", "status", "grand_total", "docstatus"],
            as_dict=True,
        ) or {}
        new_balance = frappe.db.get_value(
            "Robot Wallet Account", wallet_name, "balance_usd"
        )
        return ok({
            "transaction_id": recovered_tx,
            "journal_entry": recovered_je,
            "allocated_usd": amount,
            "new_wallet_balance_usd": float(new_balance or 0),
            "invoice": {
                "outstanding_usd": float(si_after.get("outstanding_amount") or 0),
                "payment_status": _derive_si_payment_status(dict(si_after)),
            },
            "idempotent": True,
        })
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="pay_invoice_with_wallet", message=str(e))
        return err("SERVER_ERROR", _("Could not complete the wallet payment."))
    finally:
        # Always clear the trust flag so it can't leak into a later request.
        frappe.flags.wallet_settlement_in_progress = False

    # ---------- fresh post-commit reads for the response ----------

    si_after = frappe.db.get_value(
        "Sales Invoice", sales_invoice_name,
        ["outstanding_amount", "status", "grand_total", "docstatus"],
        as_dict=True,
    ) or {}
    new_balance = frappe.db.get_value(
        "Robot Wallet Account", wallet_name, "balance_usd"
    )
    return ok({
        "transaction_id": tx_name,
        "journal_entry": je_name,
        "allocated_usd": amount,
        "new_wallet_balance_usd": float(new_balance or 0),
        "invoice": {
            "outstanding_usd": float(si_after.get("outstanding_amount") or 0),
            "payment_status": _derive_si_payment_status(dict(si_after)),
        },
        "idempotent": False,
    })


def _sync_qr_after_wallet_settlement(
    sales_invoice_name: str,
    journal_entry_name: str,
    wallet_transaction_name: str,
) -> str | None:
    """Push the post-settlement Sales Invoice snapshot onto the linked
    Robot Quote Request.

    Why explicit: ERPNext updates SI.outstanding_amount and SI.status via a
    direct SQL UPDATE inside the JE submit hook, bypassing Frappe's doc_event
    system. Phase 7D's `sync_sales_invoice_back_to_quote_request` is hooked
    on SI.on_update so it does NOT fire here.

    We intentionally do NOT set QR.latest_payment_entry -- that field tracks
    ERPNext Payment Entries only, and a JE is by definition not a PE. The QR
    detail surface for wallet settlements will be the Robot Wallet
    Transaction (Spend) via a separate listing in a future frontend phase.

    Returns the QR name updated, or None if no QR is linked to this SI.
    """
    qr_name = _find_qr_for_si(sales_invoice_name)
    if not qr_name:
        return None
    si = frappe.db.get_value(
        "Sales Invoice", sales_invoice_name,
        [
            "status", "outstanding_amount", "grand_total", "docstatus",
        ],
        as_dict=True,
    )
    if not si:
        return qr_name
    payment_status = _derive_si_payment_status(dict(si))
    frappe.db.set_value(
        "Robot Quote Request",
        qr_name,
        {
            "sales_invoice_status": si.status,
            "sales_invoice_outstanding_amount_usd": float(si.outstanding_amount or 0),
            "payment_status": payment_status,
        },
        update_modified=False,
    )
    return qr_name
