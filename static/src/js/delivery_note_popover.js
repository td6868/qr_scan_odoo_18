/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class DeliveryNotePopoverContent extends Component {
    static template = "qr_scan_odoo_18.DeliveryNotePopoverContent";
    static props = {
        note: { type: String, optional: true },
        pickingName: { type: String, optional: true },
        close: { type: Function, optional: true },
    };

    get noteLines() {
        const note = (this.props.note || "").trim();
        return note ? note.split(/\r?\n/) : [];
    }
}

export class DeliveryNotePopoverField extends Component {
    static template = "qr_scan_odoo_18.DeliveryNotePopoverField";
    static props = { ...standardFieldProps };

    setup() {
        this.popover = usePopover(DeliveryNotePopoverContent, {
            position: "bottom-start",
            popoverClass: "delivery_note_popover",
        });
    }

    get note() {
        return this.props.record?.data?.delivery_note || "";
    }

    get hasNote() {
        return Boolean(this.note.trim());
    }

    get pickingName() {
        return this.props.record?.data?.name || "";
    }

    onClick(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        if (this.popover.isOpen) {
            this.popover.close();
            return;
        }

        const anchorEl = ev.currentTarget;
        if (!anchorEl) {
            return;
        }

        this.popover.open(anchorEl, {
            note: this.note,
            pickingName: this.pickingName,
        });
    }
}

registry.category("fields").add("delivery_note_popover", {
    component: DeliveryNotePopoverField,
    supportedTypes: ["text", "char"],
});
