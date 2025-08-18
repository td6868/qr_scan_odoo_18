from odoo import models
from odoo.exceptions import ValidationError

class PrepareScanProcessor(models.TransientModel):
    _name = 'stock.picking.prepare.processor'
    _inherit = 'stock.picking.base.processor'
    _description = 'Prepare Scan Processor'

    def _get_scan_type(self):
        return 'prepare'

    def _supports_move_confirmations(self):
        return True

    def _validate_scan_specific(self, picking, **kwargs):
        """Validate prepare scan specific rules"""        
        # Check if has move lines
        if not picking.move_line_ids:
            raise ValidationError("Phiếu này không có sản phẩm để chuẩn bị!")

        
        # Check user permission (optional)
        if not self.env.user.has_group('stock.group_stock_user'):
            raise ValidationError("Bạn không có quyền chuẩn bị hàng!")
