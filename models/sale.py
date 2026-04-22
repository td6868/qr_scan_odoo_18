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

    incoming_qty = fields.Float(
        string="SL sắp về",
        compute="_compute_available_to_use",
        digits='Product Unit of Measure',
    )

    latest_stock_increase_date = fields.Date(
        string="Ngày tăng tồn gần nhất",
        related='product_id.latest_stock_increase_date',
        readonly=True,
    )

    order_stock_move_qty = fields.Float(
        string="Tồn đơn hàng",
        compute="_compute_order_stock_move_qty",
        digits='Product Unit of Measure',
    )

    is_description_mismatch = fields.Boolean(
        string="Mô tả khác tên SP",
        compute="_compute_is_description_mismatch",
        store=True,
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
                line.incoming_qty = 0.0
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
            product_qties = products.with_context(**ctx).read(['free_qty', 'virtual_available', 'incoming_qty'])
            qties_map = {p['id']: (p['free_qty'], p['virtual_available'], p['incoming_qty']) for p in product_qties}

            for line in lines:
                free_qty, virtual_available, incoming = qties_map.get(line.product_id.id, (0.0, 0.0, 0.0))

                # Use the incoming_qty directly from product rather than calculating it
                # This addresses the issue of incorrect calculations when free_qty might be negative
                # or when the relationship between virtual_available and free_qty doesn't represent incoming stock

                # Quy đổi đơn vị sang UoM trên dòng để hiển thị đúng
                if line.product_uom and line.product_id.uom_id and line.product_uom != line.product_id.uom_id:
                    free_qty = line.product_id.uom_id._compute_quantity(free_qty, line.product_uom)
                    incoming = line.product_id.uom_id._compute_quantity(incoming, line.product_uom)

                line.available_to_use = free_qty
                line.incoming_qty = incoming

    def get_incoming_details(self):
        self.ensure_one()

        moves = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', 'in', ['confirmed', 'waiting', 'assigned']),
            ('location_dest_id.usage', '=', 'internal'),
        ], order='date asc')

        result = []
        for m in moves:
            result.append({
                'date': m.date.strftime('%d/%m/%Y') if m.date else '',
                'qty': m.product_uom_qty,
                'origin': m.origin or '',
            })

        return result

    @api.depends('state', 'product_id')
    def _compute_order_stock_move_qty(self):
        valid_lines = self.filtered(lambda l: l.state in ('sale', 'done') and l.product_id)
        others = self - valid_lines

        for l in others:
            l.order_stock_move_qty = 0.0

        if not valid_lines:
            return

        # tất cả sale lines trong các order
        all_lines = valid_lines.mapped('order_id.order_line')
        sale_line_ids = all_lines.ids

        if not sale_line_ids:
            return

        # SQL
        self.env.cr.execute("""
            SELECT 
                sol.order_id,
                sm.product_id,
                SUM(sml.quantity)
            FROM stock_move_line sml
            JOIN stock_move sm ON sml.move_id = sm.id
            JOIN sale_order_line sol ON sm.sale_line_id = sol.id
            WHERE sm.sale_line_id IN %s
            AND sm.state NOT IN ('cancel', 'done')
            AND sm.picking_type_id IN (
                SELECT id FROM stock_picking_type WHERE code = 'outgoing'
            )
            GROUP BY sol.order_id, sm.product_id
        """, [tuple(sale_line_ids)])

        rows = self.env.cr.fetchall()

        # map (order_id, product_id) -> qty
        result = {}
        for order_id, product_id, qty in rows:
            result[(order_id, product_id)] = qty

        # gán lại cho từng line
        for line in valid_lines:
            key = (line.order_id.id, line.product_id.id)
            line.order_stock_move_qty = result.get(key, 0.0)

    @api.depends('name', 'product_template_id', 'product_template_id.name', 'display_type')
    def _compute_is_description_mismatch(self):
        """
        Tối ưu hiệu suất:
        - Chỉ xử lý chuỗi tối thiểu cần thiết
        - Cache tên template đã normalize theo template_id trong cùng batch compute
        - Không gọi các method nặng của Odoo trong vòng lặp
        """
        def _normalize(text):
            return ' '.join((text or '').split()).casefold()

        def _clean_first_line(line_name):
            first = (line_name or '').split('\n', 1)[0].strip()
            # Bỏ tiền tố mã dạng [CODE] nếu có
            if first.startswith('['):
                close_idx = first.find(']')
                if close_idx > -1:
                    first = first[close_idx + 1:].strip()
            return _normalize(first)

        normalized_template_name_cache = {}

        for line in self:
            if line.display_type or not line.product_template_id:
                line.is_description_mismatch = False
                continue

            tmpl_id = line.product_template_id.id
            template_name_norm = normalized_template_name_cache.get(tmpl_id)
            if template_name_norm is None:
                template_name_norm = _normalize(line.product_template_id.display_name)
                normalized_template_name_cache[tmpl_id] = template_name_norm

            line_first_norm = _clean_first_line(line.name)

            # Không mismatch nếu:
            # - trùng tên template
            # - hoặc là mô tả variant mặc định: "template (attr1, attr2, ...)"
            line.is_description_mismatch = not (
                line_first_norm == template_name_norm
                or line_first_norm.startswith(f"{template_name_norm} (")
            )

    def _prepare_stock_move_vals(self):
        """
        Giữ lại để tương thích luồng tạo move hiện tại.
        """
        res = super(SaleOrderLine, self)._prepare_stock_move_vals()
        res['is_description_mismatch'] = self.is_description_mismatch
        return res


class StockMove(models.Model):
    _inherit = 'stock.move'

    is_description_mismatch = fields.Boolean(
        string="Mô tả khác tên SP",
        related='sale_line_id.is_description_mismatch',
        store=True,
        copy=False,
        readonly=True,
    )

    latest_stock_increase_date = fields.Date(
        string="Ngày tăng tồn gần nhất",
        related='product_id.latest_stock_increase_date',
        readonly=True,
    )