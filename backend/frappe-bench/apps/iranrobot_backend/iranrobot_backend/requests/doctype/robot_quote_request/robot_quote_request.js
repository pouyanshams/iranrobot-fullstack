// Phase 7A + 7C -- Robot Quote Request Desk client-script.
//
// Buttons (mutually exclusive based on document state):
//   Phase 7A:
//     * "Create > Convert to Quotation" when no Quotation is linked yet
//     * "Open Quotation" when erpnext_quotation is set but no Sales Order yet
//   Phase 7C:
//     * "Create > Convert to Sales Order" when customer Accepted AND no SO yet
//     * "Open Sales Order" when erpnext_sales_order is set
//
// Frappe auto-loads <doctype>.js next to the JSON; no hooks.py wiring needed.

async function _confirm(msg) {
  return new Promise((resolve) => {
    frappe.confirm(msg, () => resolve(true), () => resolve(false));
  });
}

async function _call(method, args, freeze_msg) {
  frappe.dom.freeze(freeze_msg);
  try {
    const r = await frappe.call({ method, type: "POST", args });
    frappe.dom.unfreeze();
    return (r && r.message) || {};
  } catch (e) {
    frappe.dom.unfreeze();
    return { ok: false, error: { message: (e && e.message) || __("Could not reach the server.") } };
  }
}

frappe.ui.form.on("Robot Quote Request", {
  refresh(frm) {
    if (frm.is_new()) {
      return;
    }

    const hasQuotation = !!frm.doc.erpnext_quotation;
    const hasSalesOrder = !!frm.doc.erpnext_sales_order;
    const hasSalesInvoice = !!frm.doc.erpnext_sales_invoice;
    const customerAccepted = frm.doc.customer_response === "Accepted";

    // ---- Sales Invoice branch (Phase 7D) ----
    if (hasSalesInvoice) {
      frm.add_custom_button(
        __("Open Sales Invoice"),
        () => frappe.set_route("Form", "Sales Invoice", frm.doc.erpnext_sales_invoice),
      );
    } else if (hasSalesOrder) {
      frm.add_custom_button(
        __("Convert to Sales Invoice"),
        async () => {
          const ok = await _confirm(__(
            "Create a Draft ERPNext Sales Invoice from the linked Sales Order? Staff finishes review and submits in the Sales Invoice form. No Payment Entry is created -- record payments manually in Desk when received.",
          ));
          if (!ok) return;
          const envelope = await _call(
            "iranrobot_backend.api.requests.convert_sales_order_to_sales_invoice",
            { name: frm.doc.name },
            __("Creating Sales Invoice..."),
          );
          if (!envelope.ok) {
            const msg = (envelope.error && envelope.error.message) || __("Conversion failed.");
            frappe.msgprint({ title: __("Could not create Sales Invoice"), message: msg, indicator: "red" });
            return;
          }
          const siId = envelope.data && envelope.data.sales_invoice_id;
          if (!siId) {
            frappe.msgprint({ title: __("Unexpected response"), message: __("Sales Invoice id missing."), indicator: "orange" });
            return;
          }
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Sales Invoice", siId);
          });
        },
        __("Create"),
      );
    }

    // ---- Sales Order branch (Phase 7C) ----
    if (hasSalesOrder) {
      frm.add_custom_button(
        __("Open Sales Order"),
        () => frappe.set_route("Form", "Sales Order", frm.doc.erpnext_sales_order),
      );
    } else if (hasQuotation && customerAccepted) {
      // Customer accepted the Quotation -- staff can now convert to SO.
      frm.add_custom_button(
        __("Convert to Sales Order"),
        async () => {
          const ok = await _confirm(__(
            "Create a Draft ERPNext Sales Order from this accepted Quotation? Staff finishes details and submits in the Sales Order form. No invoice or payment is created.",
          ));
          if (!ok) return;
          const envelope = await _call(
            "iranrobot_backend.api.requests.convert_accepted_quote_to_sales_order",
            { name: frm.doc.name },
            __("Creating Sales Order..."),
          );
          if (!envelope.ok) {
            const msg = (envelope.error && envelope.error.message) || __("Conversion failed.");
            frappe.msgprint({ title: __("Could not create Sales Order"), message: msg, indicator: "red" });
            return;
          }
          const soId = envelope.data && envelope.data.sales_order_id;
          if (!soId) {
            frappe.msgprint({ title: __("Unexpected response"), message: __("Sales Order id missing."), indicator: "orange" });
            return;
          }
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Sales Order", soId);
          });
        },
        __("Create"),
      );
    }

    // ---- Quotation branch (Phase 7A) ----
    // Show "Open Quotation" even when an SO exists, so staff can pivot back
    // to the original proposal for reference. The Convert button only shows
    // when there is no Quotation linked yet.
    if (hasQuotation) {
      frm.add_custom_button(
        __("Open Quotation"),
        () => frappe.set_route("Form", "Quotation", frm.doc.erpnext_quotation),
      );
    } else {
      frm.add_custom_button(
        __("Convert to Quotation"),
        async () => {
          const ok = await _confirm(__(
            "Create a Draft ERPNext Quotation from this Quote Request? Staff finishes pricing and submits in the new Quotation form.",
          ));
          if (!ok) return;
          const envelope = await _call(
            "iranrobot_backend.api.requests.convert_quote_request_to_quotation",
            { name: frm.doc.name },
            __("Creating Quotation..."),
          );
          if (!envelope.ok) {
            const msg = (envelope.error && envelope.error.message) || __("Conversion failed.");
            frappe.msgprint({ title: __("Could not create Quotation"), message: msg, indicator: "red" });
            return;
          }
          const qid = envelope.data && envelope.data.quotation_id;
          if (!qid) {
            frappe.msgprint({ title: __("Unexpected response"), message: __("Quotation id missing."), indicator: "orange" });
            return;
          }
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Quotation", qid);
          });
        },
        __("Create"),
      );
    }
  },
});
