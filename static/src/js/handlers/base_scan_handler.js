/**
 * Base Scan Handler - Class cơ sở cho tất cả các handler
 */
export class BaseScanHandler {
  constructor(component) {
    this.component = component
    this.orm = component.orm
    this.notification = component.notification
  }

  /**
   * Xử lý sau khi QR được quét thành công
   * @param {Object} processResult - Kết quả từ QRProcessor
   */
  async handleScanSuccess(processResult) {
    const { picking, qrInfo, context, nextAction } = processResult

    // Hiển thị thông báo thành công
    this._showSuccessMessage(picking, context)

    // Cập nhật state của component
    this._updateComponentState(picking, qrInfo, nextAction)

    // Load dữ liệu cần thiết
    await this._loadRequiredData(picking, context)
  }

  /**
   * Hiển thị thông báo thành công (override trong subclass)
   */
  _showSuccessMessage(picking, context) {
    const message = this._buildSuccessMessage(picking, context)
    if (this.component.result && this.component.result.el) {
      this.component.result.el.innerHTML = message
    }
  }

  /**
   * Xây dựng HTML thông báo thành công (override trong subclass)
   */
  _buildSuccessMessage(picking, context) {
    return `
            <div class="alert alert-success">
                <h4><i class="fa fa-check-circle me-2"></i>Quét thành công!</h4>
                <p><strong>Phiếu:</strong> ${picking.name}</p>
                <p><strong>Khách hàng:</strong> ${(picking.partner_id && picking.partner_id[1]) || "N/A"}</p>
            </div>
        `
  }

  /**
   * Cập nhật state của component
   */
  _updateComponentState(picking, qrInfo, nextAction) {
    const newState = {
      scannedPickingId: picking.id,
      scannedPickingName: picking.name,
      [nextAction]: true,
    }
    this.component._updateState(newState)
  }

  /**
   * Load dữ liệu cần thiết (override trong subclass)
   */
  async _loadRequiredData(picking, context) {
    // Override trong subclass nếu cần
  }

  /**
   * Lưu dữ liệu scan (override trong subclass)
   */
  async saveScanData(data) {
    throw new Error("saveScanData must be implemented in subclass")
  }
}
