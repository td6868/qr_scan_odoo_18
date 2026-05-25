# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from markupsafe import Markup


class SaleOrderAssignTask(models.TransientModel):
    _name = 'sale.order.assign.task'
    _description = 'Wizard Giao Việc'

    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True)

    # Partner (auto-filled from sale order)
    partner_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        related='sale_order_id.partner_id',
        readonly=True,
    )

    # Picking policy - Mặc định KHÔNG CHỌN để sale phải xác nhận
    picking_policy = fields.Selection([
        ('direct', 'Càng sớm càng tốt'),
        ('one', 'Đi khi đủ hàng'),
    ], string='Chính sách giao hàng', required=True)

    # Shipping method - có thể thay đổi
    shipping_method_id = fields.Many2one(
        'delivery.carrier',
        string='Phương thức vận chuyển',
    )
    shipping_method_name = fields.Char(
        string='Tên phương thức VC',
        related='shipping_method_id.name',
        readonly=True,
    )
    
    # Loại vận chuyển (bao cước)
    type_shipping_cost = fields.Selection(
        selection=[
            ('1', 'Khách hàng trả phí'),
            ('2', 'Bao cước toàn bộ'),
            ('3', 'Bao cước một phần'),
        ],
        string='Loại vận chuyển',
        help='Thông tin bao cước để giao vận biết ai trả phí vận chuyển'
    )

    # Boolean để hiển thị section gửi xe
    is_bus_shipping = fields.Boolean(
        string='Là vận chuyển xe tải/xe bus',
        compute='_compute_is_bus_shipping',
    )

    # ========== Thông tin gửi xe ==========
    park_info = fields.Text(
        string='Thông tin gửi xe',
        help='Nhập Thông tin gửi xe: tên, SĐT, địa chỉ...'
    )

    # ========== Thông tin người nhận ==========
    recipient_phone = fields.Char('SĐT người nhận')
    recipient_name = fields.Char('Tên người nhận')
    recipient_address = fields.Text('Địa chỉ người nhận')

    # ========== Nhân viên kho phụ trách ==========
    wh_user_id = fields.Many2one(
        'res.users',
        string='NV kho',
        help='Nhân viên kho được sale chỉ định giao việc'
    )

    # ========== Shipping History ==========
    shipping_history_ids = fields.Many2many(
        'customer.shipping.history',
        compute='_compute_shipping_history',
        string='Lịch sử gửi xe'
    )
    shipping_history_count = fields.Integer(
        string='Số lần gửi xe',
        compute='_compute_shipping_history'
    )
    
    # Check xem đã giao việc trước đó chưa
    is_reassignment = fields.Boolean(
        string='Đã giao việc trước đó',
        compute='_compute_is_reassignment',
        help='True nếu đã giao việc cho picking này rồi'
    )
    
    # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
    # Uncomment các dòng sau khi cài đặt module 'shipping_carrier'
    # và thêm 'shipping_carrier' vào depends trong __manifest__.py
    # 
    # shipping_carrier_company_id = fields.Many2one(
    #     'shipping.carrier.company',
    #     string='Nhà xe',
    #     help='Chọn nhà xe vận chuyển'
    # )
    # 
    # shipping_route_id = fields.Many2one(
    #     'shipping.route',
    #     string='Tuyến đường',
    #     domain="[('company_ids', 'in', shipping_carrier_company_id)]",
    #     help='Chọn tuyến đường'
    # )
    # 
    # @api.onchange('shipping_carrier_company_id')
    # def _onchange_shipping_carrier(self):
    #     """Reset route khi đổi nhà xe và auto-fill park_info"""
    #     if self.shipping_carrier_company_id:
    #         # Auto-fill park_info từ thông tin nhà xe
    #         carrier = self.shipping_carrier_company_id
    #         self.park_info = f"{carrier.name}\nSĐT: {carrier.phone}\nĐịa chỉ: {carrier.address or ''}"
    #     else:
    #         self.shipping_route_id = False

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Auto-fill shipping method from sale order"""
        if self.sale_order_id and self.sale_order_id.shipping_method:
            self.shipping_method_id = self.sale_order_id.shipping_method
        if self.sale_order_id and self.sale_order_id.park_info:
            self.park_info = self.sale_order_id.park_info
        if self.sale_order_id and self.sale_order_id.type_shipping_cost:
            self.type_shipping_cost = self.sale_order_id.type_shipping_cost

    @api.depends('shipping_method_name')
    def _compute_is_bus_shipping(self):
        for rec in self:
            name = (rec.shipping_method_name or '').strip()
            rec.is_bus_shipping = 'Xe tải' in name or 'Xe bus' in name if name else False

    @api.depends('partner_id')
    def _compute_shipping_history(self):
        """Load shipping history for this customer"""
        for rec in self:
            if rec.partner_id:
                history = self.env['customer.shipping.history'].search([
                    ('partner_id', '=', rec.partner_id.id)
                ], limit=10, order='shipping_date desc')
                rec.shipping_history_ids = history
                rec.shipping_history_count = len(history)
            else:
                rec.shipping_history_ids = False
                rec.shipping_history_count = 0
    
    @api.depends('sale_order_id')
    def _compute_is_reassignment(self):
        """Check xem đã giao việc cho picking này trước đó chưa"""
        for rec in self:
            if rec.sale_order_id:
                # Kiểm tra xem có picking nào đã được giao việc chưa
                pickings = rec.sale_order_id.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel') and p.sale_assigned_date
                )
                rec.is_reassignment = bool(pickings)
            else:
                rec.is_reassignment = False

    def action_view_shipping_history(self):
        """Open shipping history for this customer"""
        self.ensure_one()
        return {
            'name': f'Lịch sử gửi xe - {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.shipping.history',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {'default_partner_id': self.partner_id.id},
            'target': 'new',
        }

    def action_confirm(self):
        """Xác nhận giao việc - cập nhật picking_policy và thông tin gửi xe"""
        self.ensure_one()
        so = self.sale_order_id

        if not self.picking_policy:
            raise ValidationError("Vui lòng chọn chính sách giao hàng!")

        # 1. Cập nhật picking_policy trên sale order
        so.picking_policy = self.picking_policy
        so.shipping_method = self.shipping_method_id
        if self.is_bus_shipping:
            so.park_info = self.park_info or False
            
            # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
            # Uncomment để lưu thông tin nhà xe vào sale order
            # if self.shipping_carrier_company_id:
            #     so.shipping_carrier_company_id = self.shipping_carrier_company_id
            # if self.shipping_route_id:
            #     so.shipping_route_id = self.shipping_route_id

        # 2. Cập nhật move_type trên các picking chưa hoàn thành
        pickings = so.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        if pickings:
            picking_vals = {
                'move_type': self.picking_policy,
                'shipping_method': self.shipping_method_id,
            }
            if self.type_shipping_cost:
                picking_vals['type_shipping_cost'] = self.type_shipping_cost
            if self.wh_user_id:
                picking_vals['wh_user_id'] = self.wh_user_id.id
            if self.is_bus_shipping:
                picking_vals['park_info'] = self.park_info or False
                
                # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
                # Uncomment để lưu thông tin nhà xe vào picking
                # if self.shipping_carrier_company_id:
                #     picking_vals['shipping_carrier_company_id'] = self.shipping_carrier_company_id.id
                # if self.shipping_route_id:
                #     picking_vals['shipping_route_id'] = self.shipping_route_id.id

            if self.recipient_name:
                recipient_text = self.recipient_name
                if self.recipient_phone:
                    recipient_text += f' - {self.recipient_phone}'
                picking_vals['recipient_info'] = recipient_text
                # Lưu riêng từng field để report dùng
                picking_vals['recipient_name'] = self.recipient_name
            if self.recipient_phone:
                picking_vals['recipient_phone'] = self.recipient_phone
            if self.recipient_address:
                picking_vals['recipient_address'] = self.recipient_address

            pickings.write(picking_vals)

        # 3. Nếu là xe tải/xe bus → lưu lịch sử gửi xe
        if self.is_bus_shipping and (self.park_info or self.recipient_name or self.recipient_phone or self.recipient_address):
            self._save_shipping_history(pickings)

        # 4. Cập nhật thông tin giao việc từ sale cho thủ kho
        if pickings:
            pickings.write({
                'sale_assigned_date': fields.Datetime.now(),
                'sale_assigned_user_id': self.env.uid,
                # KHÔNG reset warehouse_acknowledged để thủ kho không phải nhận việc lại
                # Chỉ update sale_assigned_date để trigger needs_recheck = True
            })

        # 5. Post message to chatter
        policy_label = dict(self._fields['picking_policy'].selection).get(self.picking_policy, '')
        shipping_method_label = self.shipping_method_id.name if self.shipping_method_id else 'Không có'

        message = f"""<p><strong>✅ Đã giao việc</strong></p>
        <ul>
            <li><strong>Chính sách giao hàng:</strong> {policy_label}</li>
            <li><strong>Phương thức vận chuyển:</strong> {shipping_method_label}</li>"""

        if self.is_bus_shipping and self.park_info:
            message += f"""
            <li><strong>Thông tin gửi xe:</strong> {self.park_info}</li>"""
        if self.recipient_name:
            message += f"""
            <li><strong>Người nhận:</strong> {self.recipient_name} - {self.recipient_phone or ''}</li>"""
        if self.wh_user_id:
            message += f"""
            <li><strong>NV kho phụ trách:</strong> {self.wh_user_id.name}</li>"""

        message += f"""
        </ul>
        <p><em>Người giao việc: {self.env.user.name}</em></p>"""

        so.message_post(
            body=Markup(message),
            subject='Giao việc',
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        return {'type': 'ir.actions.act_window_close'}

    def _save_shipping_history(self, pickings):
        """Save shipping history records"""
        self.ensure_one()
        for picking in pickings:
            history_vals = {
                'partner_id': self.partner_id.id,
                'park_info': self.park_info,
                'sale_order_id': self.sale_order_id.id,
                'picking_id': picking.id,
                'shipping_method_id': self.shipping_method_id.id,
                'recipient_name': self.recipient_name,
                'recipient_phone': self.recipient_phone,
                'recipient_address': self.recipient_address,
                'note': f'Giao việc từ wizard - Chính sách: {self.picking_policy}'
            }
            
            # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
            # Uncomment để lưu thông tin nhà xe vào lịch sử
            # if self.shipping_carrier_company_id:
            #     history_vals['shipping_carrier_company_id'] = self.shipping_carrier_company_id.id
            # if self.shipping_route_id:
            #     history_vals['shipping_route_id'] = self.shipping_route_id.id
            
            self.env['customer.shipping.history'].create(history_vals)
