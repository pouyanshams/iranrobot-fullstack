"""Phase 8A -- Robot Wallet Account controller.

A 1:1-with-Customer prepaid wallet header. The `balance_usd` and
`available_balance_usd` fields are **cached** -- the source of truth is
SUM(Robot Wallet Transaction.credit_amount_usd - debit_amount_usd) WHERE
docstatus = 1 for this wallet.

Phase 8A does NOT implement spending or top-up flows; this controller only
exposes the recompute helper so the transaction controller (and bench-side
smokes) can refresh the cache after submit/cancel.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class RobotWalletAccount(Document):
    def validate(self):
        # Phase 8A is USD-only. Force currency = "USD" defensively even though
        # the field default + read_only already prevent UI edits.
        if not self.currency:
            self.currency = "USD"
        if self.currency != "USD":
            frappe.throw(
                f"Robot Wallet Account currency must be 'USD' in Phase 8A "
                f"(got {self.currency!r}).",
                title="Unsupported currency",
            )
        if not self.status:
            self.status = "Active"
        # Defensive clamp -- the cached fields must never be negative. The
        # ledger is the source of truth; this guards against accidental UI edits.
        if self.balance_usd is None:
            self.balance_usd = 0
        if self.available_balance_usd is None:
            self.available_balance_usd = 0

    # ------------------------------------------------------------------ #
    # Balance recomputation
    # ------------------------------------------------------------------ #

    def recompute_balance(self) -> float:
        """Refresh `balance_usd`, `available_balance_usd`, and
        `last_transaction_at` from the submitted ledger.

        Returns the freshly-computed balance. Uses `db_set` so the cache is
        written without re-running `validate` or `on_update`. Phase 8A has no
        holds, so `available_balance_usd == balance_usd`.
        """
        row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0) AS balance,
                   MAX(posted_at) AS last_at
              FROM `tabRobot Wallet Transaction`
             WHERE wallet     = %s
               AND docstatus  = 1
            """,
            (self.name,),
            as_dict=True,
        )
        balance = float(row[0]["balance"] or 0) if row else 0.0
        last_at = row[0]["last_at"] if row else None

        self.db_set("balance_usd", balance, update_modified=False)
        self.db_set("available_balance_usd", balance, update_modified=False)
        if last_at is not None:
            self.db_set("last_transaction_at", last_at, update_modified=False)
        return balance
