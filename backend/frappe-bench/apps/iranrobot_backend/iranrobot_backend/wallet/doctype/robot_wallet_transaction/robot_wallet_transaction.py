"""Phase 8A -- Robot Wallet Transaction controller.

Append-only ledger row. Submitted (docstatus=1) rows are immutable; cancellation
follows the counter-transaction pattern (set in Phase 8G), never deletion.

Hard rules enforced here:
    - exactly one of (credit_amount_usd, debit_amount_usd) is non-zero
    - the chosen amount sign matches transaction_type's direction
    - `direction` is derived, not user-set
    - `customer` is denormalised from `wallet.customer`
    - `idempotency_key` is required on submit
    - `posted_by` / `posted_ip` are snapshotted at save time
    - `Adjustment-*` types require a `reason`

After submit / cancel, the cached balance on the parent Robot Wallet Account is
refreshed by calling `account.recompute_balance()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


_CREDIT_TYPES = {"Top Up", "Refund", "Adjustment-Credit"}
_DEBIT_TYPES = {"Spend", "Adjustment-Debit"}
_ADJUSTMENT_TYPES = {"Adjustment-Credit", "Adjustment-Debit"}


class RobotWalletTransaction(Document):
    # -------------------------------------------------------------- validate
    def validate(self):
        self._derive_direction()
        self._snapshot_customer()
        self._validate_amount()
        self._validate_currency()
        self._validate_adjustment_reason()
        self._snapshot_posted_metadata()
        if not self.posted_at:
            self.posted_at = frappe.utils.now_datetime()

    # ----------------------------------------------------------- before_submit
    def before_submit(self):
        if not self.idempotency_key:
            frappe.throw(
                _("Robot Wallet Transaction requires an idempotency_key before submit."),
                title=_("Missing idempotency_key"),
            )
        self._restrict_manual_spend_refund()

    def _restrict_manual_spend_refund(self):
        """Phase 8B hardening + 8D-2 escape: manual submission of Spend/Refund
        via Desk requires System Manager, but trusted backend code paths
        (Phase 8D-2 `pay_invoice_with_wallet`, future 8G refund API) bypass
        the role check by setting `frappe.flags.wallet_settlement_in_progress`
        before submit.

        The flag is intentionally module-local rather than persistent: it is
        only valid for the lifetime of the current request, and any code that
        sets it is responsible for clearing it in a finally block.

        Bench seeders (`_phase8a_smoke`, `_phase8d2_smoke`) run as
        Administrator, so they're also exempt.
        """
        if self.transaction_type not in {"Spend", "Refund"}:
            return
        if getattr(frappe.flags, "wallet_settlement_in_progress", False):
            return
        actor = frappe.session.user
        if actor == "Administrator":
            return
        roles = set(frappe.get_roles(actor))
        if "System Manager" not in roles:
            frappe.throw(
                _(
                    "Manual {0} transactions require the System Manager role. "
                    "Customer-facing spending uses the wallet settlement API "
                    "(Phase 8D-2); refund flows arrive in Phase 8G."
                ).format(self.transaction_type),
                title=_("Restricted transaction type"),
            )

    # --------------------------------------------------------------- on_submit
    def on_submit(self):
        # Refresh the parent wallet's cached balance + last_transaction_at.
        # The recompute reads SUM over docstatus=1 rows, which now includes us.
        self._refresh_parent_cache()
        # Snapshot balance_after_usd on this row for audit. Read the freshly
        # written cache off the parent.
        new_balance = frappe.db.get_value(
            "Robot Wallet Account", self.wallet, "balance_usd"
        )
        if new_balance is not None:
            self.db_set("balance_after_usd", float(new_balance), update_modified=False)

    # --------------------------------------------------------------- on_cancel
    def on_cancel(self):
        # Cancellation = docstatus 1 -> 2. The recompute SUM excludes us
        # automatically, which is the correct effect.
        self._refresh_parent_cache()

    # ============================================================== internals

    def _derive_direction(self):
        tt = self.transaction_type
        if tt in _CREDIT_TYPES:
            self.direction = "Credit"
        elif tt in _DEBIT_TYPES:
            self.direction = "Debit"
        else:
            frappe.throw(
                _("Unknown transaction_type {0}.").format(tt),
                title=_("Invalid transaction_type"),
            )

    def _snapshot_customer(self):
        if not self.wallet:
            frappe.throw(_("wallet is required."))
        cust = frappe.db.get_value("Robot Wallet Account", self.wallet, "customer")
        if not cust:
            frappe.throw(
                _("Wallet {0} has no linked Customer.").format(self.wallet),
                title=_("Orphan wallet"),
            )
        self.customer = cust

    def _validate_amount(self):
        credit = float(self.credit_amount_usd or 0)
        debit = float(self.debit_amount_usd or 0)
        if credit < 0 or debit < 0:
            frappe.throw(_("Amounts must be non-negative."))
        if credit > 0 and debit > 0:
            frappe.throw(_("Only one of credit / debit may be non-zero."))
        if credit == 0 and debit == 0:
            frappe.throw(_("Amount must be non-zero."))
        # Direction-amount agreement.
        if self.direction == "Credit" and credit == 0:
            frappe.throw(_("Credit transactions must set credit_amount_usd."))
        if self.direction == "Debit" and debit == 0:
            frappe.throw(_("Debit transactions must set debit_amount_usd."))

    def _validate_currency(self):
        if not self.currency:
            self.currency = "USD"
        if self.currency != "USD":
            frappe.throw(
                _("Phase 8A wallet ledger is USD-only (got {0}).").format(self.currency),
                title=_("Unsupported currency"),
            )

    def _validate_adjustment_reason(self):
        if self.transaction_type in _ADJUSTMENT_TYPES and not (self.reason or "").strip():
            frappe.throw(
                _("Adjustment transactions require a reason."),
                title=_("Missing reason"),
            )

    def _snapshot_posted_metadata(self):
        if not self.posted_by:
            self.posted_by = frappe.session.user
        if not self.posted_ip:
            self.posted_ip = (
                getattr(frappe.local, "request_ip", None)
                or getattr(getattr(frappe.local, "request", None), "remote_addr", None)
                or ""
            )

    def _refresh_parent_cache(self):
        try:
            account = frappe.get_doc("Robot Wallet Account", self.wallet)
            account.recompute_balance()
        except Exception as e:
            # Don't break the submit/cancel transaction over a cache refresh
            # error; log it for accountant follow-up.
            frappe.log_error(
                title="RobotWalletTransaction._refresh_parent_cache",
                message=f"wallet={self.wallet} tx={self.name} err={e}",
            )
