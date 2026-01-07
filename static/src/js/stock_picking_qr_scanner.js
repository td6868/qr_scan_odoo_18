"use client"

/**
 * Main QR Scanner Component - Refactored version
 * Sử dụng kiến trúc mới với separation of concerns - No hooks version
 */
import { Component, useRef, onMounted } from "@odoo/owl"
import { QRScanner } from "./core/qr_scanner.js"
import { QRProcessor } from "./core/qr_processor.js"
import { PrepareScanHandler } from "./handlers/prepare_scan_handler.js"
import { ShippingScanHandler } from "./handlers/shipping_scan_handler.js"
import { ReceiveScanHandler } from "./handlers/receive_scan_handler.js"
import { CheckingScanHandler } from "./handlers/checking_scan_handler.js"
import { LocationScanHandler } from "./handlers/location_scan_handler.js"
import { CameraManager } from "./utils/camera_manager.js"
import { FileManager } from "./utils/file_manager.js"
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "./components/confirmation_dialog.js"
import { markup } from "@odoo/owl"


export class StockPickingQrScanner extends Component {
  setup() {
    super.setup()

    this.video = useRef("video");
    this.camera = useRef("camera");
    this.reader = useRef("reader");
    this.fileInput = useRef("fileInput");

    // Services - lấy từ env thay vì dùng hooks
    this.dialogService = this.env.services.dialog
    this.orm = this.env.services.orm
    this.notification = this.env.services.notification

    // State management - sử dụng object thông thường thay vì useState
    this.state = {
      // Scan type và mode
      selectedScanType: null,
      showModeSelector: true,
      scanMode: null,

      // Scanning state
      isScanning: false,

      // Picked data
      scannedPickingId: null,
      scannedPickingName: null,

      // UI states
      showCaptureArea: false,
      showNoteArea: false,
      showProductConfirmArea: false,
      showShippingTypeArea: false,
      showShippingCaptureArea: false,
      showShippingNoteArea: false,
      showLocationInventoryArea: false,

      // Data
      capturedImages: [],
      moveLines: [],
      selectedShippingType: null,
      shippingPhone: "",
      shippingCompany: "",
      scanNoteValue: "",
      scannedLocationId: null,
      scannedLocationName: null,
      locationData: null,
      quants: [],

      // Capture methods
      captureMethod: null,
    }

    // Core components - khởi tạo sau khi có services
    this.qrScanner = new QRScanner()
    this.qrProcessor = new QRProcessor(this.orm, this.notification)
    this.cameraManager = new CameraManager()
    this.fileManager = new FileManager()

    // Context từ action
    const context = this.env.services.action.currentController?.action?.context || {}
    this.scanType = context.scan_type

    // Initialize handlers sau khi có services
    this.handlers = {
      prepare: new PrepareScanHandler(this),
      shipping: new ShippingScanHandler(this),
      receive: new ReceiveScanHandler(this),
      checking: new CheckingScanHandler(this),
      kiemke: new LocationScanHandler(this),
    }

    onMounted(() => {
    })
  }

  async checkProductConfirm() {
    await this.handlers.prepare.checkProductQuantities();
  }

  /**
   * Trigger re-render khi state thay đổi
   */
  _updateState(newState) {
    Object.assign(this.state, newState)
    this.render()
  }

  /**
   * Thiết lập loại scan (outgoing/incoming/inventory)
   */
  setScanType(scanType) {
    this._updateState({
      selectedScanType: scanType,
      showModeSelector: true,
    })
    this.scanType = scanType
  }

  /**
   * Thiết lập chế độ scan (prepare/shipping/receive/checking)
   */
  setScanMode(mode) {
    this._updateState({
      scanMode: mode,
      showModeSelector: false,
    })

    // Delay để đảm bảo DOM đã update
    setTimeout(() => {
      this._startQRScanning()
    }, 100)
  }

  /**
   * Bắt đầu quét QR với kiến trúc mới
   */
  async _startQRScanning() {
    const context = {
      scan_type: this.scanType,
      scan_mode: this.state.scanMode,
    }

    await this.qrScanner.startScanning(
      (qrInfo) => this._handleQRScanSuccess(qrInfo, context),
      (error) => this._handleQRScanError(error),
    )
  }

