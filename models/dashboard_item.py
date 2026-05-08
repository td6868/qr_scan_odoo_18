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
    allowed_group_ids = fields.Many2many(
        'res.groups',
        'dashboard_item_res_groups_rel',
        'dashboard_item_id',
        'group_id',
        string='Allowed Groups',
        help='Nếu để trống thì mọi user có quyền vào Dashboard Hub đều thấy item này.',
    )

    @api.model
    def get_dashboard_data(self):
        dashboards = self.search([('active', '=', True)])
        visible_dashboards = dashboards.filtered(
            lambda dashboard: not dashboard.allowed_group_ids
            or bool(dashboard.allowed_group_ids & self.env.user.groups_id)
        )
        return [{
            'id': dashboard.id,
            'name': dashboard.name,
            'description': dashboard.description or '',
            'url': dashboard.url,
            'icon': dashboard.icon,
            'color': dashboard.color,
            'open_new_tab': dashboard.open_new_tab,
        } for dashboard in visible_dashboards]
