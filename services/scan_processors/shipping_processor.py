from odoo import models
from odoo.exceptions import ValidationError

class ShippingScanProcessor(models.TransientModel):
    _name = 'stock.picking.shipping.processor'
    _inherit = 'stock.picking.base.processor'
    _description = 'Shipping Scan Processor'

    def _get_scan_type(self):
        return 'shipping'

    def _supports_move_confirmations(self):
        return True

    def _get_specific_scan_vals(self, **kwargs):
        return {
            'shipping_type': kwargs.get('shipping_type'),
            'shipping_phone': kwargs.get('shipping_phone'),
            'shipping_company': kwargs.get('shipping_company'),
        }

    def _validate_scan_specific(self, picking, **kwargs):
        """Validate shipping scan specific rules"""
        if not kwargs.get('shipping_type'):
            raise ValidationError("Vui lòng chọn loại vận chuyển!")
        
        # Check if prepared first
        if not picking.scan_history_ids.filtered(lambda h: h.scan_type == 'prepare'):
            raise ValidationError("Phải chuẩn bị hàng trước khi vận chuyển!")