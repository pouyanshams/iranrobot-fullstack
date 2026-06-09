"""Phase 8D-0 -- Wallet accounting bootstrap.

Creates the minimal ERPNext accounting objects required to record wallet
top-up and wallet-funded invoice settlement Payment Entries:

  1. Account: "Customer Wallet Liability - IR"
        parent_account   = "Current Liabilities - IR"
        root_type        = "Liability"
        account_type     = "Receivable"   (so it's a valid Customer party account)
        account_currency = "USD"
        is_group         = 0

  2. Mode of Payment: "Wallet"
        type     = "General"
        accounts = [{company: "IranRobot",
                     default_account: "Customer Wallet Liability - IR"}]

Behaviour:
  - **Idempotent**: rerunning is safe; existing compatible records are
    reported, not modified.
  - **Local-only**: refuses to run unless the site is `iranrobot.localhost`.
    This is a dev-only guardrail to prevent accidental production CoA edits.
  - **Loud on incompatibility**: if an Account or Mode of Payment already
    exists with settings that differ from the desired ones, the bootstrap
    throws rather than silently overwriting.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_accounting_bootstrap.run

The proposed `root_type=Liability + account_type=Receivable` combination is
unusual but is the canonical way to track customer advances in ERPNext while
still allowing the account to be a valid Customer party account on a
Payment Entry. The companion spike
(`_phase8d_accounting_spike`) empirically validates that combination before
any customer-facing Pay-with-Wallet endpoint is built.
"""

from __future__ import annotations

import frappe


# -------------------------------------------------------------------- constants

COMPANY = "IranRobot"

WALLET_LIABILITY_ACCOUNT = "Customer Wallet Liability - IR"
WALLET_LIABILITY_PARENT = "Current Liabilities - IR"
WALLET_LIABILITY_ROOT_TYPE = "Liability"
WALLET_LIABILITY_ACCOUNT_TYPE = "Receivable"
WALLET_LIABILITY_CURRENCY = "USD"

WALLET_MOP = "Wallet"
WALLET_MOP_TYPE = "General"

_ALLOWED_SITE = "iranrobot.localhost"


# -------------------------------------------------------------------- helpers

def _step(label, msg):
    print(f"  [{label}] {msg}")


def _current_site():
    try:
        return frappe.local.site
    except (AttributeError, RuntimeError):
        return None


def _guard_site():
    actual = _current_site()
    if actual != _ALLOWED_SITE:
        frappe.throw(
            f"wallet_accounting_bootstrap refuses to run on site {actual!r}. "
            f"Only {_ALLOWED_SITE!r} is allowed (dev guardrail).",
            title="Site guard",
        )


# -------------------------------------------------------------------- Account

def _check_or_create_account() -> dict:
    if frappe.db.exists("Account", WALLET_LIABILITY_ACCOUNT):
        existing = frappe.db.get_value(
            "Account",
            WALLET_LIABILITY_ACCOUNT,
            [
                "root_type",
                "account_type",
                "account_currency",
                "parent_account",
                "is_group",
            ],
            as_dict=True,
        ) or {}
        problems = []
        if existing.get("root_type") != WALLET_LIABILITY_ROOT_TYPE:
            problems.append(
                f"root_type={existing.get('root_type')!r} "
                f"(want {WALLET_LIABILITY_ROOT_TYPE!r})"
            )
        if existing.get("account_type") != WALLET_LIABILITY_ACCOUNT_TYPE:
            problems.append(
                f"account_type={existing.get('account_type')!r} "
                f"(want {WALLET_LIABILITY_ACCOUNT_TYPE!r})"
            )
        if existing.get("account_currency") != WALLET_LIABILITY_CURRENCY:
            problems.append(
                f"account_currency={existing.get('account_currency')!r} "
                f"(want {WALLET_LIABILITY_CURRENCY!r})"
            )
        if existing.get("parent_account") != WALLET_LIABILITY_PARENT:
            problems.append(
                f"parent_account={existing.get('parent_account')!r} "
                f"(want {WALLET_LIABILITY_PARENT!r})"
            )
        if int(existing.get("is_group") or 0) != 0:
            problems.append("is_group=1 (want 0)")
        if problems:
            frappe.throw(
                f"Account {WALLET_LIABILITY_ACCOUNT!r} exists with incompatible "
                f"settings:\n  - " + "\n  - ".join(problems)
                + "\n\nRefusing to overwrite. Review manually before continuing.",
                title="Incompatible existing Account",
            )
        _step(
            "ACCOUNT",
            f"exists with compatible settings: {dict(existing)}",
        )
        return {"status": "exists", "name": WALLET_LIABILITY_ACCOUNT, **dict(existing)}

    if not frappe.db.exists("Account", WALLET_LIABILITY_PARENT):
        frappe.throw(
            f"Parent account {WALLET_LIABILITY_PARENT!r} does not exist. "
            "The wallet bootstrap requires the standard ERPNext Chart of "
            "Accounts to be initialised first.",
            title="Missing parent account",
        )

    short_name = WALLET_LIABILITY_ACCOUNT.split(" - ")[0]
    acc = frappe.get_doc({
        "doctype": "Account",
        "account_name": short_name,
        "company": COMPANY,
        "parent_account": WALLET_LIABILITY_PARENT,
        "root_type": WALLET_LIABILITY_ROOT_TYPE,
        "account_type": WALLET_LIABILITY_ACCOUNT_TYPE,
        "account_currency": WALLET_LIABILITY_CURRENCY,
        "is_group": 0,
    })
    try:
        acc.insert(ignore_permissions=True)
    except Exception as e:
        frappe.throw(
            f"Account creation failed: {type(e).__name__}: {e}",
            title="Account.insert raised",
        )
    _step(
        "ACCOUNT",
        f"created {acc.name} "
        f"(root_type={acc.root_type}, account_type={acc.account_type}, "
        f"currency={acc.account_currency}, parent={acc.parent_account})",
    )
    return {
        "status": "created",
        "name": acc.name,
        "root_type": acc.root_type,
        "account_type": acc.account_type,
        "account_currency": acc.account_currency,
        "parent_account": acc.parent_account,
    }


