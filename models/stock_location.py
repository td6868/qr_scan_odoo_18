from odoo import models, fields
from odoo.exceptions import UserError
import json

class StockLocation(models.Model):
    _inherit = 'stock.location'
    
    qr_code_image = fields.Binary(string="QR Code Image", attachment=True, store=True)
    qr_code_data = fields.Text(string="QR Code Data")
    
    def generate_qr_code(self):
        """Tạo QR code cho record sử dụng multi-model service"""
        qr_service = self.env['multi.model.qr.service']
        for record in self:
            qr_service.generate_qr_for_record(record, 'stock.location')

    def create(self, vals_list):
        records = super().create(vals_list)
        # Tạo QR code cho các record mới
        for record in records:
            if record.name:
                record.generate_qr_code()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Nếu name thay đổi, tạo lại QR code
        if "name" in vals:
            for rec in self:
                rec.generate_qr_code()
        return res

    def action_qr_scan_stock_location_history(self):
        """Action để mở lịch sử quét QR của location này"""
        return {
            'name': 'Lịch sử quét QR',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.location.scan.history',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.id)],
            'context': {
                'default_location_id': self.id,
                'search_default_location_id': self.id,
            },
            'target': 'current',
        }


class StockLocationScanHistory(models.Model):
    _name = 'stock.location.scan.history'
    _description = 'Stock Location Scan History'
    _order = 'scan_time desc'

    location_id = fields.Many2one('stock.location', string='Location', required=True)
    scan_time = fields.Datetime(string='Scan Date', required=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)

    # Dữ liệu lưu kết quả scan
    inventory_data = fields.Text(string='Inventory Data JSON')
    note = fields.Text(string='Scan Note')

    # Thống kê cơ bản (cập nhật khi lưu, không compute)
    total_products = fields.Integer(string='Tổng số sản phẩm', default=0)
    products_with_changes = fields.Integer(string='Số sản phẩm thay đổi', default=0)
    total_quantity_added = fields.Float(string='Tổng số lượng thêm', default=0.0)
    total_quantity_removed = fields.Float(string='Tổng số lượng giảm', default=0.0)
    
    # Chi tiết thay đổi sản phẩm
    product_changes_summary = fields.Text(string='Tóm tắt thay đổi sản phẩm')


    def save_inventory_scan(self, inventory_data, scan_note=None):
        """Lưu dữ liệu scan và thống kê chi tiết"""
        self.ensure_one()

        if inventory_data:
            self.inventory_data = json.dumps(inventory_data)

            # Tính toán thống kê chi tiết
            total_products = len(inventory_data)
            products_with_changes = 0
            total_added = 0.0
            total_removed = 0.0
            changes_summary = []

            for item in inventory_data:
                current_qty = item.get('current_quantity', 0)
                counted_qty = item.get('counted_quantity', 0)
                difference = counted_qty - current_qty
                
                if difference != 0:
                    products_with_changes += 1
                    product_name = item.get('product_name', 'Unknown Product')
                    
                    if difference > 0:
                        total_added += difference
                        changes_summary.append(f"+ {product_name}: +{difference}")
                    else:
                        total_removed += abs(difference)
                        changes_summary.append(f"- {product_name}: {difference}")

            # Cập nhật các field thống kê
            self.total_products = total_products
            self.products_with_changes = products_with_changes
            self.total_quantity_added = total_added
            self.total_quantity_removed = total_removed
            self.product_changes_summary = '\n'.join(changes_summary) if changes_summary else 'Không có thay đổi'

        if scan_note:
            self.note = scan_note

        return True
