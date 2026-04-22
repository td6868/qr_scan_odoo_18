/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { _t } from "@web/core/l10n/translation";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";
import { x2ManyCommands } from "@web/core/orm_service";

const SUPPORTED_BUTTONS = new Set([
    "action_fill_all_quantities",
    "action_clear_reserved_quantities",
]);

async function ensureEditMode(controller) {
    if (!controller.model.root.isInEdition) {
        await controller.model.root.switchMode("edit");
    }
}

function getEditableMoves(controller) {
    const moveList = controller.model.root.data.move_ids_without_package;
    if (!moveList?.records) {
        return [];
    }
    return moveList.records.filter((record) => !["done", "cancel"].includes(record.data.state));
}

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        if (
            this.props.resModel === "stock.picking" &&
            SUPPORTED_BUTTONS.has(clickParams.name)
        ) {
            return executeButtonCallback(this.ui.activeElement, async () => {
                await ensureEditMode(this);

                const moves = getEditableMoves(this);
                if (!moves.length) {
                    return false;
                }

                const commands = moves.map((moveRecord) =>
                    x2ManyCommands.update(moveRecord.resId, {
                        quantity:
                            clickParams.name === "action_fill_all_quantities"
                                ? (moveRecord.data.product_uom_qty || 0)
                                : 0,
                    })
                );

                await this.model.root.update({
                    move_ids_without_package: commands,
                });

                await this.save({ reload: false });

                this.env.services.notification.add(
                    clickParams.name === "action_fill_all_quantities"
                        ? _t("Đã điền toàn bộ số lượng thực hiện.")
                        : _t("Đã xóa toàn bộ số lượng thực hiện."),
                    { type: "success" }
                );

                return false;
            });
        }

        return super.beforeExecuteActionButton(...arguments);
    },
});