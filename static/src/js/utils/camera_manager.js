/**
 * Camera Manager - Quản lý camera và chụp ảnh
 */
export class CameraManager {
  constructor() {
    this.stream = null
    this.video = null
  }

  /**
   * Khởi động camera
   */
  async startCamera(videoElement) {
    try {
      this.video = videoElement
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      })
      this.video.srcObject = this.stream
      return true
    } catch (error) {
      console.error("Lỗi khởi động camera:", error)
      throw new Error("Không thể truy cập camera: " + error.message)
    }
  }

  /**
   * Chụp ảnh từ camera
   */
  captureImage() {
    if (!this.video || !this.stream) {
      throw new Error("Camera chưa được khởi động")
    }

    const canvas = document.createElement("canvas")
    const context = canvas.getContext("2d")

    canvas.width = this.video.videoWidth
    canvas.height = this.video.videoHeight

    context.drawImage(this.video, 0, 0)

    return {
      data: canvas.toDataURL("image/jpeg", 0.8),
      timestamp: new Date().toLocaleString(),
      id: Date.now(),
    }
  }

  /**
   * Dừng camera
   */
  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop())
      this.stream = null
    }
    if (this.video) {
      this.video.srcObject = null
      this.video = null
    }
  }
}
