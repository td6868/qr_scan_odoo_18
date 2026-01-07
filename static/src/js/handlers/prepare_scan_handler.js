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
          [this.component.state.scannedPickingId],
          { 
            
          }
        )
        this.notification.add("Đã xác nhận và lưu thông tin chuẩn bị hàng thành công!", { type: "success" })
      } catch (validateError) {
      }

      this.component._updateState({ showProductConfirmArea: false })
      this.component.resetMode()
    } catch (error) {
      // Extract the actual error message from the server response
      let errorMessage = "Lỗi lưu dữ liệu"
      
      // Check if it's an Odoo server error
      if (error && error.data && error.data.message) {
        errorMessage = error.data.message
      } 
      // Check for network or other errors
      else if (error.message) {
        errorMessage = error.message
      }
      
      // Display the error to the user
      this.notification.add(errorMessage, { 
        type: "danger",
        sticky: true, // Make the notification stay until dismissed
      })
    }
  }

  async checkProductQuantities() {
    const { moveLines } = this.component.state;
    const updatedMoveLines = [];

    for (const moveLine of moveLines) {
      const productId = moveLine.product_id;
      const enteredQuantity = moveLine.quantity_confirmed;

      try {
        // Fetch actual quantity from Odoo (assuming a method exists or needs to be created)
        // For now, let's simulate this with a direct ORM call to get product quantity
        const actualQuantity = await this.orm.call(
          "stock.quant",
          "get_product_available_quantity",
          [productId]
        );

        if (enteredQuantity > actualQuantity) {
          this.notification.add(
            `Số lượng nhập cho sản phẩm ${moveLine.product_name} (${enteredQuantity}) lớn hơn số lượng thực tế trong kho (${actualQuantity}). Đã cập nhật lại thành ${actualQuantity}.`,
            { type: "warning" }
          );
          updatedMoveLines.push({ ...moveLine, quantity_confirmed: actualQuantity });
        } else {
          updatedMoveLines.push(moveLine);
        }
      } catch (error) {
        console.error(`Error checking quantity for product ${moveLine.product_name}:`, error);
        this.notification.add(
          `Lỗi khi kiểm tra số lượng cho sản phẩm ${moveLine.product_name}: ${error.message}`,
          { type: "danger" }
        );
        updatedMoveLines.push(moveLine); // Keep original if error occurs
      }
    }
    this.component._updateState({ moveLines: updatedMoveLines });
  }

}
