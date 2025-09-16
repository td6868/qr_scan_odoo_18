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
        """Build QR data string based on model type"""
        qr_builders = {
            'stock.picking': self._build_picking_qr_data,
            'stock.location': self._build_location_qr_data,
        }
        
        builder_func = qr_builders.get(model_name, self._build_generic_qr_data)
        return builder_func(record)
    
    def _build_picking_qr_data(self, picking):
        """Build QR data for stock picking"""
        qr_data = f"Model: stock.picking\n"
        # qr_data += f"Picking: {picking.name}\n"
        qr_data += f"ID: {picking.id}\n"
        return qr_data

    def _build_location_qr_data(self, location):
        """Build QR data for stock location"""
        qr_data = f"Model: stock.location\n"
        # qr_data += f"Name: {location.name}\n"
        qr_data += f"ID: {location.id}\n"
        return qr_data

    def _build_generic_qr_data(self, record):
        """Build generic QR data for any model"""
        qr_data = f"Model: {record._name}\n"
        
        # Tự động lấy các field phổ biến
        common_fields = ['name', 'display_name', 'id']
        
        for field_name in common_fields:
            if hasattr(record, field_name):
                value = getattr(record, field_name)
                if value:
                    qr_data += f"{field_name.title()}: {value}\n"
            
        return qr_data
   
    def _create_qr_image(self, qr_data):
        """Create QR image from data"""
        qr = qrcode.QRCode(
            version=3,
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
        """Parse QR content and return model info"""
        lines = qr_content.strip().split('\n')
        result = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip().lower()] = value.strip()
        
        return {
            'model': result.get('model'),
            'picking_name': result.get('picking'),
            'picking_id': int(result.get('id', 0)) if result.get('id', '').isdigit() else None,
            'customer': result.get('customer'),
            'date': result.get('date'),
            'is_valid': bool(result.get('model') == 'stock.picking' and result.get('id'))
        }
