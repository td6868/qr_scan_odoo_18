"use client"

/**
 * Core QR Scanner - Chỉ chịu trách nhiệm quét QR và trả về thông tin model
 */
import { Component } from "@odoo/owl"


export class QRScanner extends Component {
  setup() {
    // Không sử dụng hooks trong core scanner
    this.isScanning = false
    this.qrScanner = null
  }

  /**
   * Bắt đầu quét QR
   * @param {Function} onSuccess - Callback khi quét thành công
   * @param {Function} onError - Callback khi có lỗi
   */
  async startScanning(onSuccess, onError) {
    try {
      // 1. Kiểm tra nếu đang chạy trong App Odoo Mobile (Sử dụng Native Scanner)
      if (this.env && this.env.services && this.env.services.mobile && this.env.services.mobile.methods.scanBarcode) {
        try {
          const result = await this.env.services.mobile.methods.scanBarcode();
          if (result) {
            this._handleScanSuccess(result, onSuccess);
          }
          return; // Thoát vì đã dùng scanner của App
        } catch (mobileError) {
          console.warn("Lỗi quét bằng App Odoo, chuyển sang quét bằng trình duyệt:", mobileError);
        }
      }

      // 2. Chạy quét bằng Trình duyệt (HTML5Qrcode) - Yêu cầu HTTPS
      if (!window.isSecureContext && window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        throw new Error("Android yêu cầu kết nối HTTPS để bật Camera. Hãy kiểm tra lại địa chỉ web.");
      }

      this.stopScanning()
      this.isScanning = true

      // Đảm bảo phần tử hiển thị camera sẵn sàng
      const readerEl = document.getElementById("reader")
      if (readerEl) {
        readerEl.classList.remove("d-none")
      }

      const scanner = new Html5Qrcode("reader")
      const config = {
        fps: 20,
        qrbox: { width: 250, height: 250 },
        aspectRatio: 1.0
      }

      try {
        // Thử bật camera sau (environment)
        await scanner.start(
          { facingMode: "environment" },
          config,
          (data) => this._handleScanSuccess(data, onSuccess),
          (err) => this._handleScanError(err, onError),
        )
      } catch (e) {
        console.warn("Camera sau lỗi, thử chế độ mặc định:", e);
        await scanner.start(
          { facingMode: "user" },
          config,
          (data) => this._handleScanSuccess(data, onSuccess),
          (err) => this._handleScanError(err, onError),
        )
      }

      this.qrScanner = scanner
    } catch (error) {
      this.isScanning = false
      let errMsg = error.message;
      if (error.name === "NotAllowedError") errMsg = "Bạn đã chặn quyền Camera trong trình duyệt.";
      if (error.name === "NotFoundError") errMsg = "Không tìm thấy thiết bị Camera.";

      if (onError) onError("Lỗi: " + errMsg)
    }
  }

  /**
   * Dừng quét QR
   */
  async stopScanning() {
    if (this.qrScanner && this.isScanning) {
      try {
        await this.qrScanner.stop()
        this.qrScanner = null
        this.isScanning = false

        // Tìm reader element trong DOM
        const readerEl = document.getElementById("reader")
        if (readerEl) {
          readerEl.classList.remove("d-none")
        }
      } catch (err) {
        console.error("Lỗi dừng quét:", err)
        this.qrScanner = null
        this.isScanning = false
      }
    }
  }

  /**
   * Xử lý khi quét QR thành công
   */
  _handleScanSuccess(data, onSuccess) {
    const qrInfo = this._parseQRData(data)

    if (qrInfo.isValid) {
      this.stopScanning()
      const readerEl = document.getElementById("reader")
      if (readerEl) {
        readerEl.classList.add("d-none")
      }

      if (onSuccess) {
        onSuccess(qrInfo)
      }
    } else {
      if (onSuccess) {
        onSuccess({ isValid: false, error: "Mã QR không hợp lệ!" })
      }
    }
  }

  /**
   * Xử lý lỗi quét QR
   */
  _handleScanError(err, onError) {
    console.warn("QR Scan Error:", err)
    // Không cần xử lý gì đặc biệt cho lỗi quét thông thường
  }

  /**
   * Parse dữ liệu QR và trả về thông tin model
   */
  _parseQRData(data) {
    try {
      const content = (data || '').trim()

      // New compact format: id.code (no ':')
      if (content.includes('.') && !content.includes(':')) {
        const [idPart, codePart] = content.split('.', 1).concat(content.split('.').slice(1).join('.'))
        const recordId = Number.parseInt(idPart)
        const code = Number.parseInt(codePart)
        const codeMap = { 1: 'stock.picking', 2: 'stock.location' }
        const model = codeMap[code]
        if (!Number.isNaN(recordId) && model) {
          return {
            isValid: true,
            model,
            recordId,
            rawData: data,
            parsedData: { ID: String(recordId), ModelCode: String(code) },
          }
        }
        return { isValid: false, error: 'Mã QR không hợp lệ (định dạng id.code)!' }
      }

      // Backward compatibility: key-value pairs separated by new lines
      const keyValuePairs = content.split("\n")
      const scannedData = {}
      for (const pair of keyValuePairs) {
        const [key, value] = pair.split(":")
        if (key && value) {
          scannedData[key.trim()] = value.trim()
        }
      }

      if (!Object.prototype.hasOwnProperty.call(scannedData, 'Model')) {
        return { isValid: false, error: "QR không chứa thông tin model" }
      }

      const model = scannedData.Model
      const recordId = scannedData.ID ? Number.parseInt(scannedData.ID) : null

      return {
        isValid: true,
        model,                  // vd: "stock.picking", "stock.location"
        recordId,               // nếu không có ID sẽ = null
        rawData: data,
        parsedData: scannedData,       // giữ nguyên các key-value parse được
      }
    } catch (error) {
      return { isValid: false, error: "Lỗi parse dữ liệu QR: " + error.message }
    }
  }
}

QRScanner.template = `
    <div class="qr-scanner-container">
        <div class="qr-reader-container">
            <div id="reader" style="width: 100%;"></div>
        </div>
    </div>
`
