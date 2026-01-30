from odoo import models, fields, api


class DashboardItem(models.Model):
    _name = 'dashboard.item'
    _description = 'Dashboard Item'
    _order = 'sequence, name'

    name = fields.Char('Tên Dashboard', required=True)
    description = fields.Text('Mô tả')
    url = fields.Char('URL/Endpoint', required=True, help='VD: /dashboard/stock_picking')
    icon = fields.Selection([
        ('fa-chart-line', '📈 Biểu đồ đường'),
        ('fa-chart-bar', '📊 Biểu đồ cột'),
        ('fa-chart-pie', '🥧 Biểu đồ tròn'),
        ('fa-table', '📋 Bảng'),
        ('fa-truck', '🚚 Vận chuyển'),
        ('fa-boxes', '📦 Kho hàng'),
        ('fa-shopping-cart', '🛒 Đơn hàng'),
        ('fa-users', '👥 Nhân viên'),
        ('fa-dollar-sign', '💰 Tài chính'),
        ('fa-cog', '⚙️ Cài đặt'),
    ], string='Icon', default='fa-chart-line', required=True)
    color = fields.Selection([
        ('primary', 'Xanh dương'),
        ('success', 'Xanh lá'),
        ('warning', 'Vàng'),
        ('danger', 'Đỏ'),
        ('info', 'Xanh nhạt'),
        ('purple', 'Tím'),
    ], string='Màu sắc', default='primary', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Hoạt động', default=True)
    open_new_tab = fields.Boolean('Mở tab mới', default=True, 
                                   help='Nếu bật, dashboard sẽ mở trong tab mới')

    @api.model
    def get_dashboard_data(self):
        """Trả về dữ liệu dashboard cho client"""
        dashboards = self.search([('active', '=', True)])
        return [{
            'id': d.id,
            'name': d.name,
            'description': d.description or '',
            'url': d.url,
            'icon': d.icon,
            'color': d.color,
            'open_new_tab': d.open_new_tab,
        } for d in dashboards]
