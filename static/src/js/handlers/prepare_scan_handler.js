/**
 * Prepare Scan Handler - Xử lý logic cho chế độ chuẩn bị hàng
 */
import { BaseScanHandler } from "./base_scan_handler.js"

export class PrepareScanHandler extends BaseScanHandler {
  _buildSuccessMessage(picking, context) {
    return `
            <div class="alert alert-success">
                <h4><i class="fa fa-check-circle me-2"></i>Quét thành công - Chế độ chuẩn bị hàng!</h4>
                <p><strong>Phiếu xuất kho:</strong> ${picking.name}</p>
                <p><strong>Khách hàng:</strong> ${picking.partner_id[1] || "N/A"}</p>
            </div>
        `
  }

  async _loadRequiredData(picking, context) {
    // Load move lines cho việc xác nhận sản phẩm
    await this._loadMoveLines(picking.id)
  }

  async _loadMoveLines(pickingId) {
    try {
      const moveLines = await this.orm.call("stock.picking", "read", [[pickingId], ["move_ids_without_package"]])

      if (moveLines && moveLines[0] && moveLines[0].move_ids_without_package) {
        const moves = await this.orm.call("stock.move", "read", [
          moveLines[0].move_ids_without_package,
          ["product_id", "product_uom_qty", "product_uom", "quantity"],
        ])

        const newMoveLines = moves.map((move) => ({
          id: move.id,
          product_id: move.product_id[0],
          product_name: move.product_id[1],
          quantity: move.product_uom_qty,
          quantity_confirmed: move.product_uom_qty,
          uom: move.product_uom[1],
          confirm_note: "",
        }))

        this.component._updateState({ moveLines: newMoveLines })
      }
    } catch (error) {
      console.error("Lỗi load move lines:", error)
      this.notification.add("Lỗi tải danh sách sản phẩm!", { type: "danger" })
    }
  }

  async saveToDatabase(data) {
    const { images, scanNote, moveLineConfirms } = data

    console.log("PrepareScanHandler.saveToDatabase called with:", {
      pickingId: this.component.state.scannedPickingId,
      imagesCount: images?.length || 0,
      scanNote: scanNote,
      moveLineConfirmsCount: moveLineConfirms?.length || 0,
    })

    try {
      const imagesData = images.map((img, index) => {
        return {
          data: img.data.includes(',') ? img.data.split(",")[1] : img.data,
          name: img.name,
          description: `Ảnh minh chứng chuẩn bị hàng #${index + 1}`,
        };
      })

      console.log("Calling update_scan_info with scan_type: prepare")
      const scanResult = await this.orm.call(
        "stock.picking",
        "update_scan_info",
        [this.component.state.scannedPickingId],
        {
          images_data: imagesData,
          scan_note: scanNote,
          move_line_confirms: moveLineConfirms,
          scan_mode: this.component.state.scanMode,
        }
      )
      console.log("update_scan_info result:", scanResult)

      this.notification.add("Đã lưu tất cả thông tin thành công!", { type: "success" })

      try {
        await this.orm.call(
          "stock.picking", 
          "button_validate", 
          [this.component.state.scannedPickingId],
          { 
            
          }
        )
        this.notification.add("Đã xác nhận và lưu thông tin vận chuyển thành công!", { type: "success" })
      } catch (validateError) {
        console.error("Lỗi xác nhận phiếu giao hàng:", validateError)
        throw new Error("Đã lưu thông tin nhưng không thể xác nhận phiếu giao hàng: " + validateError.message)
      }

      this.component._updateState({ showProductConfirmArea: false })
      this.component.resetMode()
    } catch (error) {
      console.error("Lỗi lưu dữ liệu:", error)
      this.notification.add("Lỗi lưu dữ liệu: " + error.message, { type: "danger" })
    }
  }

}
