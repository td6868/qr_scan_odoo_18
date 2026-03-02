# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderConfirmInherit(models.TransientModel):
    _inherit = "sale.order.confirm.kk"

    shipping_carrier_company_id = fields.Many2one(
        'shipping.carrier.company',
        string="Nhà xe",
        help="Chọn nhà xe khi phương thức vận chuyển là Xe tải / Xe bus"
    )

    shipping_method_name = fields.Char(related='shipping_method.name', readonly=True)
    
    shipping_route_id = fields.Many2one(
        'shipping.route',
        string='Tuyến đường',
        domain="[('company_ids', '=', shipping_carrier_company_id)]",
        help='Tuyến đường vận chuyển'
    )

    demo_bus_company = fields.Text(string="Thông tin gửi xe")

    def action_sale_order_confirm_info(self, so):
        """Override để lưu thông tin nhà xe vào sale order"""
        res = super(SaleOrderConfirmInherit, self).action_sale_order_confirm_info(so)
        
        # Lưu vào sale order trước
        write_vals = {}
        # if self.shipping_carrier_company_id:
        #     write_vals.update({
        #         'shipping_carrier_company_id': self.shipping_carrier_company_id.id,
        #         'shipping_route_id': self.shipping_route_id.id if self.shipping_route_id else False
        #     })
        if self.demo_bus_company:
            write_vals['demo_bus_company'] = self.demo_bus_company
            
        if write_vals:
            so.write(write_vals)
        return res
    
    @api.onchange('shipping_carrier_company_id')
    def _onchange_shipping_carrier_company_id(self):
        self.shipping_route_id = False

    def action_sale_order_confirm(self):
        """Override chính: Cập nhật nhà xe và tuyến đường vào Picking SAU KHI confirm đơn hàng"""
        # 1. Lấy sale order liên quan
        so = self.get_info_so_id()
        
        # 2. Chạy logic confirm mặc định (để tạo ra các bản ghi picking_ids)
        res = super(SaleOrderConfirmInherit, self).action_sale_order_confirm()
        
        # 3. Sau khi confirm, picking_ids đã được tạo, tiến hành cập nhật trực tiếp vào picking
        # if self.shipping_carrier_company_id:
        #     for picking in so.picking_ids:
        #         picking.write({
        #             'shipping_carrier_company_id': self.shipping_carrier_company_id.id,
        #             'shipping_route_id': self.shipping_route_id.id if self.shipping_route_id else False
        #         })
        if self.demo_bus_company:
            for picking in so.picking_ids:
                picking.write({
                    'demo_bus_company': self.demo_bus_company
                })
        
        return res
