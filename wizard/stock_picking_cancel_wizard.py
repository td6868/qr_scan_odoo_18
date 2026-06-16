# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup

class StockPickingCancelWizard(models.TransientModel):
    _name = 'stock.picking.cancel.wizard'
    _description = 'Wizard Từ Chối Giao Việc'

    picking_id = fields.Many2one(
        'stock.picking', 
        string='Phiếu kho', 
        required=True, 
        default=lambda self: self.env.context.get('active_id')
    )
    reason = fields.Text(
        string='Lý do từ chối', 
        required=True,
        help='Nhập lý do từ chối giao việc để phản hồi cho sales'
    )

    def action_confirm_cancel(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking:
            return {'type': 'ir.actions.act_window_close'}
            
        if not picking.sale_assigned_date:
            raise ValidationError(_("Phiếu này chưa được sale giao việc!"))
        
        if picking.warehouse_acknowledged:
            raise ValidationError(_("Phiếu này đã được xác nhận nhận việc rồi!"))

        # Ghi nhận lý do và reset các trường giao việc trên Picking
        picking.write({
            'cancel_reason': self.reason,
            'sale_assigned_date': False,
            'sale_assigned_user_id': False,
            'wh_user_id': False,
            'warehouse_acknowledged': False,
            'warehouse_acknowledged_date': False,
            'wh_ack_user_id': False,
        })

        # Post message to sale order chatter
        if picking.sale_id:
            message = f"""<p><strong>❌ Thủ kho không chấp nhận công việc</strong></p>
            <ul>
                <li><strong>Phiếu xuất kho:</strong> {picking.name}</li>
                <li><strong>Thủ kho:</strong> {self.env.user.name}</li>
                <li><strong>Thời gian:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                <li><strong>Lý do từ chối:</strong> {self.reason}</li>
            </ul>
            <p><em>Vui lòng kiểm tra lại đơn hàng!</em></p>"""   
            
            picking.sale_id.message_post(
                body=Markup(message),
                subject=_('Thủ kho không chấp nhận công việc'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        
        # Log to picking chatter as well for history
        picking.message_post(
            body=Markup(f"<p><strong>❌ Đã từ chối giao việc với lý do:</strong> {self.reason}</p>"),
            subject=_('Từ chối giao việc'),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        return {'type': 'ir.actions.act_window_close'}
