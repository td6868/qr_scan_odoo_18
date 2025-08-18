from odoo import models
from odoo.exceptions import ValidationError

class ReceiveScanProcessor(models.TransientModel):
    _name = 'stock.picking.receive.processor'
    _inherit = 'stock.picking.base.processor'
    _description = 'Receive Scan Processor'

    def _get_scan_type(self):
        return 'receive'

    def _validate_scan_specific(self, picking, **kwargs):
        """Validate receive scan specific rules"""
        existing_scan = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'receive')
        if existing_scan:
            raise ValidationError("Phiếu nhập kho này đã được nhận hàng rồi!")
        
        # Check if it's incoming picking
        if picking.picking_type_id.code != 'incoming':
            raise ValidationError("Chỉ có thể nhận hàng cho phiếu nhập kho!")
