from odoo import models, fields
from odoo.exceptions import ValidationError

class ShippingScanProcessor(models.TransientModel):
    _name = 'stock.picking.shipping.processor'
    _inherit = 'stock.picking.base.processor'
    _description = 'Shipping Scan Processor - Xác nhận gửi xe'

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

    def _validate_record_state(self, picking):
        """Override: Shipping mode CHỈ cho phép quét khi picking đã 'done'"""
        # Chỉ chặn 'cancel', không chặn 'done'
        if picking.state == 'cancel':
            raise ValidationError(f"Không thể gửi xe phiếu đã bị hủy '{picking.name}'")
        # Không cần check 'done' vì shipping yêu cầu state = done

    def _validate_scan_specific(self, picking, **kwargs):
        """Validate shipping scan specific rules
        
        Note: Most validation is now done in API layer for early feedback.
        This is a safety net for direct model calls.
        """
        # Kiểm tra gửi xe 2 lần
        if picking.is_shipped:
            raise ValidationError(f"⚠️ Phiếu {picking.name} đã được xác nhận gửi xe rồi!\nKhông thể gửi xe lại, nhưng bạn vẫn có thể thêm chi phí.")

        # Validate shipping type (skip if validate_only mode)
        if kwargs.get('shipping_type') != 'validate_only' and not kwargs.get('shipping_type'):
            raise ValidationError("Vui lòng chọn loại vận chuyển!")

    def _process_additional_data(self, scan_history, **kwargs):
        """Xử lý gửi xe: Đánh dấu đã gửi xe và ghi nhận thông tin"""
        super()._process_additional_data(scan_history, **kwargs)
        picking = scan_history.picking_id
        
        if picking and not picking.is_shipped:
            # Thu thập data nâng cấp cho picking
            update_vals = {
                'is_shipped': True,
                'is_sent_to_carrier': True,
                'actual_shipping_date': fields.Datetime.now(),
                'shipping_confirmed_by': self.env.user.id,
                'shipping_driver_phone': kwargs.get('shipping_driver_phone'),
                'shipping_vehicle_number': kwargs.get('shipping_vehicle_number'),
                'shipping_tracking_number': kwargs.get('shipping_tracking_number'),
            }
            if kwargs.get('shipping_route_id'):
                update_vals['shipping_route_id'] = kwargs.get('shipping_route_id')
                
            picking.write(update_vals)