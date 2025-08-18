from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class PurchaseOrderPrint(models.TransientModel):
    _name = "product.order.print"
    
    def get_info_poc_id(self):
        id = self.env.context.get('active_ids')
        poc = self.env['product.order.china'].browse(id)
        return poc
    
    def action_print(self, poc):
        return self.env.ref('qr_scan_odoo_18.action_report_purchase_order_china').report_action(poc)
    
    def action_confirm(self):
        poc = self.get_info_poc_id()
            
        poc._compute_subtotal_word()
        report = self.action_print(poc)

        return report