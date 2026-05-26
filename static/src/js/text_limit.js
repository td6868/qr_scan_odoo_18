/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { TextField } from "@web/views/fields/text/text_field";
import { onMounted, onPatched } from "@odoo/owl";

const PARK_INFO_MAX_LENGTH = 200; // Bạn đổi lại 200 khi test xong

patch(TextField.prototype, {
    setup() {
        super.setup();

        const applyTextLimit = () => {
            if (this.props.name !== "park_info") return;

            const textarea = this.textareaRef?.el;
            if (textarea && !textarea.__parkInfoLimitApplied) {
                textarea.maxLength = PARK_INFO_MAX_LENGTH;
                textarea.addEventListener("input", () => {
                    if (textarea.value.length > PARK_INFO_MAX_LENGTH) {
                        textarea.value = textarea.value.slice(0, PARK_INFO_MAX_LENGTH);
                    }
                });
                textarea.__parkInfoLimitApplied = true;
            }
        };

        onMounted(applyTextLimit);
        onPatched(applyTextLimit);
    },
});
