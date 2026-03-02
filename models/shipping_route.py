# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ShippingRoute(models.Model):
    _name = 'shipping.route'
    _description = 'Tuyến đường vận chuyển'
    _order = 'name'
    
    name = fields.Char('Tên tuyến', compute='_compute_name', store=True)
    origin_city = fields.Char('Điểm đi', required=True)
    destination_city = fields.Char('Điểm đến', required=True)
    estimated_days = fields.Integer('Thời gian vận chuyển (ngày)', default=1)
    
    # Các nhà xe phục vụ tuyến này
    company_ids = fields.Many2many(
        'shipping.carrier.company',
        'shipping_company_route_rel',
        'route_id', 'company_id',
        string='Nhà xe phục vụ'
    )
    
    note = fields.Text('Ghi chú')
    
    @api.depends('origin_city', 'destination_city')
    def _compute_name(self):
        for record in self:
            if record.origin_city and record.destination_city:
                record.name = f"{record.origin_city} → {record.destination_city}"
            else:
                record.name = "Tuyến mới"
    
    @api.constrains('origin_city', 'destination_city')
    def _check_cities(self):
        for record in self:
            if record.origin_city and record.destination_city:
                if record.origin_city.lower() == record.destination_city.lower():
                    raise ValidationError('Điểm đi và điểm đến không được trùng nhau!')
