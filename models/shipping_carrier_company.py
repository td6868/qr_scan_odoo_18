# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ShippingCarrierCompany(models.Model):
    _name = 'shipping.carrier.company'
    _description = 'Nhà xe vận chuyển'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    # Thông tin cơ bản
    name = fields.Char('Tên nhà xe', required=True, tracking=True)
    phone = fields.Char('Số điện thoại', required=True, tracking=True)
    phone_secondary = fields.Char('Số điện thoại phụ')
    address = fields.Text('Địa chỉ gửi hàng')
    contact_person = fields.Char('Người liên hệ')

    
    # Thông tin vận hành
    route_ids = fields.Many2many(
        'shipping.route', 
        'shipping_company_route_rel',
        'company_id', 'route_id',
        string='Tuyến đường phục vụ'
    )
    schedule_ids = fields.One2many(
        'shipping.schedule', 
        'company_id', 
        string='Lịch trình xuất bến'
    )
    
    # Ghi chú
    note = fields.Text('Ghi chú nội bộ')
    
    # Liên kết
    picking_ids = fields.One2many('stock.picking', 'shipping_carrier_company_id', string='Phiếu xuất kho')
    
    @api.constrains('phone')
    def _check_phone(self):
        for record in self:
            if record.phone and len(record.phone) < 10:
                raise ValidationError('Số điện thoại phải có ít nhất 10 chữ số!')
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.phone})"
            result.append((record.id, name))
        return result
    
    def action_view_pickings(self):
        """Xem danh sách phiếu xuất kho của nhà xe này"""
        self.ensure_one()
        return {
            'name': f'Phiếu xuất kho - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('shipping_carrier_company_id', '=', self.id)],
            'context': {'default_shipping_carrier_company_id': self.id}
        }
