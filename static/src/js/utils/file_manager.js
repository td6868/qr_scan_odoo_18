/**
 * File Manager - Quản lý upload file và xử lý ảnh
 */
export class FileManager {
  /**
   * Xử lý file được chọn
   */
  static async handleFileUpload(file) {
    return new Promise((resolve, reject) => {
      if (!file || !file.type.startsWith("image/")) {
        reject(new Error("Vui lòng chọn file ảnh hợp lệ"))
        return
      }

      const reader = new FileReader()
      reader.onload = (e) => {
        resolve({
          data: e.target.result,
          name: file.name,
          timestamp: new Date().toLocaleString(),
          id: Date.now(),
        })
      }
      reader.onerror = () => reject(new Error("Lỗi đọc file"))
      reader.readAsDataURL(file)
    })
  }

  /**
   * Chuyển đổi ảnh thành base64 để lưu vào database
   */
  static convertToBase64(imageData) {
    if (imageData.startsWith("data:image/")) {
      return imageData.split(",")[1]
    }
    return imageData
  }

  /**
   * Validate kích thước file
   */
  static validateFileSize(file, maxSizeMB = 5) {
    const maxSize = maxSizeMB * 1024 * 1024
    if (file.size > maxSize) {
      throw new Error(`File quá lớn. Kích thước tối đa: ${maxSizeMB}MB`)
    }
    return true
  }
}
