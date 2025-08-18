from odoo import models
from odoo.exceptions import ValidationError

class CheckingScanProcessor(models.TransientModel):
    _name = 'stock.picking.checking.processor'
    _inherit = 'stock.picking.base.processor'
    _description = 'Checking Scan Processor'

    def _get_scan_type(self):
        return 'checking'

    def _supports_move_confirmations(self):
        return True

    def _validate_scan_specific(self, picking, **kwargs):
        """Validate checking scan specific rules"""
        # existing_scan = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'checking')
        # if existing_scan:
        #     raise ValidationError("Phiếu nhập kho này đã được kiểm hàng rồi!")
        
        # Check if received first
        if not picking.scan_history_ids.filtered(lambda h: h.scan_type == 'receive'):
            raise ValidationError("Chỉ có thể kiểm hàng sau khi đã nhận hàng!")
