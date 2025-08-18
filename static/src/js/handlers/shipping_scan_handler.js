/**
 * Shipping Scan Handler - Xử lý logic cho chế độ vận chuyển
 */
import { BaseScanHandler } from "./base_scan_handler.js"

export class ShippingScanHandler extends BaseScanHandler {
  _buildSuccessMessage(picking, context) {
    return `
            <div class="alert alert-success">
                <h4><i class="fa fa-truck me-2"></i>Quét thành công - Chế độ vận chuyển!</h4>
                <p><strong>Phiếu xuất kho:</strong> ${picking.name}</p>
                <p><strong>Khách hàng:</strong> ${picking.partner_id[1] || "N/A"}</p>
                <p><strong>Trạng thái:</strong> <span class="badge bg-info">Đã chuẩn bị hàng</span></p>
            </div>
        `
  }

  async _loadRequiredData(picking, context) {
    // Shipping mode doesn't need to load move lines
    // Just set basic state
    this.component._updateState({
      shippingType: "",
      shippingPhone: "",
      shippingCompany: "",
    })
  }

  async saveToDatabase(data) {
    const { images, scanNote, shippingType, shippingPhone, shippingCompany } = data

    try {
      let imagesData = []
      if (shippingType === "delivery" && images && images.length > 0) {
        imagesData = images.map((img, index) => ({
          data: img.data.includes(',') ? img.data.split(",")[1] : img.data,
          name: img.name,
          description: `Ảnh minh chứng vận chuyển #${index + 1}`,
        }))
      }

      await this.orm.call("stock.picking", "update_scan_info", 
        [this.component.state.scannedPickingId],
        {
          images_data: imagesData, // Will be empty array for pickup/viettelpost
          scan_note: scanNote,          
          shipping_type: shippingType,
          shipping_phone: shippingPhone,
          shipping_company: shippingCompany,
          scan_mode: this.component.state.scanMode,
        }
      )

      this.notification.add("Đã lưu thông tin vận chuyển thành công!", { type: "success" })

      this.component._updateState({ showNoteArea: false })
      this.component.resetMode()
    } catch (error) {
      console.error("Lỗi lưu dữ liệu vận chuyển:", error)
      this.notification.add("Lỗi lưu dữ liệu: " + error.message, { type: "danger" })
    }
  }
  async saveScanShippingData(data) {
    return this.saveToDatabase(data)
  }
}
