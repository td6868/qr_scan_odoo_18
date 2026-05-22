from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO

class MultiModelQRService(models.TransientModel):
    _name = 'multi.model.qr.service'
    _description = 'QR Code Service for Multi Model'

    def generate_qr_for_record(self, record, model_name=None):
        """Generate QR code for any record"""
        if not model_name:
            model_name = record._name
        
        qr_data = self._build_qr_data(record, model_name)
        
        # Kiểm tra xem record có field qr_code_image và qr_code_data không
        if hasattr(record, 'qr_code_image') and hasattr(record, 'qr_code_data'):
            if not record.qr_code_image or record.qr_code_data != qr_data:
                record.qr_code_data = qr_data
                qr_image = self._create_qr_image(qr_data)
                record.qr_code_image = qr_image
        else:
            # Nếu model không có field QR, chỉ tạo và return image
            return self._create_qr_image(qr_data)

    def _build_qr_data(self, record, model_name):
        """Build compact QR data in format: '<id>.<code>'
        Model codes:
          stock.picking -> 1
          stock.location -> 2
        Unknown models -> code 0
        """
        model_code_map = {
            'stock.picking': 1,
            'stock.location': 2,
        }
        code = model_code_map.get(model_name, 0)
        # Ensure we return strictly: id.code
        # Với stock.location: sử dụng id_loc_qr thay vì id của record
        if model_name == 'stock.location':
            loc_id_for_qr = getattr(record, 'id_loc_qr', None) or record.id
            return f"{int(loc_id_for_qr)}.{code}"
        return f"{record.id}.{code}"
    
    # Các builder cũ không còn dùng nữa vì đã chuyển sang định dạng rút gọn
    # để giảm số lượng ký tự trong QR.
   
    def _create_qr_image(self, qr_data):
        """Create QR image from data"""
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue())
    

    def parse_qr_data(self, qr_content):
        """Parse compact QR content '<id>.<code>' and return model info.
        Backward compatible: if content contains 'Model:' style, try to parse it too.
        """
        content = (qr_content or '').strip()
        if not content:
            return {'model': None, 'record_id': None, 'is_valid': False}

        # New compact format: id.code
        if '.' in content and ':' not in content:
            try:
                id_part, code_part = content.split('.', 1)
                record_id = int(id_part)
                code = int(code_part)
                code_model_map = {
                    1: 'stock.picking',
                    2: 'stock.location',
                }
                model = code_model_map.get(code)
                return {
                    'model': model,
                    'record_id': record_id,
                    'is_valid': bool(model and record_id > 0),
                }
            except Exception:
                return {'model': None, 'record_id': None, 'is_valid': False}

        # Fallback old multiline format
        lines = content.split('\n')
        result = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip().lower()] = value.strip()

        model = result.get('model')
        rec_id = int(result.get('id', 0)) if result.get('id', '').isdigit() else None
        return {
            'model': model,
            'record_id': rec_id,
            'is_valid': bool(model in ('stock.picking', 'stock.location') and rec_id),
        }
