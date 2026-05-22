# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderConfirmInherit(models.TransientModel):
    _inherit = "sale.order.confirm.kk"

    park_info = fields.Text(
        string="Thông tin gửi xe",
        help="Thông tin gửi xe do sale tự nhập khi phương thức vận chuyển là Xe tải / Xe bus"
    )

    shipping_method_name = fields.Char(related='shipping_method.name', readonly=True)

    def action_sale_order_confirm_info(self, so):
        """Override để lưu thông tin gửi xe vào sale order"""
        res = super(SaleOrderConfirmInherit, self).action_sale_order_confirm_info(so)

        if self.park_info:
            so.write({'park_info': self.park_info})
        return res

    def action_sale_order_confirm(self):
        """Override chính: Cập nhật thông tin gửi xe và nhân viên sale vào Picking SAU KHI confirm đơn hàng"""
        so = self.get_info_so_id()
        res = super(SaleOrderConfirmInherit, self).action_sale_order_confirm()

        write_vals = {}
        if self.park_info:
            write_vals['park_info'] = self.park_info
        if so.user_id:
            write_vals['user_id'] = so.user_id.id

        if write_vals:
            for picking in so.picking_ids:
                picking.write(write_vals)

        return res