  /**
   * Xử lý khi quét QR thành công
   */
  async _handleQRScanSuccess(qrInfo, context) {
    try {
      if (!qrInfo.isValid) {
        this._showError(qrInfo.error)
        return
      }

      // Xử lý QR thông qua QRProcessor
      const processResult = await this.qrProcessor.processQR(qrInfo, context)

      // Delegate cho handler tương ứng
      const handler = this.handlers[context.scan_mode]
      if (handler) {
        await handler.handleScanSuccess(processResult)
      } else {
        throw new Error(`Không tìm thấy handler cho mode: ${context.scan_mode}`)
      }
    } catch (error) {
      this._showError(error.message)
    }
  }

  /**
   * Xử lý lỗi quét QR
   */
  _handleQRScanError(error) {
    this._showError("Lỗi quét QR: " + error)
  }

  /**
   * Hiển thị lỗi
   */
  _showError(message) {
    this.notification.add(message, { type: "danger" })
    this.qrScanner.stopScanning()
  }

  /**
   * Reset về trạng thái ban đầu
   */
  async resetMode() {
    await this.qrScanner.stopScanning()
    this.cameraManager.stopCamera()

    // Reset tất cả states
    this._updateState({
      showModeSelector: true,
      scanMode: null,
      showCaptureArea: false,
      showNoteArea: false,
      showProductConfirmArea: false,
      showShippingTypeArea: false,
      showReceiveNoteArea: false,
      showCheckingCaptureArea: false,
      showCheckingProductConfirmArea: false,
      showLocationInventoryArea: false,
      capturedImages: [],
      moveLines: [],
      scannedPickingId: null,
      scannedPickingName: null,
      scannedLocationId: null,
      scannedLocationName: null,
      locationData: null,
      quants: [],
      captureMethod: null,
      shippingCaptureMethod: null,
      checkingCaptureMethod: null,
      receiveCaptureMethod: null,
    })
  }

  /**
   * Bắt đầu camera
   */
  async startCamera() {
    try {
      await this.cameraManager.startCamera(this.video.el)
    } catch (error) {
      this.notification.add(error.message, { type: "danger" })
    }
  }

  /**
   * Chụp ảnh
   */
  captureImage() {
    try {
      const image = this.cameraManager.captureImage()
      const newImages = [...this.state.capturedImages, image]
      this._updateState({ capturedImages: newImages })
    } catch (error) {
      this.notification.add(error.message, { type: "danger" })
    }
  }

  /**
   * Xử lý file upload
   */
  async handleFileUpload(file) {
    try {
      FileManager.validateFileSize(file)
      const image = await FileManager.handleFileUpload(file)
      const newImages = [...this.state.capturedImages, image]
      this._updateState({ capturedImages: newImages })
    } catch (error) {
      this.notification.add(error.message, { type: "danger" })
    }
  }

  /**
   * Lưu dữ liệu scan
   */
  async saveImgScanData() {
    if (!this.state.scannedPickingId) {
      this.notification.add("Không tìm thấy thông tin phiếu !", { type: "danger" })
      return
    }

    this.notification.add("Đã lưu thông tin quét QR và ảnh chụp thành công!", { type: "success" })

    this._updateState({
      showNoteArea: false,
      showProductConfirmArea: true,
      showCaptureArea: false,
    })
  }

  /**
   * Thu thập dữ liệu scan
   */
  _collectScanData() {
    const images = this.state.capturedImages.map((img) => ({
      data: FileManager.convertToBase64(img.data),
      name: img.name || `Image_${img.id}.jpg`,
      description: `Ảnh ${this.state.scanMode} - ${img.timestamp}`,
    }))

    return {
      images,
      scanNote: this.state.scanNoteValue,
      moveLineConfirms: this._getMoveLineConfirms(),
      shippingType: this.state.selectedShippingType,
      shippingPhone: this.state.shippingPhone,
      shippingCompany: this.state.shippingCompany,
    }
  }

  /**
   * Lấy thông tin xác nhận move lines
   */
  _getMoveLineConfirms() {
    return this.state.moveLines.map((line) => ({
      move_id: line.id,
      product_id: line.product_id,
      quantity_confirmed: line.quantity_confirmed,
      confirm_note: line.confirm_note,
    }))
  }

  // Event handlers
  onScanNoteInput(ev) {
    this._updateState({ scanNoteValue: ev.target.value })
  }

