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
        # Kiểm tra trạng thái gửi xe
        if picking.ship_inf_state == 'none':
            raise ValidationError(f"⚠️ Phiếu {picking.name} không thuộc phương thức vận chuyển cần gửi xe (Xe tải/Xe bus, Grab)!")
        elif picking.ship_inf_state == 'received':
            raise ValidationError(f"⚠️ Phiếu {picking.name} đã được xác nhận gửi xe trước đó (Trạng thái: Đã nhận)!")
        elif picking.ship_inf_state == 'completed':
            raise ValidationError(f"⚠️ Phiếu {picking.name} đã hoàn thành giao hàng!")
        elif picking.ship_inf_state != 'not_received':
            raise ValidationError(f"⚠️ Phiếu {picking.name} không ở trạng thái 'Chưa nhận'!")

        # Validate shipping type (skip if validate_only mode)
        # if kwargs.get('shipping_type') != 'validate_only' and not kwargs.get('shipping_type'):
        #     raise ValidationError("Vui lòng chọn loại vận chuyển!")

    def _process_additional_data(self, scan_history, **kwargs):
        """Xử lý gửi xe: Đánh dấu đã nhận hàng gửi xe và ghi nhận thông tin"""
        super()._process_additional_data(scan_history, **kwargs)
        picking = scan_history.picking_id
        
        if picking and picking.ship_inf_state == 'not_received':
            # Thu thập data nâng cấp cho picking
            update_vals = {
                'ship_inf_state': 'received',
                'shipping_confirmed_by': self.env.user.id,
                'shipping_driver_phone': kwargs.get('shipping_driver_phone'),
                'shipping_vehicle_number': kwargs.get('shipping_vehicle_number'),
                'shipping_tracking_number': kwargs.get('shipping_tracking_number'),
            }
            
            picking.write(update_vals)
