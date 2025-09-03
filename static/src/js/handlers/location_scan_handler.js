/**
 * Location Scan Handler - Xử lý logic cho quét QR vị trí kho
 */
import { BaseScanHandler } from "./base_scan_handler.js"

export class LocationScanHandler extends BaseScanHandler {
  constructor(component) {
    super(component)
    this.locationData = null
    this.quants = []
  }

  /**
   * Xử lý khi quét QR vị trí kho thành công
   */
  async handleScanSuccess(processResult) {
    const { location, qrInfo, context } = processResult
    
    try {
      // Load dữ liệu vị trí và sản phẩm
      await this._loadLocationData(location)
      
      // Hiển thị thông báo thành công
      this._showSuccessMessage(location, context)
      
      // Cập nhật state của component
      this._updateComponentState(location, qrInfo, context)
      
      // Hiển thị giao diện kiểm kê
      this.component._updateState({
        showLocationInventoryArea: true,
        locationData: this.locationData,
        quants: this.quants
      })
      
    } catch (error) {
      console.error('Lỗi xử lý quét vị trí:', error)
      this.notification.add('Lỗi xử lý quét vị trí: ' + error.message, { type: 'danger' })
    }
  }

  /**
   * Load dữ liệu vị trí và sản phẩm
   */
  async _loadLocationData(location) {
    try {
      // Lấy thông tin vị trí
      this.locationData = {
        id: location.id,
        name: location.name,
        complete_name: location.complete_name,
        usage: location.usage
      }

      // Lấy danh sách sản phẩm trong vị trí
      const quantsResult = await this.orm.call(
        'stock.quant',
        'get_location_products',
        [location.id]
      )
      
      this.quants = quantsResult.map(quant => ({
        id: quant.id,
        product_id: quant.product_id[0],
        product_name: quant.product_id[1],
        product_code: quant.product_id[2] || '',
        quantity: quant.quantity,
        counted_quantity: quant.quantity, // Mặc định bằng số lượng hiện tại
        uom_name: quant.product_uom_id[1],
        difference: 0
      }))

    } catch (error) {
      console.error('Lỗi load dữ liệu vị trí:', error)
      throw new Error('Không thể tải dữ liệu vị trí')
    }
  }

  /**
   * Hiển thị thông báo thành công cho vị trí
   */
  _buildSuccessMessage(location, context) {
    return `
      <div class="alert alert-success">
        <h4><i class="fa fa-map-marker me-2"></i>Quét vị trí thành công!</h4>
        <p><strong>Vị trí:</strong> ${location.complete_name}</p>
        <p><strong>Số sản phẩm:</strong> ${this.quants.length}</p>
      </div>
    `
  }

  /**
   * Cập nhật state cho vị trí
   */
  _updateComponentState(location, qrInfo, context) {
    const newState = {
      scannedLocationId: location.id,
      scannedLocationName: location.complete_name,
      scanMode: context.scan_mode || 'kiemke'
    }
    this.component._updateState(newState)
  }

  /**
   * Cập nhật số lượng kiểm kê cho sản phẩm
   */
  async updateProductQuantity(quantId, newQuantity) {
    try {
      const quant = this.quants.find(q => q.id === quantId)
      if (!quant) {
        throw new Error('Không tìm thấy sản phẩm')
      }

      // Cập nhật số lượng và tính chênh lệch
      quant.counted_quantity = parseFloat(newQuantity) || 0
      quant.difference = quant.counted_quantity - quant.quantity

      // Cập nhật state
      this.component._updateState({ quants: [...this.quants] })

      // this.notification.add('Cập nhật số lượng thành công', { type: 'success' })
      
    } catch (error) {
      console.error('Lỗi cập nhật số lượng:', error)
      this.notification.add('Lỗi cập nhật số lượng: ' + error.message, { type: 'danger' })
    }
  }

  /**
   * Thêm sản phẩm mới vào vị trí
   */
  async addNewProduct(productId, quantity) {
    try {
      // Kiểm tra sản phẩm đã tồn tại trong vị trí chưa
      const existingQuant = this.quants.find(q => q.product_id === productId)
      if (existingQuant) {
        throw new Error('Sản phẩm đã tồn tại trong vị trí này')
      }

      // Tìm kiếm sản phẩm thông qua inventory processor
      const products = await this.orm.call(
        'stock.quant',
        'search_products_for_inventory',
        [],
        { search_term: productId.toString(), limit: 20 }
      )

      if (!products || products.length === 0) {
        throw new Error('Không tìm thấy sản phẩm')
      }

      const productInfo = products[0]
      
      // Tạo quant mới
      const newQuant = {
        id: `new_${Date.now()}`, // ID tạm thời
        product_id: productInfo.id,
        product_name: productInfo.name,
        product_code: productInfo.default_code || '',
        quantity: 0,
        counted_quantity: parseFloat(quantity) || 0,
        uom_name: productInfo.uom_name,
        difference: parseFloat(quantity) || 0,
        is_new: true
      }

      this.quants.push(newQuant)
      
      // Cập nhật state
      this.component._updateState({ quants: [...this.quants] })

      this.notification.add('Thêm sản phẩm thành công', { type: 'success' })
      
    } catch (error) {
      console.error('Lỗi thêm sản phẩm:', error)
      this.notification.add('Lỗi thêm sản phẩm: ' + error.message, { type: 'danger' })
    }
  }

