/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useRef, onMounted, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class StockPickingQrScanner extends Component {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.result = useRef("result");
        this.reader = useRef("reader");
        this.video = useRef("video");
        this.camera = useRef("camera");
        this.scanNote = useRef("scanNote");
        this.shippingNote = useRef("shippingNote");
        this.shippingPhone = useRef("shippingPhone");
        this.shippingCompany = useRef("shippingCom");
        this.productList = useRef("productList");
        // Thêm các ref mới cho file input
        this.fileInput = useRef("fileInput");
        this.shippingFileInput = useRef("shippingFileInput");
        
        this.orm = useService("orm");
        
        try {
            this.notification = useService("notification");
        } catch (e) {
            console.warn("Notification service không khả dụng:", e);
            this.notification = null;
        }
        
        this.model = "stock.picking";
        this.scanModel = "stock.picking.scan";
        this.state = useState({
            // Mode management
            showModeSelector: true,
            scanMode: null, // 'prepare' hoặc 'shipping'

            // Thêm các state cho việc chọn phương thức
            captureMethod: null,
            shippingCaptureMethod: null,

            isScanning: false,
            qrScanner: null,
            
            // Prepare mode states (existing)
            showCaptureArea: false,
            showNoteArea: false,
            showProductConfirmArea: false,
            capturedImages: [],
            currentImageIndex: 0,
            scanNoteValue: '',
            moveLines: [],
            
            // Shipping mode states (new)
            showShippingTypeArea: false,
            showShippingCaptureArea: false,
            showShippingNoteArea: false,
            selectedShippingType: null,
            shippingCapturedImages: [],
            shippingCurrentImageIndex:0,
            shippingPhone: '',
            shippingCompany: '',
            
            // Common states
            scannedPickingId: null,
            scannedPickingName: null,
        });

        // Thêm handlers mới
        this.onCaptureMethodChange = (method) => {
            this.state.captureMethod = method;
        };

        this.onShippingCaptureMethodChange = (method) => {
            this.state.shippingCaptureMethod = method;
        };

        this.onFileSelected = (ev) => {
            const file = ev.target.files[0];
            if (file) {
                this.handleFileUpload(file, 'prepare');
            }
        };

        this.onShippingFileSelected = (ev) => {
            const file = ev.target.files[0];
            if (file) {
                this.handleFileUpload(file, 'shipping');
            }
        };

        // Thêm handler cho scan note
        this.onScanNoteInput = (ev) => {
            this.state.scanNoteValue = ev.target.value;
        };
                
        // Existing handlers
        this.onConfirmQuantityInput = (ev, index) => {
            const value = parseFloat(ev.target.value) || 0;
            this.updateProductConfirm(index, "quantity_confirmed", value);
        };

        // this.onConfirmCheckboxChange = (ev, index) => {
        //     this.updateProductConfirm(index, "is_confirmed", ev.target.checked);
        // };

        this.onConfirmNoteInput = (ev, index) => {
            this.updateProductConfirm(index, "confirm_note", ev.target.value);
        };

        // New shipping handlers
        this.onShippingTypeChange = (ev) => {
            this.state.selectedShippingType = ev.target.value;
        };

        this.onShippingPhoneInput = (ev) => {
            this.state.shippingPhone = ev.target.value;
        };

        this.onShippingCompanyInput = (ev) => {
            this.state.shippingCompany = ev.target.value;
        };

        onMounted(() => {
            // Không load scanner ngay, đợi user chọn mode
        });
    }

    // ===== MODE MANAGEMENT =====
    setScanMode(mode) {
        this.state.scanMode = mode;
        this.state.showModeSelector = false;
        // Thêm delay để đảm bảo DOM đã update
        setTimeout(() => {
            this.loadQrCodeScanner();
        }, 100);
    }

    // Cập nhật resetMode để sử dụng async version
    async resetMode() {
        // Dừng QR scanner trước khi reset và chờ hoàn thành
        await this.stopQrCodeScannerAsync();

        // Reset tất cả states
        this.state.showModeSelector = true;
        this.state.scanMode = null;
        this.state.showCaptureArea = false;
        this.state.showNoteArea = false;
        this.state.showProductConfirmArea = false;
        this.state.showShippingTypeArea = false;
        this.state.showShippingCaptureArea = false;
        this.state.showShippingNoteArea = false;
        this.state.capturedImages = [];
        this.state.currentImageIndex = -1;
        this.state.shippingCapturedImages = [];
        this.state.shippingCurrentImageIndex = -1;
        this.state.scannedPickingId = null;
        this.state.scannedPickingName = null;
        this.state.selectedShippingType = null;
        this.state.shippingPhone = '';
        this.state.shippingCompany = '';
        this.state.moveLines = [];
        this.state.captureMethod = null;
        this.state.shippingCaptureMethod = null;
        
        // Clear result area
        if (this.result.el) {
            this.result.el.innerHTML = '';
        }
        
        // Show reader again
        if (this.reader.el) {
            this.reader.el.classList.remove('d-none');
        }
        
        // Stop camera if running
        if (this.videoStream) {
            this.videoStream.getTracks().forEach(track => track.stop());
            this.videoStream = null;
        }

        // Reset file inputs
        if (this.fileInput.el) {
            this.fileInput.el.value = '';
        }
        if (this.shippingFileInput.el) {
            this.shippingFileInput.el.value = '';
        }
    }

    // ===== UTILITY METHODS =====
    _showNotification(message, type = "info") {
        if (this.notification) {
            this.notification.add(message, { type: type });
        } else {
            if (type === "danger") {
                alert("Lỗi: " + message);
            } else {
                alert(message);
            }
        }
    }
    
    _showError(message) {
        const errorMessage = document.createElement('div');
        errorMessage.innerHTML = `
            <div class="alert alert-danger">
                <h4><i class="fa fa-exclamation-circle me-2"></i>Lỗi!</h4>
                <p>${message}</p>
            </div>
        `;
        this.result.el.innerHTML = '';
        this.result.el.appendChild(errorMessage);
        
        const retryButton = document.createElement('button');
        retryButton.className = 'btn btn-primary mt-3';
        retryButton.innerHTML = '<i class="fa fa-refresh me-2"></i>Thử lại';
        retryButton.addEventListener('click', () => {
            this.resetMode();
        });
        this.result.el.appendChild(retryButton);
    }

    //kiểm tra file ảnh 
    handleFileUpload(file, mode) {
        // Kiểm tra loại file
        if (!file.type.startsWith('image/')) {
            this._showNotification("Vui lòng chọn file ảnh!", "warning");
            return;
        }
        
        // Kiểm tra kích thước file (ví dụ: max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            this._showNotification("File ảnh quá lớn! Vui lòng chọn file nhỏ hơn 5MB.", "warning");
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            const imageDataUrl = e.target.result;
            const timestamp = new Date().toLocaleString('vi-VN');
            const imageObj = {
                data: imageDataUrl,
                name: `Upload_${file.name}_${timestamp}`,
                timestamp: timestamp,
                id: Date.now()
            };
            
            if (mode === 'prepare') {
                this.state.capturedImages.push(imageObj);
                this.state.currentImageIndex = this.state.capturedImages.length - 1;
            } else if (mode === 'shipping') {
                this.state.shippingCapturedImages.push(imageObj);
                this.state.shippingCurrentImageIndex = this.state.shippingCapturedImages.length - 1;
            }
            
            this._showNotification(`Đã thêm ảnh thứ ${this.state.capturedImages.length}!`, "success");
        };
        reader.readAsDataURL(file);
    }

    // ===== QR SCANNER =====
    loadQrCodeScanner() {
        // Dừng scanner cũ nếu đang chạy
        this.stopQrCodeScanner();
        this.state.isScanning = true;

        const self = this;
        // const scanner = new Html5QrcodeScanner('reader', {
        //     qrbox: {
        //         width: 250,
        //         height: 250,
        //     },
        //     fps: 20,
        //     cameraIdOrConfig: { facingMode: { exact: "environment" } }
        // });
        const scanner = new Html5Qrcode("reader");
        const config = { fps: 20, qrbox: { width: 250, height: 250 } };
        scanner.start(
            { facingMode: "environment" },
            config,
            success, error
        )
        // Lưu reference scanner
        this.state.qrScanner = scanner;

        // scanner.render(success, error);
        
        async function success(data) {
            const keyValuePairs = data.split('\n');
            const scannedData = {};
            for (const pair of keyValuePairs) {
                const [key, value] = pair.split(':');
                if (key && value) {
                    const trimmedKey = key.trim();
                    const trimmedValue = value.trim();
                    scannedData[trimmedKey] = trimmedValue;
                }
            }
            
            if (scannedData.hasOwnProperty('Picking') && scannedData.hasOwnProperty('ID')) {
                self.stopQrCodeScanner();
                self.reader.el.classList.add('d-none');
                
                const pickingId = parseInt(scannedData['ID']);
                const domain = [['id', '=', pickingId]];
                
                try {
                    const picking = await self.orm.call(self.model, 'search_read', [domain]);
                    if (picking.length === 0) {
                        self._showError("Không tìm thấy phiếu xuất kho!");
                    } else {
                        self._showSuccess(picking[0], data);
                    }
                } catch (error) {
                    self._showError("Lỗi khi tìm kiếm phiếu xuất kho: " + error);
                }
            } else {
                self._showError("Mã QR không hợp lệ! Không tìm thấy thông tin phiếu xuất kho.");
                self.stopQrCodeScanner();
                self.reader.el.classList.add('d-none');
            }
        }

        function error(err) {
            console.warn(err);
        }
    }

    //Html5QRcodescanner
    // stopQrCodeScanner() {
    //     if (this.state.qrScanner && this.state.isScanning) {
    //         try {
    //             this.state.qrScanner.clear();
    //             this.state.qrScanner = null;
    //             this.state.isScanning = false;
    //             console.log("QR Scanner stopped successfully");
    //         } catch (err) {
    //             console.error("Error stopping QR scanner:", err);
    //             this.state.isScanning = false;
    //         }
    //     }
    // }

    //Html5QRcode
    stopQrCodeScanner() {
        if (this.state.qrScanner && this.state.isScanning) {
            try {
                // Sử dụng stop() thay vì clear() cho Html5Qrcode
                this.state.qrScanner.stop().then(() => {
                    console.log("QR Scanner stopped successfully");
                    this.state.qrScanner = null;
                    this.state.isScanning = false;
                    
                    // Đảm bảo reader element được hiển thị lại
                    if (this.reader.el) {
                        this.reader.el.classList.remove('d-none');
                    }
                }).catch(err => {
                    console.error("Error stopping QR scanner:", err);
                    this.state.qrScanner = null;
                    this.state.isScanning = false;
                    
                    // Vẫn hiển thị lại reader element ngay cả khi có lỗi
                    if (this.reader.el) {
                        this.reader.el.classList.remove('d-none');
                    }
                });
            } catch (err) {
                console.error("Error stopping QR scanner:", err);
                this.state.qrScanner = null;
                this.state.isScanning = false;
                
                // Đảm bảo reader element được hiển thị lại
                if (this.reader.el) {
                    this.reader.el.classList.remove('d-none');
                }
            }
        }
    }

    // Phương thức async để dừng scanner và chờ hoàn thành
    async stopQrCodeScannerAsync() {
        if (this.state.qrScanner && this.state.isScanning) {
            try {
                await this.state.qrScanner.stop();
                console.log("QR Scanner stopped successfully");
                this.state.qrScanner = null;
                this.state.isScanning = false;
                
                // Đảm bảo reader element được hiển thị lại
                if (this.reader.el) {
                    this.reader.el.classList.remove('d-none');
                }
            } catch (err) {
                console.error("Error stopping QR scanner:", err);
                this.state.qrScanner = null;
                this.state.isScanning = false;
                
                // Vẫn hiển thị lại reader element ngay cả khi có lỗi
                if (this.reader.el) {
                    this.reader.el.classList.remove('d-none');
                }
            }
        }
    }
    
    _showSuccess(picking, data) {
        const successMessage = document.createElement('div');
        
        if (this.state.scanMode === 'prepare') {
            // PREPARE MODE LOGIC
            if (picking.state === 'done' || picking.state === 'cancel') {
                this._showError(`Không thể quét QR cho phiếu có trạng thái '${picking.state}'!`);
                return;
            }
            
            successMessage.innerHTML = `
                <div class="alert alert-success">
                    <h4><i class="fa fa-check-circle me-2"></i>Quét thành công - Chế độ chuẩn bị hàng!</h4>
                    <p><strong>Phiếu xuất kho:</strong> ${picking.name}</p>
                    <p><strong>Khách hàng:</strong> ${picking.partner_id[1] || 'N/A'}</p>
                    <p><strong>Ngày:</strong> ${picking.scheduled_date || 'N/A'}</p>
                </div>
            `;
            this.result.el.innerHTML = '';
            this.result.el.appendChild(successMessage);
            
            this.state.scannedPickingId = picking.id;
            this.state.scannedPickingName = picking.name;
            this.state.showCaptureArea = true;
            
            this._loadMoveLines(picking.id);
            
        } else if (this.state.scanMode === 'shipping') {
            // SHIPPING MODE LOGIC
            if (!picking.is_scanned) {
                this._showError("Phiếu xuất kho này chưa được quét QR và chụp ảnh chứng minh!");
                return;
            }
            if (picking.is_shipped) {
                this._showError("Phiếu xuất kho này đã được vận chuyển rồi!");
                return;
            }
            
            successMessage.innerHTML = `
                <div class="alert alert-success">
                    <h4><i class="fa fa-truck me-2"></i>Quét thành công - Chế độ vận chuyển!</h4>
                    <p><strong>Phiếu xuất kho:</strong> ${picking.name}</p>
                    <p><strong>Khách hàng:</strong> ${picking.partner_id[1] || 'N/A'}</p>
                    <p><strong>Ngày:</strong> ${picking.scheduled_date || 'N/A'}</p>
                    <p><strong>Trạng thái:</strong> <span class="badge bg-info">Đã chuẩn bị hàng</span></p>
                </div>
            `;
            this.result.el.innerHTML = '';
            this.result.el.appendChild(successMessage);
            
            this.state.scannedPickingId = picking.id;
            this.state.scannedPickingName = picking.name;
            this.state.showShippingTypeArea = true;
        }
    }

    // ===== PREPARE MODE METHODS (existing) =====
    startCamera() {
        this._initCamera();
    }
    
    _initCamera() {
        if (!this.video.el) {
            console.error("Không tìm thấy element video");
            this._showNotification("Không tìm thấy element video. Vui lòng tải lại trang.", "danger");
            return;
        }
        
        const constraints = {
            video: { facingMode: "environment" },
            audio: false
        };
        
        this._showNotification("Đang khởi tạo camera...", "info");
        
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            const msg = "Trình duyệt của bạn không hỗ trợ truy cập camera";
            console.error(msg);
            this._showNotification(msg, "danger");
            return;
        }
        
        navigator.mediaDevices.getUserMedia(constraints)
            .then(stream => {
                this.videoStream = stream;
                this.video.el.srcObject = stream;
                this.video.el.onloadedmetadata = () => {
                    this.video.el.play();
                    this._showNotification("Camera đã sẵn sàng!", "success");
                };
            })
            .catch(err => {
                console.error("Lỗi khi khởi tạo camera: ", err);
                this._showNotification("Không thể khởi tạo camera: " + err.message + ". Vui lòng cấp quyền truy cập camera và tải lại trang.", "danger");
            });
    }
    
    captureImage() {
        if (!this.video.el) {
            this._showNotification("Không tìm thấy element video. Vui lòng tải lại trang.", "danger");
            return;
        }

        if (!this.video.el.srcObject) {
            this._showNotification("Camera chưa sẵn sàng! Vui lòng bấm 'Bật camera' trước.", "warning");
            return;
        }

        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        const videoWidth = this.video.el.videoWidth;
        const videoHeight = this.video.el.videoHeight;

        if (!videoWidth || !videoHeight) {
            this._showNotification("Video chưa sẵn sàng. Vui lòng đợi giây lát và thử lại.", "warning");
            return;
        }

        canvas.width = videoWidth;
        canvas.height = videoHeight;
        context.drawImage(this.video.el, 0, 0, videoWidth, videoHeight);
        const imageDataUrl = canvas.toDataURL('image/jpeg', 0.8);
    
        const timestamp = new Date().toLocaleString('vi-VN');
        const imageObj = {
            data: imageDataUrl,
            name: `Image_${timestamp}`,
            timestamp: timestamp,
            id: Date.now() // unique id
        };
        
        if (this.state.scanMode === 'prepare') {
            this.state.capturedImages.push(imageObj);
            this.state.currentImageIndex = this.state.capturedImages.length - 1;
        } else if (this.state.scanMode === 'shipping') {
            this.state.shippingCapturedImages.push(imageObj);
            this.state.shippingCurrentImageIndex = this.state.shippingCapturedImages.length - 1;
        }
        
        this._showNotification(`Đã chụp ảnh thứ ${this.state.capturedImages.length}!`, "success");
    }

    removeImage(index, mode) {
        if (mode === 'prepare') {
            if (index >= 0 && index < this.state.capturedImages.length) {
                this.state.capturedImages.splice(index, 1);
                // Điều chỉnh currentImageIndex
                if (this.state.currentImageIndex >= this.state.capturedImages.length) {
                    this.state.currentImageIndex = Math.max(0, this.state.capturedImages.length - 1);
                }
            }
        }
        if (mode == 'shipping'){
            if (index >= 0 && index < this.state.shippingCapturedImages.length) {
                this.state.shippingCapturedImages.splice(index, 1);
                // Điều chỉnh currentImageIndex
                if (this.state.shippingCurrentImageIndex >= this.state.shippingCapturedImages.length) {
                    this.state.shippingCurrentImageIndex = Math.max(0, this.state.shippingCurrentImageIndex.length - 1);
                }
            }
        }
        this._showNotification("Đã xóa ảnh!", "success");
    }


    viewImage(index, mode) {
        if (mode == 'prepare'){
            this.state.currentImageIndex = index;
        }
        else if (mode == 'shipping'){
            this.state.shippingCurrentImageIndex = index;
        }
        
    }

    addMoreImages() {
        // Reset capture method để cho phép chụp/upload thêm
        if (this.state.scanMode === 'prepare') {
            this.state.captureMethod = null;
        } else if (this.state.scanMode === 'shipping') {
            this.state.shippingCaptureMethod = null;
        }
    }
    
    retakeImage() {
        if (this.state.scanMode === 'prepare') {
            this.state.capturedImages = [];
            // Reset file input
            if (this.fileInput.el) {
                this.fileInput.el.value = '';
            }
        } else if (this.state.scanMode === 'shipping') {
            this.state.shippingCapturedImages = null;
            // Reset file input
            if (this.shippingFileInput.el) {
                this.shippingFileInput.el.value = '';
            }
        }
    }
    
    saveImages() {
        if (this.state.scanMode === 'prepare' && this.state.capturedImages.length === 0) {
            this._showNotification("Vui lòng chụp ít nhất 1 ảnh!", "warning");
            return;
        }

        if (this.state.scanMode === 'shipping' && this.state.shippingCapturedImages.length === 0) {
            this._showNotification("Vui lòng chụp ít nhất 1 ảnh!", "warning");
            return;
        }
        
        if (this.state.scanMode === 'prepare') {
            this.state.showCaptureArea = false;
            this.state.showNoteArea = true;
        } else if (this.state.scanMode === 'shipping') {
            this.state.showShippingCaptureArea = false;
            this.state.showShippingNoteArea = true;
        }
    }

    // saveImage() {
    //     this.state.showShippingCaptureArea = false;
    //     this.state.showShippingNoteArea = true;
    // }
    
    async _loadMoveLines(pickingId) {
        try {
            // Thay đổi: lấy dữ liệu từ stock.move thay vì stock.move.line
            const domain = [["picking_id", "=", pickingId]];
            const fields = [
                "product_id",
                "product_uom", 
                "product_uom_qty",
                "picking_id",
                "name",
                "quantity",
            ];
            
            // Lấy tất cả stock.move của picking
            const moves = await this.orm.call("stock.move", "search_read", [domain, fields]);
            
            // Map dữ liệu cho giao diện - hiển thị TẤT CẢ sản phẩm
            this.state.moveLines = moves.map((move) => ({
                move_line_id: move.id, // Sử dụng move.id làm identifier
                move_id: move.id,      // Lưu move_id riêng
                product_id: move.product_id[0],
                product_name: move.product_id[1],
                quantity: move.product_uom_qty, // Số lượng nhu cầu
                uom: move.product_uom[1],
                // is_confirmed: false,
                quantity_confirmed: move.product_uom_qty,
                confirm_note: ""
            }));
                        
            console.log("Loaded moves:", this.state.moveLines);
            
        } catch (error) {
            console.error("Error loading moves:", error);
            this._showNotification("Lỗi khi tải danh sách sản phẩm: " + error, "danger");
        }
    }

    
    async saveScanData() {
        if (!this.state.scannedPickingId) {
            this._showNotification("Không tìm thấy thông tin phiếu xuất kho!", "danger");
            return;
        }
        
                   
        this._showNotification("Đã lưu thông tin quét QR và ảnh chụp thành công!", "success");
        
        this.state.showNoteArea = false;
        this.state.showProductConfirmArea = true;
        this.state.showCaptureArea = false;

        const note = this.state.scanNoteValue;
            
        
    }
    
    updateProductConfirm(index, field, value) {
        this.state.moveLines[index][field] = value;
    }
    
    async saveProductConfirm() {
        if (!this.state.scannedPickingId || this.state.moveLines.length === 0) {
            this._showNotification("Không có thông tin sản phẩm để xác nhận.", "danger");
            return;
        }
        this.dialogService.add(ConfirmationDialog, {
            title: "Xác nhận lưu",
            body: "Bạn có chắc chắn muốn lưu các thay đổi này không?",
            confirm: async () => {
            try {
                // Lưu thông tin QR và ảnh trước
                const imagesData = this.state.capturedImages.map((img, index) => ({
                    data: img.data.split(',')[1], // Remove data:image/jpeg;base64,
                    name: img.name,
                    description: `Ảnh minh chứng chuẩn bị hàng #${index + 1}`
                }));

                await this.orm.call(
                    this.model,
                    'update_scan_info',
                    [this.state.scannedPickingId],
                    {
                        images_data: imagesData,
                        scan_note: this.state.scanNoteValue,
                        move_line_confirms: this.state.moveLines,
                        scan_type: 'prepare'
                    }
                );
                
                // Sau đó mới lưu thông tin xác nhận sản phẩm
                // THAY ĐỔI: Loại bỏ tham số picking_id nếu dùng phiên bản đơn giản
                await this.orm.call(
                    this.model,
                    'update_move_line_confirm',
                    [[this.state.scannedPickingId], this.state.moveLines]
                );
                
                this._showNotification("Đã lưu tất cả thông tin thành công!", "success");
                
                if (this.videoStream) {
                    this.videoStream.getTracks().forEach(track => track.stop());
                }
                
                this.result.el.innerHTML = `
                    <div class="alert alert-success">
                        <h4><i class="fa fa-check-circle me-2"></i>Đã lưu thành công!</h4>
                        <p>Thông tin quét QR, ảnh chụp và xác nhận sản phẩm đã được lưu.</p>
                    </div>
                    <button class="btn btn-primary mt-3" id="newScanButton">
                        <i class="fa fa-qrcode me-2"></i>Quét mã QR mới
                    </button>
                `;
                
                this.state.showProductConfirmArea = false;

                document.getElementById('newScanButton').addEventListener('click', () => {
                    this.resetMode();
                });
                

            } catch (error) {
                console.error("Save product confirm error: ", error);
                this._showNotification("Lỗi khi lưu thông tin: " + error, "danger");
            }
        },
            cancel: () => {
                // Logic sẽ chạy khi người dùng nhấn "Cancel" hoặc đóng dialog
                console.log("Người dùng đã hủy bỏ.");
            },
        });
    }

    // ===== SHIPPING MODE METHODS (new) =====
    confirmShippingType() {
        if (!this.state.selectedShippingType) {
            this._showNotification("Vui lòng chọn loại vận chuyển!", "warning");
            return;
        }
        
        this.state.showShippingTypeArea = false;
        
        if (this.state.selectedShippingType === 'delivery') {
            // Nếu chọn "Đặt ship" thì cần chụp ảnh
            this.state.showShippingCaptureArea = true;
        } else {
            // Nếu chọn "Khách đến lấy hàng" thì chuyển thẳng đến ghi chú
            this.state.showShippingNoteArea = true;
        }
    }
    
    async saveShippingData() {
        if (!this.state.scannedPickingId) {
            this._showNotification("Không có thông tin phiếu xuất kho để lưu.", "danger");
            return;
        }
        
        const shippingNote = this.shippingNote.el.value;
        const shippingPhone = this.state.shippingPhone;      // THÊM MỚI
        const shippingCompany = this.state.shippingCompany;
        
        this.dialogService.add(ConfirmationDialog, {
            title: "Xác nhận lưu",
            body: "Bạn có chắc chắn muốn lưu các thay đổi này không?",
            confirm: async () => {
                try {           
                    const shippingImagesData = this.state.shippingCapturedImages.map((img, index) => ({
                        data: img.data.split(',')[1],
                        name: img.name,
                        description: `Ảnh vận chuyển #${index + 1}`
                    }));     
                    await this.orm.call(
                        this.model,               // 'stock.picking'
                        'update_scan_info',       // tên method
                        [[this.state.scannedPickingId]], // args: danh sách record id (self)
                        {
                            shipping_type: this.state.selectedShippingType,
                            images_data: shippingImagesData,
                            scan_note: shippingNote,
                            shipping_phone: shippingPhone,
                            shipping_company: shippingCompany,
                            scan_type: 'shipping',
                        }
                    );
                    
                    this._showNotification("Đã lưu thông tin vận chuyển thành công!", "success");
                    
                    if (this.videoStream) {
                        this.videoStream.getTracks().forEach(track => track.stop());
                    }
                    
                    const shippingTypeText = this.state.selectedShippingType === 'pickup' ? 'Khách đến lấy hàng' : 'Đặt ship';
                    this.result.el.innerHTML = `
                        <div class="alert alert-success">
                            <h4><i class="fa fa-check-circle me-2"></i>Đã lưu thành công!</h4>
                            <p>Thông tin vận chuyển đã được lưu.</p>
                            <p><strong>Loại vận chuyển:</strong> ${shippingTypeText}</p>
                            <p><strong>Phiếu xuất kho:</strong> ${this.state.scannedPickingName}</p>
                        </div>
                        <button class="btn btn-primary mt-3" id="newShippingScanButton">
                            <i class="fa fa-truck me-2"></i>Quét QR mới
                        </button>
                    `;
                    
                    this.state.showShippingNoteArea = false;
                    
                    document.getElementById('newShippingScanButton').addEventListener('click', () => {
                        this.resetMode();
                    });
                    
                } catch (error) {
                    console.error("Save shipping data error: ", error);
                    this._showNotification("Lỗi khi lưu thông tin vận chuyển: " + error, "danger");
                }
            },
            cancel: () => {
                // Logic sẽ chạy khi người dùng nhấn "Cancel" hoặc đóng dialog
                console.log("Người dùng đã hủy bỏ.");
            },
        });
    }
}

StockPickingQrScanner.template = "khoakim_18.StockPickingQrScanner";
registry.category("actions").add("stock_picking_qr_scanner_action", StockPickingQrScanner);