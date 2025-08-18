/**
 * Confirmation Dialog Component
 */
import { Component } from "@odoo/owl"

export class ConfirmationDialog extends Component {
  static template = "qr_scan_odoo_18.ConfirmationDialog"
  static props = {
    title: String,
    body: String,
    confirm: Function,
    cancel: { type: Function, optional: true },
    confirmText: { type: String, optional: true },
    cancelText: { type: String, optional: true },
  }

  setup() {
    this.confirmText = this.props.confirmText || "Xác nhận"
    this.cancelText = this.props.cancelText || "Hủy"
  }

  async onConfirm() {
    if (this.props.confirm) {
      await this.props.confirm()
    }
    this.props.close()
  }

  onCancel() {
    if (this.props.cancel) {
      this.props.cancel()
    }
    this.props.close()
  }
}
