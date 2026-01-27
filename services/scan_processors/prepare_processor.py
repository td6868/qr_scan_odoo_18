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
        """Validate prepare scan specific rules
        
        Raises:
            ValidationError: If validation fails with a user-friendly message
        """
        try:
            # Check if has move lines
            if not picking.move_line_ids:
                raise ValidationError("Không thể xác nhận: Phiếu này không có sản phẩm để chuẩn bị!")
            
            # Check user permission (only if we have a user in env - skip for auth='none')
            if self.env.user and not self.env.user.has_group('stock.group_stock_user'):
                raise ValidationError("Lỗi quyền truy cập: Bạn không có quyền thực hiện chức năng chuẩn bị hàng!")
                
        except ValidationError as ve:
            # Re-raise with the same message to be caught by the frontend
            raise ValidationError(str(ve))
        except Exception as e:
            # Catch any other exceptions and format them for the frontend
            error_msg = f"Lỗi xác thực: {str(e) or 'Đã xảy ra lỗi không xác định'}"
            raise ValidationError(error_msg)

    def _process_additional_data(self, scan_history, **kwargs):
        """After creating prepare scan history, mark picking as prepared.
        This enables the frontend and shipping processor to validate correctly.
        """
        super()._process_additional_data(scan_history, **kwargs)
        picking = scan_history.picking_id
        # Only set if not already prepared to avoid unnecessary writes
        if picking and not picking.is_prepared:
            picking.write({'is_prepared': True})
