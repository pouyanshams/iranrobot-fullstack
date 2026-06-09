"""Phase 8E -- wallet reconciliation core.

For every Robot Wallet Account, compares three balances that should always
agree within tolerance:

  1. cached  -- Robot Wallet Account.balance_usd (the header cache).
  2. ledger  -- SUM(Robot Wallet Transaction credits - debits)
                WHERE wallet=<name> AND docstatus=1.
  3. gl      -- SUM(GL Entry credit - debit) over Customer Wallet Liability
                partywise by Customer party.

The invariant we want is::

    max(|cached - ledger|, |ledger - gl|)  <=  _RECONCILE_TOLERANCE_USD

Behaviour matrix
----------------

    max_delta <= tolerance                  -> Clean    (no action)
    tolerance <  max_delta <  freeze_threshold -> Mismatch (log only)
    max_delta >= freeze_threshold              -> Frozen   (log + freeze)

A corrupted cached balance ALSO triggers a freeze when the cached-vs-ledger
delta exceeds the threshold, even if the ledger and the GL agree (this is
the Phase 8E correction over the original §3 plan).

Cancelled / amended documents are excluded automatically: the ledger query
filters `docstatus=1`, the GL query filters `is_cancelled=0`.

Each mismatch above tolerance writes one Error Log entry titled
``Wallet reconciliation mismatch [Mismatch]`` or ``[Frozen]`` with a JSON
body containing every relevant field. The reconciliation result (status +
delta + checked_at) is snapshotted to the wallet header for accountant
visibility on the Desk form.
"""

from __future__ import annotations

import json

import frappe


# ---------- constants -----------------------------------------------------

COMPANY = "IranRobot"
WALLET_LIABILITY_ACCOUNT = "Customer Wallet Liability - IR"

_RECONCILE_TOLERANCE_USD = 0.01
_RECONCILE_FREEZE_THRESHOLD_USD = 1.00

_STATUS_CLEAN = "Clean"
_STATUS_MISMATCH = "Mismatch"
_STATUS_FROZEN = "Frozen"
_STATUS_ERROR = "Error"


# ---------- balance computations ------------------------------------------


def _cached_balance(wallet_name: str) -> float:
    val = frappe.db.get_value(
        "Robot Wallet Account", wallet_name, "balance_usd"
    )
    return float(val or 0)


def _ledger_balance(wallet_name: str) -> float:
    """SUM(credit - debit) over submitted Robot Wallet Transaction rows."""
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0)
          FROM `tabRobot Wallet Transaction`
         WHERE wallet     = %s
           AND docstatus  = 1
        """,
        (wallet_name,),
    )
    return float(rows[0][0] or 0) if rows else 0.0


def _gl_balance(customer: str) -> float:
    """SUM(credit - debit) over partywise GL entries for this Customer on the
    Customer Wallet Liability - IR account.

    Liability convention: a credit balance means the company owes the
    customer (i.e., the customer's wallet has unspent credit). That matches
    the sign of cached_balance / ledger_balance, so all three numbers are
    directly comparable without sign flips.
    """
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credit - debit), 0)
          FROM `tabGL Entry`
         WHERE account       = %s
           AND party_type    = 'Customer'
           AND party         = %s
           AND company       = %s
           AND is_cancelled  = 0
        """,
        (WALLET_LIABILITY_ACCOUNT, customer, COMPANY),
    )
    return float(rows[0][0] or 0) if rows else 0.0


# ---------- per-wallet ----------------------------------------------------


def _classify(max_delta: float) -> str:
    if max_delta <= _RECONCILE_TOLERANCE_USD:
        return _STATUS_CLEAN
    if max_delta < _RECONCILE_FREEZE_THRESHOLD_USD:
        return _STATUS_MISMATCH
    return _STATUS_FROZEN


def _log_mismatch(payload: dict, level: str) -> None:
    """Write a single Error Log entry titled with the level."""
    try:
        frappe.log_error(
            title=f"Wallet reconciliation mismatch [{level}]",
            message=json.dumps(payload, default=str, indent=2),
        )
    except Exception:
        # Never let logging mask the actual mismatch.
        pass


def _snapshot_account(wallet_name: str, status: str, delta: float) -> None:
    """Update the audit fields on the wallet header. Uses db.set_value so the
    controller's validate() doesn't fire."""
    frappe.db.set_value(
        "Robot Wallet Account",
        wallet_name,
        {
            "last_reconciliation_status": status,
            "last_reconciliation_at": frappe.utils.now_datetime(),
            "last_reconciliation_delta_usd": float(delta),
        },
        update_modified=False,
    )


def _freeze(wallet_name: str) -> None:
    frappe.db.set_value(
        "Robot Wallet Account", wallet_name, "status", "Frozen",
        update_modified=False,
    )