  onShippingTypeChange(ev) {
    this._updateState({ selectedShippingType: ev.target.value })
  }

  onShippingPhoneInput(ev) {
    this._updateState({ shippingPhone: ev.target.value })
  }

  onShippingCompanyInput(ev) {
    this._updateState({ shippingCompany: ev.target.value })
  }

  onConfirmQuantityInput = (ev, lineIndex) =>{
      const newMoveLines = [...this.state.moveLines]
      newMoveLines[lineIndex].quantity_confirmed = Number.parseFloat(ev.target.value) || 0
      this._updateState({ moveLines: newMoveLines })
    }

  onConfirmNoteInput = (ev, lineIndex) => {
    try {
      const newMoveLines = [...this.state.moveLines]
      newMoveLines[lineIndex].confirm_note = ev.target.value
      this._updateState({ moveLines: newMoveLines })
    } catch (error) {
      console.error("Error in onConfirmNoteInput:", error)
    }
  }

  onFileSelected(ev) {
    const file = ev.target.files[0]
    if (file) {
      this.handleFileUpload(file)
    }
    ev.target.value = ''
  }

  // UI helper methods
  onCaptureMethodChange(method) {
    this._updateState({ captureMethod: method })
    if (method === 'camera') {
      // Đợi DOM cập nhật để phần tử <video> được mount trước khi bật camera
      setTimeout(() => {
        this.startCamera()
      }, 100)
    }
  }

  saveImages() {
    this._updateState({
      showCaptureArea: false,
      showNoteArea: true,
    })
  }

  saveCheckingImages() {
    this._updateState({
      showCaptureArea: false,
      showProductConfirmArea: true,
    })
  }

  confirmShippingType = () => {
    if (!this.state.selectedShippingType) {
      this._showNotification("Vui lòng chọn loại vận chuyển!", "warning")
      return
    }

    this._updateState({ showShippingTypeArea: false })

    this._updateState({ showCaptureArea: true })
  }

  addMoreImages() {
    // Reset capture method để cho phép chọn lại
    this._updateState({
      captureMethod: null,
    })
  }

  removeImage(index, type) {
    if (type === "prepare" || type === "shipping" || type === "checking" || type === "receive") {
      const newImages = [...this.state.capturedImages]
      newImages.splice(index, 1)
      this._updateState({ capturedImages: newImages })
    }
  }


  saveProductConfirm() {
    if (!this.state.scannedPickingId || this.state.moveLines.length === 0) {
      this.notification.add("Không có thông tin sản phẩm để xác nhận.", { type: "danger" })
      return
    }

    this.dialogService.add(ConfirmationDialog, {
      title: "Xác nhận lưu",
      body: "Bạn có chắc chắn muốn lưu các thay đổi này không?",
      confirm: async () => {
        const handler = this.handlers[this.state.scanMode]
        if (!handler) {
          this.notification.add("Không tìm thấy handler phù hợp", { type: "danger" })
          return
        }

        const data = this._collectScanData()
        await handler.saveToDatabase(data) // Gọi method lưu database riêng
      },
    })


  }

  saveShippingData() {
    if (!this.state.scannedPickingId) {
      this.notification.add("Không có thông tin sản phẩm để xác nhận.", { type: "danger" })
      return
    } 

    this.dialogService.add(ConfirmationDialog, {
      title: "Xác nhận lưu",
      body: "Bạn có chắc chắn muốn lưu các thay đổi này không?",
      confirm: async () => {
        const handler = this.handlers[this.state.scanMode]
        if (!handler) {
          this.notification.add("Không tìm thấy handler phù hợp", { type: "danger" })
          return
        }
        const data = this._collectScanData()
        await handler.saveToDatabase(data)


      },
    })
  }

  saveReceiveData() {
    this.dialogService.add(ConfirmationDialog, {
      title: "Xác nhận lưu",
      body: "Bạn có chắc chắn muốn lưu các thay đổi này không?",
      confirm: async () => {
        const handler = this.handlers[this.state.scanMode]
        if (!handler) {
          this.notification.add("Không tìm thấy handler phù hợp", { type: "danger" })
          return
        }
        const data = this._collectScanData()
        await handler.saveScanReceiveData(data)
      },
    })
  }

// ************************************************************
  // ========== LOCATION INVENTORY METHODS ==========
// ************************************************************

