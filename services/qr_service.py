from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO

class StockPickingQRService(models.TransientModel):
    _name = 'stock.picking.qr.service'
    _description = 'QR Code Service for Stock Picking'

    def generate_qr_for_picking(self, picking):
        """Generate QR code for a picking"""
        qr_data = self._build_qr_data(picking)
        
        if not picking.qr_code_image or picking.qr_code_data != qr_data:
            picking.qr_code_data = qr_data
            qr_image = self._create_qr_image(qr_data)
            picking.qr_code_image = qr_image

    def _build_qr_data(self, picking):
        """Build QR data string"""
        qr_data = f"Model: stock.picking\n"
        qr_data += f"Picking: {picking.name}\n"
        qr_data += f"Customer: {picking.partner_id.name or 'N/A'}\n"
        qr_data += f"Date: {picking.scheduled_date}\n"
        qr_data += f"ID: {picking.id}\n"
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
