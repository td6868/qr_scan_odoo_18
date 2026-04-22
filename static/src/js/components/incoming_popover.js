/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class IncomingPopoverContent extends Component {
    static template = "qr_scan_odoo_18.IncomingPopoverContent";
    static props = {
        items: { type: Array },
        close: { type: Function, optional: true },
    };
}

export class IncomingPopoverField extends Component {
    static template = "qr_scan_odoo_18.IncomingPopoverField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: false });
        this.popover = usePopover(IncomingPopoverContent, {
            position: "bottom-start",
            popoverClass: "incoming_odo_popover",
            closeOnClickAway: (target) => !target.closest(".modal"),
        });
    }

    get displayValue() {
        const value = this.props.record?.data?.[this.props.name];
        return value ?? 0;
    }

    async onClick(ev) {
        ev.stopPropagation();

        if (this.popover.isOpen) {
            this.popover.close();
            return;
        }

        const lineId = this.props.record?.resId || this.props.record?.data?.id;
        if (!lineId) {
            return;
        }

        const anchorEl = ev.currentTarget;
        if (!anchorEl) {
            return;
        }

        this.state.loading = true;
        try {
            const data = await this.orm.call("sale.order.line", "get_incoming_details", [[lineId]]);
            if (!anchorEl.isConnected) {
                return;
            }
            const items = (Array.isArray(data) ? data : []).map((item, index) => ({
                ...item,
                _key: `${item?.date || "no-date"}-${item?.origin || "no-origin"}-${index}`,
            }));
            this.popover.open(anchorEl, {
                items,
            });
        } finally {
            this.state.loading = false;
        }
    }
}

export const incomingPopoverField = {
    component: IncomingPopoverField,
    supportedTypes: ["float", "integer"],
};

registry.category("fields").add("incoming_popover", incomingPopoverField);
