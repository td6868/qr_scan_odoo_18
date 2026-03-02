from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    #add view image proof
    def action_view_image_proof(self):
        self.ensure_one()
        domain = [('picking_id.sale_id', '=', self.id)]
        image_proof_ids = self.env['stock.picking.scan.history'].search(domain)
        """Hiển thị ảnh chứng minh"""
        result = {
            'name': 'Ảnh chứng minh',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.scan.history',
            'domain': domain,
            'context': {'create': False},
        }          
        result.update({
            "view_mode": 'kanban,form',
            "domain": domain,
        })  
        return result

    shipping_carrier_company_id = fields.Many2one(
        'shipping.carrier.company',
        string='Nhà xe',
        tracking=True,
        help='Nhà xe vận chuyển hàng hóa'
    )

    demo_bus_company = fields.Text(string="Thông tin gửi xe")

    shipping_route_id = fields.Many2one(
        'shipping.route',
        string='Tuyến đường',
        domain="[('company_ids', '=', shipping_carrier_company_id)]",
        tracking=True,
        help='Tuyến đường vận chuyển hàng hóa'
    )
    
    # def _prepare_picking_values(self):
    #     """Kế thừa thông tin nhà xe xuống phiếu xuất kho"""
    #     res = super(SaleOrder, self)._prepare_picking_values()
    #     if self.shipping_carrier_company_id:
    #         res['shipping_carrier_company_id'] = self.shipping_carrier_company_id.id
    #     if self.shipping_route_id:
    #         res['shipping_route_id'] = self.shipping_route_id.id
    #     return res

    def _demo_bus_info_inherit(self):
        """Kế thừa thông tin nhà xe xuống phiếu xuất kho"""
        res = super(SaleOrder, self)._demo_bus_info_inherit()
        if self.demo_bus_company:
            res['demo_bus_company'] = self.demo_bus_company
        return res
    