"""Phase 8E -- bench wrapper for the wallet reconciliation core.

Reconciles every Robot Wallet Account and (by default) auto-freezes any
wallet whose `max(|cached - ledger|, |ledger - GL|)` exceeds the freeze
threshold. Set ``freeze=False`` for a non-destructive audit pass.

Usage::

    # Real run -- freezes on material drift.
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_reconcile.run

    # Dry-run / audit (does not change wallet.status).
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_reconcile.run \\
        --kwargs "{'freeze': False}"

    # Single wallet only.
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_reconcile.run \\
        --kwargs "{'wallet': 'WA-2026-00001'}"

The command refuses to run on any site other than `iranrobot.localhost`
(dev guardrail).
"""

from __future__ import annotations

import json

import frappe

from iranrobot_backend.wallet import reconciliation


_ALLOWED_SITE = "iranrobot.localhost"


def _guard_site():
    actual = getattr(frappe.local, "site", None)
    if actual != _ALLOWED_SITE:
        frappe.throw(
            f"wallet_reconcile refuses to run on site {actual!r}. "
            f"Only {_ALLOWED_SITE!r} is allowed (dev guardrail).",
            title="Site guard",
        )


def _coerce_bool(value, default=True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("false", "0", "no", "off"):
        return False
    if s in ("true", "1", "yes", "on"):
        return True
    return default


def run(freeze=True, wallet=None):
    """Reconcile wallet(s). Returns the summary counts dict."""
    print("\n=== Phase 8E wallet reconciliation ===\n")
    _guard_site()
    freeze = _coerce_bool(freeze, default=True)

    if wallet:
        if not frappe.db.exists("Robot Wallet Account", wallet):
            frappe.throw(
                f"Robot Wallet Account {wallet!r} does not exist.",
                title="Unknown wallet",
            )
        results = [reconciliation.reconcile_one(wallet, freeze=freeze)]
        try:
            frappe.db.commit()
        except Exception:
            pass
    else:
        results = reconciliation.reconcile_all(freeze=freeze)

    for r in results:
        print("RECONCILE::" + json.dumps(r, default=str))

    total = len(results)
    clean = sum(1 for r in results if r.get("status") == "Clean")
    mismatch = sum(1 for r in results if r.get("status") == "Mismatch")
    frozen = sum(1 for r in results if r.get("status") == "Frozen")
    error = sum(1 for r in results if r.get("status") == "Error")

    print(f"\nDone. freeze={freeze} wallet={wallet or 'ALL'}")
    print(f"  total      = {total}")
    print(f"  clean      = {clean}")
    print(f"  mismatch   = {mismatch}")
    print(f"  frozen     = {frozen}")
    print(f"  error      = {error}")
    return {
        "total": total,
        "clean": clean,
        "mismatch": mismatch,
        "frozen": frozen,
        "error": error,
    }
