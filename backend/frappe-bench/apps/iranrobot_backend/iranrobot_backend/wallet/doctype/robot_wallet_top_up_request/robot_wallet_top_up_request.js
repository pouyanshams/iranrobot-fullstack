// Phase 8B -- Robot Wallet Top Up Request Desk client-script.
//
// Surfaces "Approve" / "Reject" buttons on a Pending request. The buttons call
// the whitelisted APIs (which run the role check + idempotency logic) and
// reload the form on success. Staff cannot edit linked_transaction,
// approval_idempotency_key, or status directly -- everything flows through
// the API.

frappe.ui.form.on("Robot Wallet Top Up Request", {
  refresh(frm) {
    if (frm.is_new() || !frm.doc.name) return;
    if (frm.doc.status !== "Pending") return;

    frm.add_custom_button(
      __("Approve"),
      () => {
        frappe.prompt(
          [
            {
              fieldname: "bank_reference",
              fieldtype: "Data",
              label: __("Bank Reference (optional)"),
            },
          ],
          (values) => {
            frappe.call({
              method:
                "iranrobot_backend.api.wallet.staff_approve_top_up_request",
              args: { name: frm.doc.name, bank_reference: values.bank_reference || "" },
              callback: (res) => {
                const env = (res && res.message) || {};
                if (env.ok) {
                  frappe.show_alert({
                    message: __("Top-up approved."),
                    indicator: "green",
                  });
                  frm.reload_doc();
                } else {
                  const err = (env.error && env.error.message) || __("Approval failed.");
                  frappe.msgprint({
                    title: __("Approval error"),
                    indicator: "red",
                    message: err,
                  });
                }
              },
            });
          },
          __("Approve top-up request"),
          __("Approve")
        );
      },
      __("Actions")
    );

    frm.add_custom_button(
      __("Reject"),
      () => {
        frappe.prompt(
          [
            {
              fieldname: "reason",
              fieldtype: "Small Text",
              label: __("Rejection Reason"),
              reqd: 1,
            },
          ],
          (values) => {
            frappe.call({
              method:
                "iranrobot_backend.api.wallet.staff_reject_top_up_request",
              args: { name: frm.doc.name, reason: values.reason },
              callback: (res) => {
                const env = (res && res.message) || {};
                if (env.ok) {
                  frappe.show_alert({
                    message: __("Top-up rejected."),
                    indicator: "orange",
                  });
                  frm.reload_doc();
                } else {
                  const err = (env.error && env.error.message) || __("Rejection failed.");
                  frappe.msgprint({
                    title: __("Rejection error"),
                    indicator: "red",
                    message: err,
                  });
                }
              },
            });
          },
          __("Reject top-up request"),
          __("Reject")
        );
      },
      __("Actions")
    );
  },
});
