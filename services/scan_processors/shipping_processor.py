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
        """Validate shipping scan specific rules
        
        Note: Most validation is now done in API layer for early feedback.
        This is a safety net for direct model calls.
        """
        # Validate shipping type (skip if validate_only mode)
        if kwargs.get('shipping_type') != 'validate_only' and not kwargs.get('shipping_type'):
            raise ValidationError("Vui lòng chọn loại vận chuyển!")

    def _process_additional_data(self, scan_history, **kwargs):
        """Mark picking as shipped after processing"""
        super()._process_additional_data(scan_history, **kwargs)
        picking = scan_history.picking_id
        if picking and not picking.is_shipped:
            picking.write({'is_shipped': True})