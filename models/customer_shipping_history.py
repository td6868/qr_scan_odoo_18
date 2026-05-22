# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CustomerShippingHistory(models.Model):
    _name = 'customer.shipping.history'
    _description = 'Lịch sử gửi xe theo khách hàng'
    _order = 'shipping_date desc'
    _rec_name = 'display_name'

    # Core relations
    partner_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        required=True,
        index=True,
        ondelete='cascade'
    )
    park_info = fields.Text(
        string='Thông tin gửi xe',
        help='Thông tin gửi xe đã sử dụng'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn hàng',
        ondelete='set null'
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Phiếu xuất kho',
        ondelete='set null'
    )

    # Shipping details
    shipping_date = fields.Datetime(
        string='Ngày gửi',
        default=fields.Datetime.now,
        required=True
    )
    shipping_method_id = fields.Many2one(
        'delivery.carrier',
        string='Phương thức vận chuyển'
    )

    # Recipient info (if different from partner)
    recipient_name = fields.Char(string='Người nhận')
    recipient_phone = fields.Char(string='SĐT người nhận')
    recipient_address = fields.Text(string='Địa chỉ nhận')

    # Metadata
    created_by = fields.Many2one(
        'res.users',
        string='Người tạo',
        default=lambda self: self.env.user,
        readonly=True
    )
    note = fields.Text(string='Ghi chú')

    # Display name
    display_name = fields.Char(
        string='Tên hiển thị',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('partner_id', 'park_info', 'shipping_date')
    def _compute_display_name(self):
        for record in self:
            partner_name = record.partner_id.name or 'N/A'
            park_info = (record.park_info or 'N/A').strip()
            if len(park_info) > 30:
                park_info = park_info[:30] + '...'
            date_str = record.shipping_date.strftime('%d/%m/%Y') if record.shipping_date else 'N/A'
            record.display_name = f"{partner_name} - {park_info} ({date_str})"

    def name_get(self):
        result = []
        for record in self:
            name = record.display_name or f"History #{record.id}"
            result.append((record.id, name))
        return result

    @api.model
    def get_history_by_partner(self, partner_id):
        """Get shipping history for a partner - called from JS popover"""
        if not partner_id:
            return []

        histories = self.search([
            ('partner_id', '=', partner_id)
        ], order='shipping_date desc', limit=10)

        result = []
        for h in histories:
            result.append({
                'id': h.id,
                'date': h.shipping_date.strftime('%d/%m/%Y %H:%M') if h.shipping_date else '',
                'park_info': h.park_info or '',
                'sale_order': h.sale_order_id.name or '',
                'picking': h.picking_id.name or '',
                'recipient_name': h.recipient_name or '',
                'recipient_phone': h.recipient_phone or '',
                'recipient_address': h.recipient_address or '',
                'note': h.note or '',
            })
        return result

    @api.model
    def get_history_for_apply(self, history_ids):
        """Get history data for applying to wizard - called from JS popover"""
        if not history_ids:
            return False

        history = self.browse(history_ids[0]) if isinstance(history_ids, list) else self.browse(history_ids)
        if not history.exists():
            return False

        return {
            'park_info': history.park_info or '',
            'recipient_name': history.recipient_name or '',
            'recipient_phone': history.recipient_phone or '',
            'recipient_address': history.recipient_address or '',
        }
