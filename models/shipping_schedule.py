# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ShippingSchedule(models.Model):
    _name = 'shipping.schedule'
    _description = 'Lịch trình xuất bến'
    _order = 'company_id, route_id, weekday, departure_time'
    
    company_id = fields.Many2one('shipping.carrier.company', string='Nhà xe', required=True, ondelete='cascade')
    route_id = fields.Many2one('shipping.route', string='Tuyến đường', required=True)
    
    weekday = fields.Selection([
        ('0', 'Thứ Hai'),
        ('1', 'Thứ Ba'),
        ('2', 'Thứ Tư'),
        ('3', 'Thứ Năm'),
        ('4', 'Thứ Sáu'),
        ('5', 'Thứ Bảy'),
        ('6', 'Chủ Nhật'),
        ('daily', 'Hàng ngày'),
    ], string='Ngày trong tuần', required=True, default='daily')
    
    departure_time = fields.Text('Thời gian hoạt động', help='Thời gian hoạt động')
    frequency = fields.Selection([
        ('daily', 'Hàng ngày'),
        ('weekly', 'Hàng tuần'),
        ('biweekly', 'Hai tuần một lần'),
        ('monthly', 'Hàng tháng'),
    ], string='Tần suất', default='daily')
    
    active = fields.Boolean('Hoạt động', default=True)
    note = fields.Text('Ghi chú')
    
    _sql_constraints = [
        ('unique_schedule', 'unique(company_id, route_id, weekday, departure_time)', 
         'Lịch trình này đã tồn tại!')
    ]
    
    def name_get(self):
        result = []
        for record in self:
            weekday_label = dict(self._fields['weekday'].selection).get(record.weekday)
            name = f"{record.route_id.name} - {weekday_label} {record.departure_time}"
            result.append((record.id, name))
        return result
