# -*- coding: utf-8 -*-
from odoo import models, fields, api
from markupsafe import Markup

class QRScanNotification(models.Model):
    _name = 'qr_scan.notification'
    _description = 'QR Scan App Notifications'
    _order = 'create_date desc'

    notification_type = fields.Selection([
        ('reassign_request', 'Reassignment Request'),
        ('info', 'Information'),
        ('warning', 'Warning'),
    ], string='Type', required=True, default='info')
    
    title = fields.Char(string='Title', required=True)
    message = fields.Text(string='Message')
    
    # Người nhận thông báo
    recipient_user_id = fields.Many2one('res.users', string='Recipient User', required=True, index=True)
    
    # Trạng thái
    is_read = fields.Boolean(string='Is Read', default=False)
    is_processed = fields.Boolean(string='Is Processed', default=False)  # Đã xử lý (accept/decline)
    response = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ], string='Response', default='pending')
    
    # Dữ liệu liên quan (JSON format)
    related_model = fields.Char(string='Related Model')  # e.g., 'stock.picking'
    related_id = fields.Integer(string='Related Record ID')
    
    # Cho reassignment request
    picking_id = fields.Many2one('stock.picking', string='Related Picking')
    from_user_id = fields.Many2one('res.users', string='From User')
    new_employee_id = fields.Many2one('hr.employee', string='New Employee')
    
    # Metadata
    create_date = fields.Datetime(string='Created At', readonly=True)
    response_date = fields.Datetime(string='Response Date')
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.ensure_one()
        self.write({'is_read': True})
        return True
    
    def accept_reassignment(self):
        """Accept reassignment request"""
        self.ensure_one()
        if self.notification_type != 'reassign_request':
            return {'status': 'error', 'message': 'Not a reassignment request'}
        
        if self.response != 'pending':
            return {'status': 'error', 'message': 'Already processed'}
        
        # Update picking's assigned user
        if self.picking_id and self.new_employee_id and self.new_employee_id.user_id:
            self.picking_id.sudo().write({
                'shipping_confirmed_by': self.new_employee_id.user_id.id,
            })
            
            # Log to chatter
            self.picking_id.message_post(
                body=Markup(f"""
                    <p><strong>✅ Yêu cầu chuyển giao được chấp nhận</strong></p>
                    <p>{self.new_employee_id.name} đã đồng ý nhận công việc giao hàng cho phiếu {self.picking_id.name}</p>
                """),
                subject=f'Chấp nhận chuyển giao: {self.picking_id.name}',
                message_type='notification',
            )
        
        # Update notification
        self.write({
            'response': 'accepted',
            'is_processed': True,
            'is_read': True,
            'response_date': fields.Datetime.now(),
        })
        
        return {'status': 'success', 'message': 'Đã chấp nhận yêu cầu chuyển giao'}
    
    def decline_reassignment(self):
        """Decline reassignment request"""
        self.ensure_one()
        if self.notification_type != 'reassign_request':
            return {'status': 'error', 'message': 'Not a reassignment request'}
        
        if self.response != 'pending':
            return {'status': 'error', 'message': 'Already processed'}
        
        # Log to chatter
        if self.picking_id and self.new_employee_id:
            self.picking_id.message_post(
                body=Markup(f"""
                    <p><strong>❌ Yêu cầu chuyển giao bị từ chối</strong></p>
                    <p>{self.new_employee_id.name} đã từ chối nhận công việc giao hàng cho phiếu {self.picking_id.name}</p>
                """),
                subject=f'Từ chối chuyển giao: {self.picking_id.name}',
                message_type='notification',
            )
        
        # Update notification
        self.write({
            'response': 'declined',
            'is_processed': True,
            'is_read': True,
            'response_date': fields.Datetime.now(),
        })
        
        return {'status': 'success', 'message': 'Đã từ chối yêu cầu chuyển giao'}
