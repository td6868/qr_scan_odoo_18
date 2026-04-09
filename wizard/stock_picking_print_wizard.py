from odoo import models, fields, api, _

class StockPickingPrintWizard(models.TransientModel):
    _name = 'stock.picking.print.wizard'
    _description = 'Wizard in phiếu xuất kho'

    picking_id = fields.Many2one('stock.picking', string='Phiếu kho', default=lambda self: self.env.context.get('active_id'))
    report_type = fields.Selection(selection='_get_report_types', string='Loại phiếu in', required=True, default='type_1')
    
    sender_info = fields.Char(string='Người gửi')
    recipient_info = fields.Char(string='Người nhận')

    @api.model
    def _get_report_types(self):
        """Lấy danh sách các loại phiếu in từ model stock.picking."""
        context = self.env.context or {}
        # Tìm picking_id từ nhiều nguồn context khác nhau
        picking_id = context.get('active_id') or context.get('default_picking_id')
        if not picking_id and context.get('active_ids'):
            picking_id = context.get('active_ids')[0]

        if picking_id:
            picking = self.env['stock.picking'].browse(picking_id).exists()
            if picking:
                # Nếu tìm thấy picking, trả về danh sách options theo logic của bản ghi đó
                return picking._get_print_report_options()
        
        # Trường hợp fallback (khi load view hoặc không tìm thấy context)
        # Trả về tất cả các loại để widget Selection được đăng ký đầy đủ
        return [
            ('type_1', 'In phiếu'),
            ('type_2', 'In phiếu (Điền)'),
            ('type_3', 'In phiếu (Gửi xe)'),
            ('type_4', 'In phiếu (Tên gốc)')
        ]

    @api.onchange('report_type', 'picking_id')
    def _onchange_report_type(self):
        if self.report_type == 'type_3' and self.picking_id:
            # Lấy dữ liệu đã được tính toán từ bản ghi
            self.sender_info = self.picking_id.sender_info
            self.recipient_info = self.picking_id.recipient_info

    def action_print(self):
        self.ensure_one()
        picking = self.picking_id or self.env['stock.picking'].browse(self.env.context.get('active_id'))
        
        if not picking:
            return {'type': 'ir.actions.act_window_close'}
            
        if self.report_type == 'type_3':
            # Lưu lại thông tin vào phiếu xuất kho để đồng bộ và lưu trữ
            picking.write({
                'sender_info': self.sender_info,
                'recipient_info': self.recipient_info,
            })
            return self.env.ref('qr_scan_odoo_18.action_report_packing_ticket').report_action(picking)

        # Gọi hàm xử lý in các loại khác từ model stock.picking
        if hasattr(picking, 'action_perform_print'):
            return picking.action_perform_print(self.report_type)

        if self.report_type == 'type_1':
            return picking.action_print_picking()
        
        return {'type': 'ir.actions.act_window_close'}
