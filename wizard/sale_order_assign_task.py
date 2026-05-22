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

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Auto-fill shipping method from sale order"""
        if self.sale_order_id and self.sale_order_id.shipping_method:
            self.shipping_method_id = self.sale_order_id.shipping_method
        if self.sale_order_id and self.sale_order_id.park_info:
            self.park_info = self.sale_order_id.park_info

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

        # 2. Cập nhật move_type trên các picking chưa hoàn thành
        pickings = so.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        if pickings:
            picking_vals = {
                'move_type': self.picking_policy,
                'shipping_method': self.shipping_method_id,
            }
            if self.is_bus_shipping:
                picking_vals['park_info'] = self.park_info or False

            if self.recipient_name:
                recipient_text = self.recipient_name
                if self.recipient_phone:
                    recipient_text += f' - {self.recipient_phone}'
                picking_vals['recipient_info'] = recipient_text

            pickings.write(picking_vals)

        # 3. Nếu là xe tải/xe bus → lưu lịch sử gửi xe
        if self.is_bus_shipping and (self.park_info or self.recipient_name or self.recipient_phone or self.recipient_address):
            self._save_shipping_history(pickings)

        # 4. Tạo bản ghi giao việc (assigned_task) trên từng picking
        for picking in pickings:
            self.env['stock.picking.scan.history'].create({
                'picking_id': picking.id,
                'scan_type': 'assigned_task',
                'scan_user_id': self.env.uid,
                'scan_date': fields.Datetime.now(),
                'scan_note': f'Giao việc từ SO - Chính sách: {dict(self._fields["picking_policy"].selection).get(self.picking_policy, "")}'
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
            self.env['customer.shipping.history'].create({
                'partner_id': self.partner_id.id,
                'park_info': self.park_info,
                'sale_order_id': self.sale_order_id.id,
                'picking_id': picking.id,
                'shipping_method_id': self.shipping_method_id.id,
                'recipient_name': self.recipient_name,
                'recipient_phone': self.recipient_phone,
                'recipient_address': self.recipient_address,
                'note': f'Giao việc từ wizard - Chính sách: {self.picking_policy}'
            })
