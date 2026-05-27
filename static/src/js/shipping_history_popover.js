/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class ShippingHistoryPopoverContent extends Component {
    static template = "qr_scan_odoo_18.ShippingHistoryPopoverContent";
    static props = {
        historyData: { type: Array, optional: true },
        addressData: { type: Array, optional: true },
        record: { type: Object, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ applyingId: null, activeTab: "history" });
        this.tabs = [
            { key: "history", label: "Lịch sử đã dùng" },
            { key: "addresses", label: "Địa chỉ khả dụng" },
        ];
    }

    setTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    get currentItems() {
        return this.state.activeTab === "addresses"
            ? (this.props.addressData || [])
            : (this.props.historyData || []);
    }

    get emptyMessage() {
        return this.state.activeTab === "addresses"
            ? "Chưa có địa chỉ giao khả dụng"
            : "Chưa có địa chỉ giao hàng đã dùng";
    }

    async applyHistory(item) {
        if (!this.props.record || !item?.id) {
            return;
        }

        this.state.applyingId = item.id;
        try {
            // Get contact data from server (item.id is contact_id)
            const contactData = await this.orm.call(
                "customer.shipping.history",
                "get_history_for_apply",
                [item.id]
            );

            if (contactData) {
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
            this.notification.add("Đã áp dụng địa chỉ giao hàng", { type: "success" });
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

        const partnerField = this.props.record?.data?.partner_id;
        const partnerId = Array.isArray(partnerField)
            ? partnerField[0]
            : (partnerField?.id || partnerField);

        if (!partnerId || typeof partnerId !== "number") {
            this.notification.add("Không tìm thấy khách hàng.", { type: "warning" });
            return;
        }

        const anchorEl = ev.currentTarget;
        if (!anchorEl) return;

        this.state.loading = true;
        try {
            const [historyData, addressData] = await Promise.all([
                this.orm.call("customer.shipping.history", "get_history_by_partner", [partnerId]),
                this.orm.call("customer.shipping.history", "get_available_delivery_addresses", [partnerId]),
            ]);

            if (!anchorEl.isConnected) return;

            this.popover.open(anchorEl, {
                historyData: Array.isArray(historyData) ? historyData : [],
                addressData: Array.isArray(addressData) ? addressData : [],
                record: this.props.record,
            });
        } catch (error) {
            console.error("Error loading shipping data:", error);
            this.notification.add("Lỗi khi tải địa chỉ giao hàng: " + error.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("fields").add("shipping_history_popover", {
    component: ShippingHistoryPopoverField,
    supportedTypes: ["integer"],
});
