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
      this.stopScanning()
      this.isScanning = true

      // Import Html5Qrcode dynamically để tránh lỗi
      // const { Html5Qrcode } = await import("html5-qrcode")
      const scanner = new Html5Qrcode("reader")
      const config = { fps: 20, qrbox: { width: 250, height: 250 } }

      await scanner.start(
        { facingMode: "environment" },
        config,
        (data) => this._handleScanSuccess(data, onSuccess),
        (err) => this._handleScanError(err, onError),
      )

      this.qrScanner = scanner
    } catch (error) {
      this.isScanning = false
      if (onError) onError("Không thể khởi động camera: " + error.message)
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
      const keyValuePairs = data.split("\n")
      const scannedData = {}

      for (const pair of keyValuePairs) {
        const [key, value] = pair.split(":")
        if (key && value) {
          scannedData[key.trim()] = value.trim()
        }
      }

      // Kiểm tra định dạng QR hợp lệ
      if (!scannedData.hasOwnProperty("Model") || !scannedData.hasOwnProperty("ID")) {
        return { isValid: false, error: "QR không chứa thông tin model hợp lệ" }
      }

      return {
        isValid: true,
        model: scannedData.Model,
        recordId: Number.parseInt(scannedData.ID),
        pickingName: scannedData.Picking,
        customerName: scannedData.Customer,
        date: scannedData.Date,
        rawData: data,
        parsedData: scannedData,
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
