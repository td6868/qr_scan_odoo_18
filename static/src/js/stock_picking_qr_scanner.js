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
import { CameraManager } from "./utils/camera_manager.js"
import { FileManager } from "./utils/file_manager.js"
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "./components/confirmation_dialog.js"


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

      // Data
      capturedImages: [],
      moveLines: [],
      selectedShippingType: null,
      shippingPhone: "",
      shippingCompany: "",
      scanNoteValue: "",

      // Capture methods
      captureMethod: null,

      
    }


    // Core components - khởi tạo sau khi có services
    this.qrScanner = new QRScanner()
    this.qrProcessor = new QRProcessor(this.orm, this.notification)
    this.cameraManager = new CameraManager()

    // Context từ action
    const context = this.env.services.action.currentController?.action?.context || {}
    this.scanType = context.scan_type

    // Initialize handlers sau khi có services
    this.handlers = {
      prepare: new PrepareScanHandler(this),
      shipping: new ShippingScanHandler(this),
      receive: new ReceiveScanHandler(this),
      checking: new CheckingScanHandler(this),
    }

    onMounted(() => {
    })

  }

  /**
   * Mounted - khởi tạo refs sau khi component được mount
   */
  // mounted() {
  //   // Lấy refs từ DOM thay vì dùng useRef
  //   this.result = { el: this.el.querySelector('[t-ref="result"]') }
  //   this.video = { el: this.el.querySelector('[t-ref="video"]') }
  //   this.scanNote = { el: this.el.querySelector('[t-ref="scanNote"]') }
  //   this.fileInput = { el: this.el.querySelector('[t-ref="fileInput"]') }
  // }

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
      capturedImages: [],
      moveLines: [],
      scannedPickingId: null,
      scannedPickingName: null,
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
      console.error("[v0] Error in onConfirmNoteInput:", error)
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
  }

  onCheckingCaptureMethodChange(method) {
    this._updateState({ checkingCaptureMethod: method })
  }

  onReceiveCaptureMethodChange(method) {
    this._updateState({ receiveCaptureMethod: method })
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

    if (this.state.selectedShippingType === "delivery") {
      this._updateState({ showCaptureArea: true })
    } else {
      this._updateState({ showNoteArea: true })
    }
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

  viewImage(index, type) {
    // Implement image viewer modal
    console.log("View image:", index, type)
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

}

// Sử dụng template từ file XML hiện có
StockPickingQrScanner.template = "qr_scan_odoo_18.StockPickingQrScanner"
registry.category("actions").add("action_stock_picking_qr_scanner_outgoing", StockPickingQrScanner)
registry.category("actions").add("action_stock_picking_qr_scanner_incoming", StockPickingQrScanner) 
registry.category("actions").add("action_stock_picking_qr_scanner_inventory", StockPickingQrScanner)