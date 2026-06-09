"""Phase 8B patch -- convert Robot Wallet Transaction.linked_top_up_request from
Data to Link -> Robot Wallet Top Up Request.

In Phase 8A the field was a `Data` column because the target DocType did not
exist yet. In Phase 8B we ship `Robot Wallet Top Up Request`, so we can safely
upgrade the column.

`frappe.reload_doc` re-syncs the DocType JSON into the database schema. The
column type stays VARCHAR/Data-ish under the hood for Link fields, so no DDL
migration is required. Any pre-8B rows have `linked_top_up_request=NULL` (no
top-up flow existed yet), so there is nothing to backfill.
"""

import frappe


def execute():
    frappe.reload_doc("wallet", "doctype", "robot_wallet_top_up_request")
    frappe.reload_doc("wallet", "doctype", "robot_wallet_transaction")