# -------------------------------------------------------------------- Mode of Payment

def _check_or_create_mop() -> dict:
    if frappe.db.exists("Mode of Payment", WALLET_MOP):
        mop = frappe.get_doc("Mode of Payment", WALLET_MOP)
        problems = []
        if mop.type != WALLET_MOP_TYPE:
            problems.append(f"type={mop.type!r} (want {WALLET_MOP_TYPE!r})")
        company_rows = [r for r in (mop.accounts or []) if r.company == COMPANY]
        if not company_rows:
            problems.append(f"no accounts row for company {COMPANY!r}")
        else:
            row = company_rows[0]
            if row.default_account != WALLET_LIABILITY_ACCOUNT:
                problems.append(
                    f"company {COMPANY!r} default_account="
                    f"{row.default_account!r} "
                    f"(want {WALLET_LIABILITY_ACCOUNT!r})"
                )
        if problems:
            frappe.throw(
                f"Mode of Payment {WALLET_MOP!r} exists with incompatible "
                f"settings:\n  - " + "\n  - ".join(problems)
                + "\n\nRefusing to overwrite. Review manually before continuing.",
                title="Incompatible existing Mode of Payment",
            )
        _step(
            "MOP",
            f"exists with compatible settings "
            f"(type={mop.type}, default_account={WALLET_LIABILITY_ACCOUNT})",
        )
        return {
            "status": "exists",
            "name": WALLET_MOP,
            "type": mop.type,
            "default_account": WALLET_LIABILITY_ACCOUNT,
        }

    mop = frappe.get_doc({
        "doctype": "Mode of Payment",
        "mode_of_payment": WALLET_MOP,
        "type": WALLET_MOP_TYPE,
        "enabled": 1,
        "accounts": [{
            "company": COMPANY,
            "default_account": WALLET_LIABILITY_ACCOUNT,
        }],
    })
    mop.insert(ignore_permissions=True)
    _step(
        "MOP",
        f"created Mode of Payment {WALLET_MOP!r} "
        f"(type={WALLET_MOP_TYPE}, default_account={WALLET_LIABILITY_ACCOUNT})",
    )
    return {
        "status": "created",
        "name": mop.name,
        "type": WALLET_MOP_TYPE,
        "default_account": WALLET_LIABILITY_ACCOUNT,
    }


# -------------------------------------------------------------------- runner

def run() -> dict:
    print("\n=== Phase 8D-0 wallet accounting bootstrap ===\n")
    _guard_site()
    acc_result = _check_or_create_account()
    mop_result = _check_or_create_mop()
    # Note: Company.default_advance_received_account is intentionally NOT set
    # here. The PEs we create explicitly reference the Wallet Liability account
    # by name; changing the company default could shift the behaviour of other,
    # unrelated staff-initiated Customer Advance flows.
    frappe.db.commit()
    print("\n=== bootstrap complete ===")
    return {"account": acc_result, "mode_of_payment": mop_result}
