from odoo import api, models
class StockPickingReportKhoakim(models.AbstractModel):
    _name = 'report.qr_scan_odoo_18.report_stock_picking_khoakim'
    _description = 'Mẫu in phiếu xuất kho Khoa Kim'

    @api.model
    def _get_report_values(self, docids, data=None):
        pickings = self.env['stock.picking'].browse(docids)
        # Đảm bảo QR được tạo trước khi in báo cáo
        pickings._generate_qr_code()
        return {
            'doc_ids': pickings.ids,
            'doc_model': 'stock.picking',
            'docs': pickings,
        }
        
class PurchaseOrderChina(models.AbstractModel):
    _name = 'report.qr_scan_odoo_18.action_report_po_china'
    _description = 'Mẫu phiếu mua hàng Khoa Kim'

    def _get_report_values(self, docids, data=None):
        docs = self.env['product.order.china'].browse(docids)
        docs._generate_qr_code()
        return {
            'doc_ids': docs.ids,
            'doc_model': 'purchase.order',
            'docs': docs,
        }
        
class PurchaseOrderKhoakim(models.AbstractModel):
    _name = 'report.qr_scan_odoo_18.report_purchase_order_khoakim'
    _description = 'Mẫu phiếu mua hàng Khoa Kim'

    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)
        docs._generate_qr_code()
        return {
            'doc_ids': docs.ids,
            'doc_model': 'stock.picking',
            'docs': docs,
        }