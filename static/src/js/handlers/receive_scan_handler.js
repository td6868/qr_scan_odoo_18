/**
 * Receive Scan Handler - Xử lý logic cho chế độ nhận hàng
 */
import { BaseScanHandler } from "./base_scan_handler.js"

export class ReceiveScanHandler extends BaseScanHandler {
  _buildSuccessMessage(picking, context) {
    return `
            <div class="alert alert-success">
                <h4><i class="fa fa-download me-2"></i>Quét thành công - Chế độ nhận hàng!</h4>
                <p><strong>Phiếu nhập kho:</strong> ${picking.name}</p>
                <p><strong>Nhà cung cấp:</strong> ${(picking.partner_id && picking.partner_id[1]) || "N/A"}</p>
            </div>
        `
  }

  async saveScanReceiveData(data) {
    const { scanNote } = data

    try {
      const result = await this.orm.call("stock.picking", "update_scan_info",
        [this.component.state.scannedPickingId],
        {
          scan_note: scanNote,
          scan_mode: this.component.state.scanMode,
        },
      )

      if (result) {
        this.notification.add("Đã xác nhận nhận hàng thành công!", { type: "success" })
        this.component.resetMode()
      }
    } catch (error) {
      console.error("Lỗi xác nhận nhận hàng:", error)
      this.notification.add("Lỗi lưu dữ liệu: " + error.message, { type: "danger" })
    }
  }
}