  /**
   * Xác nhận kiểm kê và lưu vào database
   */
  async confirmInventory() {
    try {
      // Tạo lịch sử kiểm kê
      const scanHistory = await this.orm.call(
        'stock.location.scan.history',
        'create',
        [{
          'location_id': this.component.state.scannedLocationId,
          'note': this.component.state.scanNoteValue || ''
        }]
      )

      // Xử lý từng sản phẩm
      const results = []
      for (const quant of this.quants) {
        try {
          if (quant.is_new) {
            // Thêm sản phẩm mới - sử dụng add_product_to_inventory
            const result = await this.orm.call(
              'stock.quant',
              'add_product_to_inventory',
              [this.component.state.scannedLocationId, quant.product_id, quant.counted_quantity]
            )
            results.push(result)
          } else if (quant.counted_quantity !== quant.quantity) {
            // Cập nhật sản phẩm hiện có
            const quantRecord = await this.orm.call(
              'stock.quant',
              'browse',
              [quant.id]
            )
            const result = await this.orm.call(
              'stock.quant',
              'update_inventory_count',
              [quant.id, quant.counted_quantity]
            )
            results.push(result)
          }
        } catch (error) {
          console.error(`Lỗi xử lý sản phẩm ${quant.product_name}:`, error)
          results.push({
            success: false,
            error: `Lỗi xử lý ${quant.product_name}: ${error.message}`
          })
        }
      }

      // Lưu dữ liệu vào lịch sử
      const inventoryData = this.quants.map(quant => ({
        product_id: quant.product_id,
        product_name: quant.product_name,
        current_quantity: quant.quantity,
        counted_quantity: quant.counted_quantity,
        difference: quant.counted_quantity - quant.quantity
      }))

      await this.orm.call(
        'stock.location.scan.history',
        'save_inventory_scan',
        [scanHistory, inventoryData, this.component.state.scanNoteValue || '']
      )

      // Kiểm tra kết quả
      const errors = results.filter(r => !r.success)
      if (errors.length > 0) {
        this.notification.add(`Kiểm kê hoàn thành với ${errors.length} lỗi`, { type: 'warning' })
      } else {
        this.notification.add('Kiểm kê thành công!', { type: 'success' })
      }
      
      // Reset state
      this.component._updateState({
        showLocationInventoryArea: false,
        scannedLocationId: null,
        scannedLocationName: null,
        quants: []
      })
      
      // Reset mode
      this.component.resetMode()
      
    } catch (error) {
      console.error('Lỗi xác nhận kiểm kê:', error)
      this.notification.add('Lỗi xác nhận kiểm kê: ' + error.message, { type: 'danger' })
    }
  }

  /**
   * Tìm kiếm sản phẩm ở vị trí khác
   */
  async searchProductInOtherLocations(productId) {
    try {
      const result = await this.orm.call(
        'stock.quant',
        'get_product_other_locations',
        [this.component.state.scannedLocationId],
        {
          product_id: productId,
          exclude_location_id: this.component.state.scannedLocationId
        }
      )
      
      return result || []
      
    } catch (error) {
      console.error('Lỗi tìm kiếm sản phẩm:', error)
      this.notification.add('Lỗi tìm kiếm sản phẩm: ' + error.message, { type: 'danger' })
      return []
    }
  }

  /**
   * Xóa sản phẩm khỏi inventory
   */
  async removeProductFromInventory(productId) {
    try {
      // Gọi remove_product_from_inventory để xóa sản phẩm
      const result = await this.orm.call(
        'stock.quant',
        'remove_product_from_inventory',
        [this.locationData.id, productId]
      )

      if (!result.success) {
        throw new Error(result.error || 'Không thể xóa sản phẩm')
      }

      // Xóa sản phẩm khỏi danh sách quants
      this.quants = this.quants.filter(q => q.product_id !== productId)
      
      // Cập nhật state
      this.component._updateState({ quants: [...this.quants] })

      this.notification.add(`Đã xóa ${result.product_name} khỏi ${result.location_name}`, { type: 'success' })
      
    } catch (error) {
      console.error('Lỗi xóa sản phẩm:', error)
      this.notification.add('Lỗi xóa sản phẩm: ' + error.message, { type: 'danger' })
    }
  }

  /**
   * Lưu dữ liệu scan (override từ BaseScanHandler)
   */
  async saveScanData(data) {
    // Không cần implement cho location scan
    // Dữ liệu được lưu trực tiếp qua confirmInventory
    return true
  }
}
