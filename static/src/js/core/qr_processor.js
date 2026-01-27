/**
 * QR Processor - Xử lý logic dựa trên loại QR và context
 */
export class QRProcessor {
  constructor(orm, notification) {
    this.orm = orm
    this.notification = notification
  }

  /**
   * Xử lý QR đã được quét dựa trên context
   * @param {Object} qrInfo - Thông tin QR từ scanner
   * @param {Object} context - Context chứa scan_type và scan_mode
   */
  async processQR(qrInfo, context) {
    if (!qrInfo.isValid) {
      throw new Error(qrInfo.error)
    }

    // Validate model
    if (qrInfo.model === "stock.picking") {
      return await this._processPickingQR(qrInfo, context)
    } else if (qrInfo.model === "stock.location") {
      return await this._processLocationQR(qrInfo, context)
    } else {
      throw new Error(`Model không được hỗ trợ: ${qrInfo.model}`)
    }
  }

  async _processPickingQR(qrInfo, context) {
    // Lấy thông tin picking từ database
    const picking = await this._fetchPicking(qrInfo.recordId)

    // Validate picking dựa trên context
    await this._validatePickingForContext(picking, context)

    return {
      model: "stock.picking",
      picking,
      qrInfo,
      context,
      nextAction: this._determinePickingNextAction(picking, context),
    }
  }

  /**
   * Xử lý QR cho stock.location
   */
  async _processLocationQR(qrInfo, context) {
    // Lấy thông tin location từ database
    // qrInfo.recordId đối với stock.location sẽ là id_loc_qr
    const location = await this._fetchLocationByQrId(qrInfo.recordId)

    return {
      model: "stock.location",
      location,
      qrInfo,
      context,
      nextAction: this._determineLocationNextAction(location, context),
    }
  }

  /**
   * Lấy thông tin picking từ database
   */
  async _fetchPicking(pickingId) {
    const domain = [["id", "=", pickingId]]
    const fields = ["id", "name", "state", "picking_type_code", "partner_id", "is_prepared", "is_shipped"]
    const pickings = await this.orm.call("stock.picking", "search_read", [domain, fields])

    if (!pickings || pickings.length === 0) {
      throw new Error("Không tìm thấy phiếu xuất kho!")
    }

    return pickings[0]
  }

  /**
   * Lấy thông tin location từ database
   */
  async _fetchLocationByQrId(idLocQr) {
    const domain = [["id_loc_qr", "=", idLocQr]]
    const locations = await this.orm.call("stock.location", "search_read", [domain])

    if (!locations || locations.length === 0) {
      throw new Error("Không tìm thấy vị trí kho!")
    }

    return locations[0]
  }

  async _validatePickingForContext(picking, context) {
    const { scan_mode } = context

    // Gọi backend để validate logic phức tạp (bao gồm check history, state, etc.)
    try {
      const result = await this.orm.call("stock.picking", "action_validate_qr_scan", [picking.id], {
        scan_mode: scan_mode
      });

      if (result && result.status === 'error') {
        throw new Error(result.message);
      }
    } catch (error) {
      // Re-throw if it's our validation error, otherwise format it
      if (error instanceof Error) throw error;
      throw new Error("Lỗi xác thực từ hệ thống: " + (error.message || error));
    }
  }

  /**
   * Xác định hành động tiếp theo dựa trên context
   */
  _determinePickingNextAction(picking, context) {
    const { scan_mode } = context

    const actionMap = {
      prepare: "showProductConfirmArea",
      shipping: "showShippingTypeArea",
      receive: "showReceiveNoteArea",
      checking: "showCaptureArea",
    }

    return actionMap[scan_mode] || "showCaptureArea"
  }

  /**
   * Xác định hành động tiếp theo cho location
   */
  _determineLocationNextAction(location, context) {
    const { scan_mode } = context

    const actionMap = {
      kiemke: "showLocationInventoryArea",
    }

    return actionMap[scan_mode] || "showLocationInventoryArea"
  }
}