  onLocationQuantityUpdate(event) {
    // Keep raw ID to support temporary string IDs like "new_..."
    const quantId = event.target.dataset.quantId
    const newQuantity = parseFloat(event.target.value) || 0
    
    if (newQuantity < 0) {
      this.notification.add("Số lượng không âm", { type: "warning" })
      event.target.value = 0
      return
    }
    
    const handler = this.handlers.kiemke
    if (handler) {
      handler.updateProductQuantity(quantId, newQuantity)
    }
  }
  
  onAddNewProduct() {
    // Hiển thị dialog tìm kiếm và chọn sản phẩm
    this.dialogService.add(ConfirmationDialog, {
      title: "Thêm sản phẩm mới",
      body: markup(`
        <div class="form-group">
          <label>Tìm kiếm sản phẩm:</label>
          <div class="dropdown w-100">
            <input type="text" 
                  id="productSearchInput" 
                  class="form-control" 
                  placeholder="Nhập tên hoặc mã sản phẩm..." 
                  autocomplete="off"
                  data-bs-toggle="dropdown"
                  aria-expanded="false">
            <ul class="dropdown-menu w-100 mt-1" id="newProductSelect">
              <li><span class="dropdown-item-text">-- Nhập từ khóa tìm kiếm --</span></li>
            </ul>
          </div>
        </div>

        <div class="form-group mt-2">
          <label>Số lượng:</label>
          <input type="number" id="newProductQuantity" class="form-control" min="0" step="0.01" value="1">
        </div>
      `),
      confirm: async () => {
        const productSearchInput = document.getElementById('productSearchInput')
        const quantityInput = document.getElementById('newProductQuantity')
        
        const selectedProductId = productSearchInput.dataset.selectedProductId
        if (!selectedProductId) {
          this.notification.add("Vui lòng chọn sản phẩm", { type: "warning" })
          return
        }
        
        const productId = parseInt(selectedProductId)
        const quantity = parseFloat(quantityInput.value) || 0
        
        if (quantity <= 0) {
          this.notification.add("Số lượng phải lớn hơn 0", { type: "warning" })
          return
        }
        
        const handler = this.handlers.kiemke
        if (handler) {
          await handler.addNewProduct(productId, quantity)
        }
      },
    })
    
    // Setup search functionality
    setTimeout(() => {
      this._setupProductSearch()
    }, 100)
  }

  _setupProductSearch() {
    const searchInput = document.getElementById('productSearchInput')
    const productDropdown = document.getElementById('newProductSelect')
    
    if (!searchInput || !productDropdown) return
    
    let searchTimeout
    
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout)
      const searchTerm = e.target.value.trim()
      
      // Clear selected product when typing
      delete searchInput.dataset.selectedProductId
      
