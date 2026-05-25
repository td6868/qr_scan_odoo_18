/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class ShippingHistoryPopoverContent extends Component {
    static template = "qr_scan_odoo_18.ShippingHistoryPopoverContent";
    static props = {
        data: { type: Array },
        record: { type: Object, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ applyingId: null });
    }

    async applyHistory(item) {
        if (!this.props.record || !item?.id) {
            return;
        }

        this.state.applyingId = item.id;
        try {
            // Get contact data from server (item.id is now contact_id, not history_id)
            const contactData = await this.orm.call(
                "customer.shipping.history",
                "get_history_for_apply",
                [item.id]  // Pass contact_id
            );

            if (contactData) {
                // Update wizard fields directly on client-side (no server write needed)
                const updates = {};
                if (contactData.park_info) {
                    updates.park_info = contactData.park_info;
                }
                if (contactData.recipient_name) {
                    updates.recipient_name = contactData.recipient_name;
                }
                if (contactData.recipient_phone) {
                    updates.recipient_phone = contactData.recipient_phone;
                }
                if (contactData.recipient_address) {
                    updates.recipient_address = contactData.recipient_address;
                }

                await this.props.record.update(updates);
            }

            this.props.close?.();
            this.notification.add("Đã áp dụng thông tin từ địa chỉ", { type: "success" });
        } catch (error) {
            console.error("Error applying contact:", error);
            this.notification.add("Lỗi khi áp dụng địa chỉ: " + error.message, { type: "danger" });
        } finally {
            this.state.applyingId = null;
        }
    }
}

export class ShippingHistoryPopoverField extends Component {
    static template = "qr_scan_odoo_18.ShippingHistoryPopoverField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: false });
        this.popover = usePopover(ShippingHistoryPopoverContent, {
            position: "bottom-start",
            popoverClass: "shipping_history_popover",
        });
    }

    get historyCount() {
        return this.props.record?.data?.shipping_history_count || 0;
    }

    async onClick(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        if (this.popover.isOpen) {
            this.popover.close();
            return;
        }

        if (this.historyCount === 0) {
            return;
        }

        // Get partner_id from wizard record data (no need for saved record ID)
        const partnerField = this.props.record?.data?.partner_id;
        const partnerId = Array.isArray(partnerField)
            ? partnerField[0]
            : (partnerField?.id || partnerField);

        console.log("Partner ID:", partnerId);

        if (!partnerId || typeof partnerId !== "number") {
            console.error("Invalid partner ID:", partnerId);
            this.notification.add("Không tìm thấy khách hàng.", { type: "warning" });
            return;
        }

        const anchorEl = ev.currentTarget;
        if (!anchorEl) return;

        this.state.loading = true;
        try {
            // Call method on customer.shipping.history directly with partner_id
            const data = await this.orm.call(
                "customer.shipping.history",
                "get_history_by_partner",
                [partnerId]
            );
            console.log("Received data:", data);

            if (!anchorEl.isConnected) return;

            this.popover.open(anchorEl, {
                data: Array.isArray(data) ? data : [],
                record: this.props.record,
            });
        } catch (error) {
            console.error("Error loading shipping history:", error);
            this.notification.add("Lỗi khi tải lịch sử: " + error.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("fields").add("shipping_history_popover", {
    component: ShippingHistoryPopoverField,
    supportedTypes: ["integer"],
});
