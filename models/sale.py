from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    #add view image proof
    def action_view_image_proof(self):
        self.ensure_one()
        domain = [('picking_id.sale_id', '=', self.id)]
        image_proof_ids = self.env['stock.picking.scan.history'].search(domain)
        """Hiển thị ảnh chứng minh"""
        result = {
            'name': 'Ảnh chứng minh',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.scan.history',
            'domain': domain,
            'context': {'create': False},
        }          
        result.update({
            "view_mode": 'kanban,form',
            "domain": domain,
        })  
        return result