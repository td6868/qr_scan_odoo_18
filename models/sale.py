from collections import defaultdict
from odoo import models, fields, api
from odoo.fields import Datetime

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
    

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # store=False: Luôn lấy dữ liệu mới nhất từ kho khi mở form
    # Hiệu suất tốt nhờ batch query (gom tất cả SP vào 1 query duy nhất)
    available_to_use = fields.Float(
        string="Tồn kho có thể sử dụng",
        compute="_compute_available_to_use",
        digits='Product Unit of Measure',
    )

    @api.depends('product_id', 'order_id.commitment_date', 'order_id.warehouse_id')
    def _compute_available_to_use(self):
        """
        Hiển thị tồn kho tự do (free_qty) tại kho + ngày giao hàng của đơn.
        - free_qty = On Hand - Reserved (đã giữ chỗ bởi các phiếu kho đang chờ)
        - Dùng batch query: 1 query cho tất cả sản phẩm trong cùng nhóm (warehouse, date)
        - Không trừ hao, không cộng ngược — hiển thị đúng thực tế kho tại thời điểm xem
        """
        # Bước 1: Gom nhóm theo (warehouse_id, scheduled_date)
        grouped_lines = defaultdict(lambda: self.env['sale.order.line'])
        for line in self:
            if not line.product_id:
                line.available_to_use = 0.0
                continue
            warehouse_id = line.order_id.warehouse_id.id or False
            scheduled_date = line.order_id.commitment_date or Datetime.now()
            grouped_lines[(warehouse_id, scheduled_date)] |= line

        # Bước 2: Batch query cho từng nhóm — 1 query cho tất cả sản phẩm
        for (warehouse_id, scheduled_date), lines in grouped_lines.items():
            ctx = {'to_date': scheduled_date}
            if warehouse_id:
                ctx['warehouse_id'] = warehouse_id

            products = lines.mapped('product_id')
            product_qties = products.with_context(**ctx).read(['free_qty'])
            qties_map = {p['id']: p['free_qty'] for p in product_qties}

            for line in lines:
                free_qty = qties_map.get(line.product_id.id, 0.0)

                # Quy đổi đơn vị sang UoM trên dòng để hiển thị đúng
                if line.product_uom and line.product_id.uom_id and line.product_uom != line.product_id.uom_id:
                    free_qty = line.product_id.uom_id._compute_quantity(free_qty, line.product_uom)

                line.available_to_use = free_qty