      searchTimeout = setTimeout(async () => {
        if (searchTerm.length >= 2) {
          await this._searchAndLoadProducts(searchTerm, productDropdown)
        } else {
          // Clear dropdown if search term too short
          productDropdown.innerHTML = '<li><span class="dropdown-item-text">-- Nhập ít nhất 2 ký tự --</span></li>'
        }
      }, 300) // Debounce 300ms
    })
    
    // Setup dropdown click handlers
    productDropdown.addEventListener('click', (e) => {
      if (e.target.classList.contains('dropdown-item') && e.target.dataset.productId) {
        const productId = e.target.dataset.productId
        const productName = e.target.textContent
        
        // Set selected product
        searchInput.value = productName
        searchInput.dataset.selectedProductId = productId
        
        // Close dropdown
        document.getElementById("newProductSelect").classList.remove("show");
      }
    })
    
    // Focus on search input
    searchInput.focus()
  }
  
  async _searchAndLoadProducts(searchTerm, dropdownElement) {
    try {
      dropdownElement.innerHTML = '<li><span class="dropdown-item-text">Đang tìm kiếm...</span></li>'
      
      console.log('Searching for products with term:', searchTerm)
      
      const products = await this.orm.call(
        'stock.quant',
        'search_products_for_inventory',
        [],
        {
          search_term: searchTerm,
          limit: 50
        }
      )
      
      console.log('Products received from backend:', products)
      
      dropdownElement.innerHTML = ''
      
      if (products && products.length > 0) {
        products.forEach(product => {
          const listItem = document.createElement('li')
          const link = document.createElement('a')
          link.className = 'dropdown-item'
          link.href = '#'
          link.dataset.productId = product.id
          link.textContent = `${product.default_code || ''} - ${product.name}`
          listItem.appendChild(link)
          dropdownElement.appendChild(listItem)
        })
        console.log(`Added ${products.length} products to dropdown`)
      } else {
        dropdownElement.innerHTML = '<li><span class="dropdown-item-text">Không tìm thấy sản phẩm</span></li>'
        console.log('No products found')
      }
    } catch (error) {
      console.error('Lỗi tìm kiếm sản phẩm:', error)
      dropdownElement.innerHTML = '<li><span class="dropdown-item-text">Lỗi tìm kiếm</span></li>'
    }
  }
  
  onDeleteProductFromInventory(event) {
    const dataset = event.currentTarget.dataset
    const key = Object.keys(dataset)[0]
    const value = dataset[key]  // "12343.1"
    const productId = parseInt(value.split('.')[0])
    // Keep raw ID to support temporary string IDs like "new_..."
    const quantId = event.currentTarget.dataset.quantId
    
    // Tìm thông tin sản phẩm
    const quant = this.state.quants.find(q => String(q.id) === String(quantId))
    if (!quant) {
      this.notification.add("Không tìm thấy sản phẩm", { type: "warning" })
      return
    }
    
    this.dialogService.add(ConfirmationDialog, {
      title: "Xác nhận xóa sản phẩm",
      body: `Bạn có chắc chắn muốn xóa sản phẩm "${quant.product_name}" khỏi vị trí này không? Hành động này không thể hoàn tác.`,
      confirm: async () => {
        const handler = this.handlers.kiemke
        if (handler) {
          await handler.removeProductFromInventory(productId)
        }
      },
    })
  }

  onConfirmLocationInventory() {
    this.dialogService.add(ConfirmationDialog, {
      title: "Xác nhận kiểm kê",
      body: "Bạn có chắc chắn muốn xác nhận kiểm kê này không? Hệ thống sẽ cập nhật số lượng kho.",
      confirm: async () => {
        const handler = this.handlers.kiemke
        if (handler) {
          await handler.confirmInventory()
        }
      },
    })
  }
  
  onSearchProductOtherLocations(event) {
    const dataset = event.currentTarget.dataset
    const key = Object.keys(dataset)[0]
    const value = dataset[key]  // "12343.1"
    const productId = parseInt(value.split('.')[0])

    const handler = this.handlers.kiemke
    if (handler) {
      handler.searchProductInOtherLocations(productId).then(locations => {
        this._showOtherLocationsModal(locations)
      })
    }
  }
  
  _showOtherLocationsModal(locations) {
    let contentHtml;
    console.log("locations:", locations);               // In object rõ ràng trong console
    console.log("json:", JSON.stringify(locations));   // In ra dạng chuỗi JSON

    if (locations && locations.length > 0) {
        const rows = locations.map(loc => `
            <tr>
                <td>${loc.location_name}</td>
                <td>${loc.quantity}</td>
                <td>${loc.reserved_quantity}</td>
                <td>${loc.available_quantity}</td>
                <td>${loc.uom_name}</td>
            </tr>
        `).join("");

        contentHtml = `
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Vị trí</th>
                            <th>Số lượng</th>
                            <th>Đã đặt</th>
                            <th>Khả dụng</th>
                            <th>Đơn vị</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        contentHtml = `
            <div class="text-center text-muted">
                <p>Không tìm thấy sản phẩm ở vị trí khác</p>
            </div>
        `;
    }

    this.dialogService.add(ConfirmationDialog, {
      title: "Sản phẩm ở vị trí khác",
      body: markup(contentHtml),
      confirm: () => {}, // Empty confirm function
      confirmText: "Đóng"
    });
  }

}

// Sử dụng template từ file XML hiện có
StockPickingQrScanner.template = "qr_scan_odoo_18.StockPickingQrScanner"
registry.category("actions").add("action_stock_picking_qr_scanner_outgoing", StockPickingQrScanner)
registry.category("actions").add("action_stock_picking_qr_scanner_incoming", StockPickingQrScanner) 
registry.category("actions").add("action_stock_picking_qr_scanner_inventory", StockPickingQrScanner)