def reconcile_one(wallet_name: str, *, freeze: bool = True) -> dict:
    """Reconcile a single wallet. Returns a result dict; never raises.

    Set `freeze=False` for a dry-run / audit pass -- the function still
    classifies the wallet, writes Error Log entries, and snapshots the audit
    fields, but does NOT flip `Robot Wallet Account.status` to Frozen.
    """
    customer = frappe.db.get_value("Robot Wallet Account", wallet_name, "customer")
    if not customer:
        result = {
            "wallet": wallet_name,
            "customer": None,
            "status": _STATUS_ERROR,
            "error": "wallet has no linked customer",
            "checked_at": frappe.utils.now_datetime(),
        }
        try:
            _snapshot_account(wallet_name, _STATUS_ERROR, 0.0)
        except Exception:
            pass
        _log_mismatch(result, _STATUS_ERROR)
        return result

    try:
        cached = _cached_balance(wallet_name)
        ledger = _ledger_balance(wallet_name)
        gl = _gl_balance(customer)
    except Exception as e:
        result = {
            "wallet": wallet_name,
            "customer": customer,
            "status": _STATUS_ERROR,
            "error": f"{type(e).__name__}: {e}",
            "checked_at": frappe.utils.now_datetime(),
        }
        try:
            _snapshot_account(wallet_name, _STATUS_ERROR, 0.0)
        except Exception:
            pass
        _log_mismatch(result, _STATUS_ERROR)
        return result

    delta_cached_ledger = abs(cached - ledger)
    delta_ledger_gl = abs(ledger - gl)
    max_delta = max(delta_cached_ledger, delta_ledger_gl)
    status = _classify(max_delta)

    action_taken = "none"
    if status == _STATUS_MISMATCH:
        action_taken = "logged"
    elif status == _STATUS_FROZEN:
        action_taken = "frozen" if freeze else "would_freeze"

    payload = {
        "wallet": wallet_name,
        "customer": customer,
        "cached_balance": cached,
        "ledger_balance": ledger,
        "gl_balance": gl,
        "delta_cached_ledger": delta_cached_ledger,
        "delta_ledger_gl": delta_ledger_gl,
        "max_delta": max_delta,
        "tolerance": _RECONCILE_TOLERANCE_USD,
        "freeze_threshold": _RECONCILE_FREEZE_THRESHOLD_USD,
        "status": status,
        "action_taken": action_taken,
        "checked_at": frappe.utils.now_datetime(),
    }

    # Snapshot the audit fields BEFORE we may flip status, so the Desk form
    # always carries the freshest reconciliation metadata even on a freeze.
    try:
        _snapshot_account(wallet_name, status, max_delta)
    except Exception:
        # Snapshot failure is non-fatal; we still classify + log.
        pass

    if status == _STATUS_FROZEN and freeze:
        try:
            _freeze(wallet_name)
        except Exception as e:
            payload["freeze_error"] = f"{type(e).__name__}: {e}"

    if status in (_STATUS_MISMATCH, _STATUS_FROZEN):
        _log_mismatch(payload, status)

    return payload


def reconcile_all(freeze: bool = True) -> list[dict]:
    """Reconcile every Robot Wallet Account. Returns a list of result dicts.
    Catches per-wallet exceptions so one bad wallet doesn't kill the scan.
    """
    results: list[dict] = []
    names = frappe.get_all("Robot Wallet Account", pluck="name")
    for name in names:
        try:
            results.append(reconcile_one(name, freeze=freeze))
        except Exception as e:
            results.append({
                "wallet": name,
                "status": _STATUS_ERROR,
                "error": f"{type(e).__name__}: {e}",
                "checked_at": frappe.utils.now_datetime(),
            })
    try:
        frappe.db.commit()
    except Exception:
        pass
    return results


def reconcile_all_daily() -> None:
    """Frappe scheduler entry point. Called once a day via hooks.py.

    We never raise from here -- the scheduler logs unhandled errors loudly
    and we want to keep wallet UX uninterrupted by a transient DB blip.
    """
    try:
        results = reconcile_all(freeze=True)
        clean = sum(1 for r in results if r.get("status") == _STATUS_CLEAN)
        mismatch = sum(1 for r in results if r.get("status") == _STATUS_MISMATCH)
        frozen = sum(1 for r in results if r.get("status") == _STATUS_FROZEN)
        error = sum(1 for r in results if r.get("status") == _STATUS_ERROR)
        frappe.logger().info(
            f"reconcile_all_daily: total={len(results)} clean={clean} "
            f"mismatch={mismatch} frozen={frozen} error={error}"
        )
    except Exception as e:
        # Last-resort guard so the scheduler isn't poisoned.
        try:
            frappe.log_error(
                title="reconcile_all_daily crashed",
                message=f"{type(e).__name__}: {e}",
            )
        except Exception:
            pass
