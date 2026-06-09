"""Phase 8B -- Robot Wallet Top Up Request controller.

A customer-submitted request to credit their wallet. The lifecycle is driven
by `status` (Pending -> Approved | Rejected | Cancelled), NOT by docstatus --
top-up requests are not submittable.

Hard rules enforced here (defense-in-depth around the API guards):
    - `customer`, `user`, `wallet`, `submitted_at` are populated server-side and
      cannot be edited via UI/desk.
    - status transition is one-way out of Pending: Pending -> {Approved,
      Rejected, Cancelled}. Approved/Rejected/Cancelled rows are immutable.
    - A customer can NEVER set their own row to status="Approved" or
      status="Rejected", even via Desk if a Web Role somehow got share/read.
    - Amount must be a positive USD value.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


_TERMINAL_STATUSES = {"Approved", "Rejected", "Cancelled"}


class RobotWalletTopUpRequest(Document):
    # ------------------------------------------------------------------ validate
    def validate(self):
        self._validate_currency()
        self._validate_amount()
        self._validate_method()
        self._validate_required_snapshots()
        self._validate_status_transition()
        self._block_customer_self_approval_or_rejection()
        self._block_linked_payment_entry()

    # ============================================================== internals

    def _validate_currency(self):
        if not self.currency:
            self.currency = "USD"
        if self.currency != "USD":
            frappe.throw(
                _("Phase 8B wallet top-up is USD-only (got {0}).").format(self.currency),
                title=_("Unsupported currency"),
            )

    def _validate_amount(self):
        try:
            amt = float(self.amount_usd or 0)
        except (TypeError, ValueError):
            frappe.throw(_("amount_usd must be a number."))
            return
        if amt <= 0:
            frappe.throw(_("amount_usd must be positive."))

    def _validate_method(self):
        if self.method not in ("Bank Transfer", "Cash Deposit"):
            frappe.throw(
                _("Invalid method {0}. Allowed: Bank Transfer, Cash Deposit.").format(self.method),
            )

    def _validate_required_snapshots(self):
        # These five fields MUST be set by the create API before validate runs.
        # We don't auto-fill from session here because the controller is also
        # used by the patch / desk forms and we want loud failures, not silent
        # impersonation.
        for f in ("customer", "user", "wallet", "submitted_at", "status"):
            if not self.get(f):
                frappe.throw(
                    _("Field {0} is required.").format(f),
                    title=_("Missing server-side snapshot"),
                )

    def _validate_status_transition(self):
        if self.is_new():
            # New record can only be created in Pending state.
            if self.status != "Pending":
                frappe.throw(
                    _("New top-up requests must start in Pending state."),
                    title=_("Invalid initial status"),
                )
            return
        # Existing record -- compare with the DB value (avoids re-using the
        # controller's in-memory object during a transition).
        old_status = frappe.db.get_value(
            "Robot Wallet Top Up Request", self.name, "status"
        )
        if old_status == self.status:
            return
        if old_status in _TERMINAL_STATUSES:
            frappe.throw(
                _("Top-up requests in status {0} are immutable.").format(old_status),
                title=_("Terminal status"),
            )
        # Pending -> any terminal status is OK; this controller is permissive
        # because the *API* is what gates which staff/customer can do what.

    def _block_customer_self_approval_or_rejection(self):
        # Belt-and-braces: even if a customer somehow gets through to a
        # save() with status set to Approved or Rejected, we slam the door.
        if self.status in ("Approved", "Rejected"):
            actor = frappe.session.user
            if actor and self.user and actor == self.user:
                frappe.throw(
                    _("A customer cannot approve or reject their own top-up request."),
                    title=_("Self-approval blocked"),
                )

    def _block_linked_payment_entry(self):
        """Trust boundary for `linked_payment_entry` writes.

        The field stores the ERPNext Payment Entry that mirrors an approved
        top-up into GL. Only trusted backend accounting code
        (`api/wallet.py:staff_approve_top_up_request` +
        `commands/wallet_accounting_backfill`) may write it. Those code paths
        use `frappe.db.set_value(...)`, which bypasses `validate()` by
        design, so this guard never sees their writes.

        The guard fires only on save()/insert() paths -- Desk form edits,
        bench scripts that load + save the doc, or any future controller
        that calls .save(). On any of those, a non-empty value here is
        rejected loudly: callers must not stage a value into
        linked_payment_entry through controller-level save() machinery.

        Phase 8C originally introduced this as a temporary lock until the
        accounting model was proven (8D-0 spike). It now serves as a
        permanent fence -- trusted code goes through `db.set_value`,
        everything else is blocked.
        """
        new_val = (self.linked_payment_entry or "") or None
        if new_val is None:
            return
        if self.is_new():
            frappe.throw(
                _(
                    "linked_payment_entry is reserved for the future "
                    "accounting-hardening phase and must be empty on new rows."
                ),
                title=_("Field reserved"),
            )
        old_val = frappe.db.get_value(
            "Robot Wallet Top Up Request", self.name, "linked_payment_entry"
        ) or None
        if old_val != new_val:
            frappe.throw(
                _(
                    "linked_payment_entry is reserved for the future "
                    "accounting-hardening phase. Editing it manually is blocked."
                ),
                title=_("Field reserved"),
            )
