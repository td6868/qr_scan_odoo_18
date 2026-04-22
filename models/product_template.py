from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # free_qty chỉ tồn tại trên product.product (biến thể)
    # Cần tạo computed field trên product.template để tổng hợp từ các biến thể
    available_to_use_tmpl = fields.Float(
        string="Tồn khả dụng",
        compute="_compute_available_to_use_tmpl",
        digits='Product Unit of Measure',
    )

    def _compute_available_to_use_tmpl(self):
        """Tổng hợp free_qty từ tất cả biến thể của template."""
        for tmpl in self:
            tmpl.available_to_use_tmpl = sum(
                tmpl.product_variant_ids.mapped('free_qty')
            )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    latest_stock_increase_date = fields.Date(
        string="Ngày tăng tồn gần nhất",
        copy=False,
        tracking=True,
        help="Ngày gần nhất sản phẩm được tăng tồn do nhập kho hoặc khách trả hàng."
    )
