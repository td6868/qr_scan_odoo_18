# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import os
from odoo.modules import get_resource_path
from datetime import datetime, timedelta


class StockPickingDashboardAPI(http.Controller):
    
    @http.route('/dashboard/stock_picking', type='http', auth='user', website=False, sitemap=False)
    def render_dashboard(self, **kwargs):
        """Phục vụ file index.html của React Dashboard"""
        # Đường dẫn tới file index.html trong static
        path = get_resource_path('qr_scan_odoo_18', 'static', 'dashboard', 'index.html')
        
        if not path or not os.path.exists(path):
            return "<h3>Lỗi: Không tìm thấy file Dashboard!</h3><p>Vui lòng kiểm tra thư mục 'static/dashboard' trong module 'qr_scan_odoo_18'.</p>"
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content
        except Exception as e:
            return "<h3>Lỗi hệ thống:</h3><p>%s</p>" % str(e)
    
    # Mapping trạng thái sang tiếng Việt
    STATE_LABELS_VI = {
        'draft': 'Nháp',
        'waiting': 'Đang chờ',
        'confirmed': 'Đã xác nhận',
        'assigned': 'Sẵn sàng',
        'done': 'Hoàn tất',
        'cancel': 'Đã hủy',
    }
    
    SCAN_TYPE_LABELS_VI = {
        'assigned_task': 'Đã giao việc',
        'prepare': 'Chuẩn bị hàng',
        'shipping': 'Vận chuyển hàng',
        'receive': 'Nhận hàng',
        'checking': 'Nhập kho',
        'delivery_complete': 'Hoàn thành',
    }
    
    @http.route('/api/dashboard/stock_picking/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_picking_list(self, **kwargs):
        """API lấy danh sách phiếu giao hàng"""
        try:
            # Lấy parameters từ request
            filters = kwargs.get('filters', {})
            search_term = kwargs.get('search', '')
            search_field = kwargs.get('search_field', 'all')
            page = kwargs.get('page', 1)
            limit = kwargs.get('limit', 50)
            sort_by = kwargs.get('sort_by', 'date')  # 'date', 'scan_type'
            sort_order = kwargs.get('sort_order', 'desc')  # 'asc', 'desc'
            
            # Build domain
            domain = [('picking_type_code', '=', 'outgoing')]
            
            # Filter by scan_type - CẬP NHẬT để lọc theo trạng thái mới nhất
            if filters.get('scan_type'):
                domain.append(('latest_scan_type', '=', filters['scan_type']))
            
            # Filter by state
            if filters.get('state'):
                domain.append(('state', '=', filters['state']))
            
            # Filter by date
            if filters.get('date_from'):
                domain.append(('scheduled_date', '>=', filters['date_from']))
            if filters.get('date_to'):
                domain.append(('scheduled_date', '<=', filters['date_to']))
            
            # Search theo field cụ thể
            if search_term:
                if search_field == 'date':
                    # Search theo ngày (scheduled_date)
                    domain.append(('scheduled_date', 'ilike', search_term))
                elif search_field == 'sale_order':
                    # Search theo mã SO
                    domain.append(('sale_id.name', 'ilike', search_term))
                elif search_field == 'picking_name':
                    # Search theo mã phiếu
                    domain.append(('name', 'ilike', search_term))
                elif search_field == 'customer':
                    # Search theo khách hàng
                    domain.append(('partner_id.name', 'ilike', search_term))
                elif search_field == 'shipping_method':
                    # Search theo loại vận chuyển
                    domain.append(('shipping_method.name', 'ilike', search_term))
                else:
                    # Search tất cả (mặc định)
                    domain.extend([
                        '|', '|', '|', '|', '|',
                        ('name', 'ilike', search_term),
                        ('origin', 'ilike', search_term),
                        ('partner_id.name', 'ilike', search_term),
                        ('sale_id.name', 'ilike', search_term),
                        ('sale_id.user_id.name', 'ilike', search_term),
                        ('shipping_method.name', 'ilike', search_term)
                    ])
            
            # Get pickings với pagination - TỐI ƯU query
            Picking = request.env['stock.picking']
            total_count = Picking.search_count(domain)
            
            # Sắp xếp: Ưu tiên assigned_task_date ASC (cũ nhất trước), NULL cuối cùng
            # Sau đó mới đến scheduled_date DESC
            order_clause = 'assigned_task_date ASC NULLS LAST, scheduled_date DESC'
            
            # Fetch với prefetch để giảm số lần query database
            pickings = Picking.search(
                domain, 
                limit=limit, 
                offset=(page - 1) * limit, 
                order=order_clause
            )
            
            # Prefetch related fields để tránh N+1 query problem
            pickings.mapped('sale_id.name')
            pickings.mapped('sale_id.user_id.name')
            pickings.mapped('partner_id.name')
            pickings.mapped('shipping_method.name')
            pickings.mapped('delivery_note')  # Prefetch delivery note
            
            # Prepare data
            data = []
            for picking in pickings:
                # Get latest scan type - chỉ fetch 1 record
                latest_scan = picking.scan_history_ids.sorted('scan_date', reverse=True)[:1]
                latest_scan_type = latest_scan.scan_type if latest_scan else False
                latest_scan_type_label = self.SCAN_TYPE_LABELS_VI.get(latest_scan_type, '')
                
                # Get state label - sử dụng tiếng Việt
                state_label = self.STATE_LABELS_VI.get(picking.state, picking.state)
                
                # Sort priority cho scan_type: Đã giao việc -> Chuẩn bị -> Đóng gói
                scan_type_priority = {
                    'assigned_task': 1,
                    'prepare': 2,
                    'shipping': 3,
                }.get(latest_scan_type, 99)
                
                # Chuyển đổi múi giờ từ UTC trong DB sang múi giờ người dùng
                scheduled_date_local = fields.Datetime.context_timestamp(request.env.user, picking.scheduled_date) if picking.scheduled_date else None
                assigned_date_local = fields.Datetime.context_timestamp(request.env.user, picking.assigned_task_date) if picking.assigned_task_date else None
                
                data.append({
                    'id': picking.id,
                    'name': picking.name,
                    'date': scheduled_date_local.strftime('%Y-%m-%d %H:%M:%S') if scheduled_date_local else '',
                    'sale_order': picking.sale_id.name if picking.sale_id else '',
                    'customer': picking.partner_id.name if picking.partner_id else '',
                    'salesperson': picking.sale_id.user_id.name if picking.sale_id and picking.sale_id.user_id else '',
                    'shipping_method': picking.shipping_method.name if picking.shipping_method else '',
                    'scan_type': latest_scan_type,
                    'scan_type_label': latest_scan_type_label,
                    'scan_type_priority': scan_type_priority,
                    'state': picking.state,
                    'state_label': state_label,
                    'origin': picking.origin or '',
                    'note': picking.delivery_note or '',  # Sử dụng delivery_note thay vì note
                    'assigned_task_date': assigned_date_local.strftime('%Y-%m-%d %H:%M:%S') if assigned_date_local else '',
                    'sale_id': picking.sale_id.id if picking.sale_id else False,
                })
            
            # Apply sorting nếu sort_by = 'scan_type'
            if sort_by == 'scan_type':
                reverse = (sort_order == 'desc')
                data.sort(key=lambda x: x['scan_type_priority'], reverse=reverse)
            
            return {
                'status': 'success',
                'data': data,
                'total': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/dashboard/stock_picking/prepared_deliveries', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_prepared_deliveries(self, **kwargs):
        """API lấy danh sách đơn gửi xe (Xe tải, Xe bus, Grab) - Nâng cấp hỗ trợ filter và pagination"""
        try:
            # Lấy parameters từ request
            filters = kwargs.get('filters', {})
            page = kwargs.get('page', 1)
            limit = kwargs.get('limit', 50)
            sort_order = kwargs.get('sort_order', 'desc')
            
            # Build domain - chỉ lấy đơn có phương thức vận chuyển là Xe tải, Xe bus hoặc Grab
            domain = [
                ('picking_type_code', '=', 'outgoing'),
                '|', '|',
                ('shipping_method.name', 'ilike', 'xe tải'),
                ('shipping_method.name', 'ilike', 'xe bus'),
                ('shipping_method.name', 'ilike', 'grab'),
            ]
            
            # Filter by stock picking state for shipping tabs:
            # - Chưa xuất: state != done
            # - Đã xuất: state = done, optionally combined with ship_inf_state = none
            if filters.get('state') == 'not_printed':
                domain.append(('sale_assigned_date', '!=', False))
                domain.append(('warehouse_acknowledged', '=', False))
            elif filters.get('state') == 'not_done':
                domain.append(('warehouse_acknowledged', '=', True))
                domain.append(('state', '!=', 'done'))
            elif filters.get('state'):
                domain.append(('state', '=', filters['state']))
            
            # Filter by ship_inf_state (none, received hoặc not_received)
            if filters.get('ship_inf_state'):
                domain.append(('ship_inf_state', '=', filters['ship_inf_state']))
            
            # Get pickings với pagination
            Picking = request.env['stock.picking']
            total_count = Picking.search_count(domain)
            
            # Sắp xếp
            order_clause = 'scheduled_date DESC'
            
            pickings = Picking.search(
                domain, 
                limit=limit, 
                offset=(page - 1) * limit, 
                order=order_clause
            )
            
            # Prefetch related fields để tránh N+1 query
            pickings.mapped('sale_id.name')
            pickings.mapped('sale_id.user_id.name')
            pickings.mapped('partner_id.name')
            pickings.mapped('partner_id.phone')
            pickings.mapped('partner_id.mobile')
            pickings.mapped('partner_id.street')
            pickings.mapped('partner_id.street2')
            pickings.mapped('partner_id.city')
            pickings.mapped('shipping_method.name')
            
            # Prefetch các trường tùy chọn nếu có
            if hasattr(Picking, 'recipient_name'):
                pickings.mapped('recipient_name')
            if hasattr(Picking, 'recipient_phone'):
                pickings.mapped('recipient_phone')
            if hasattr(Picking, 'recipient_address'):
                pickings.mapped('recipient_address')
            if hasattr(Picking, 'recipient_info'):
                pickings.mapped('recipient_info')
            if hasattr(Picking, 'park_info'):
                pickings.mapped('park_info')
            if hasattr(Picking, 'shipping_confirmed_by'):
                pickings.mapped('shipping_confirmed_by.name')
            
            # Prepare data
            data = []
            for picking in pickings:
                
                # Chuyển đổi múi giờ từ UTC sang múi giờ người dùng
                scheduled_date_local = fields.Datetime.context_timestamp(request.env.user, picking.scheduled_date) if picking.scheduled_date else None
                assigned_date_local = fields.Datetime.context_timestamp(request.env.user, picking.assigned_task_date) if picking.assigned_task_date else None
                
                # Recipient info với fallback
                rec_name = getattr(picking, 'recipient_name', '') or getattr(picking, 'recipient_info', '') or (picking.partner_id.name if picking.partner_id else '')
                rec_phone = getattr(picking, 'recipient_phone', '') or (picking.partner_id.phone or picking.partner_id.mobile if picking.partner_id else '')
                rec_address = getattr(picking, 'recipient_address', '')
                if not rec_address and picking.partner_id:
                    addr_parts = []
                    if picking.partner_id.street:
                        addr_parts.append(picking.partner_id.street)
                    if picking.partner_id.street2:
                        addr_parts.append(picking.partner_id.street2)
                    if picking.partner_id.city:
                        addr_parts.append(picking.partner_id.city)
                    rec_address = ', '.join(addr_parts)
                
                # Vehicle / Shipping info
                park_info = getattr(picking, 'park_info', '') or ''
                
                # Ship info state
                ship_inf_state = picking.ship_inf_state if hasattr(picking, 'ship_inf_state') else ''
                
                data.append({
                    'id': picking.id,
                    'name': picking.name,
                    'date': scheduled_date_local.strftime('%Y-%m-%d %H:%M:%S') if scheduled_date_local else '',
                    'sale_order': picking.sale_id.name if picking.sale_id else '',
                    'customer': picking.partner_id.name if picking.partner_id else '',
                    'salesperson': picking.sale_id.user_id.name if picking.sale_id and picking.sale_id.user_id else '',
                    'shipping_method': picking.shipping_method.name if picking.shipping_method else '',
                    'state': picking.state,
                    'state_label': self.STATE_LABELS_VI.get(picking.state, picking.state),
                    'assigned_task_date': assigned_date_local.strftime('%Y-%m-%d %H:%M:%S') if assigned_date_local else '',
                    'sale_id': picking.sale_id.id if picking.sale_id else False,
                    'recipient_name': rec_name or '',
                    'recipient_phone': rec_phone or '',
                    'recipient_address': rec_address or '',
                    'park_info': park_info or '',
                    'ship_inf_state': ship_inf_state,
                    'shipping_confirmed_by_id': picking.shipping_confirmed_by.id if getattr(picking, 'shipping_confirmed_by', False) else False,
                    'shipping_confirmed_by_name': picking.shipping_confirmed_by.name if getattr(picking, 'shipping_confirmed_by', False) else '',
                })
            
            return {
                'status': 'success',
                'data': data,
                'total': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/dashboard/stock_picking/shipping_users', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_shipping_users(self, **kwargs):
        """Danh sách user active để chọn người gửi xe."""
        try:
            users = request.env['res.users'].sudo().search([
                ('active', '=', True),
                ('share', '=', False),
            ], order='name')

            return {
                'status': 'success',
                'data': [
                    {'id': user.id, 'name': user.name}
                    for user in users
                ],
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
            }

    @http.route('/api/dashboard/stock_picking/confirm_received', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def confirm_shipping_received(self, **kwargs):
        """Chọn người gửi xe và chuyển trạng thái giao vận sang Đã nhận."""
        try:
            picking_id = kwargs.get('picking_id')
            user_id = kwargs.get('user_id')

            if not picking_id or not user_id:
                return {'status': 'error', 'message': 'Thiếu phiếu hoặc người gửi xe'}

            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Phiếu không tồn tại'}

            user = request.env['res.users'].sudo().browse(int(user_id))
            if not user.exists():
                return {'status': 'error', 'message': 'Người gửi xe không tồn tại'}

            if picking.ship_inf_state != 'not_received':
                return {
                    'status': 'error',
                    'message': 'Chỉ có thể xác nhận các đơn ở trạng thái Chưa nhận',
                }

            picking.write({
                'shipping_confirmed_by': user.id,
                'ship_inf_state': 'received',
            })

            picking.message_post(
                body=f'<p><strong>✅ Đã chọn người gửi xe:</strong> {user.name}</p>',
                subject='Xác nhận người gửi xe',
                message_type='notification',
            )

            return {
                'status': 'success',
                'message': f'Đã chuyển đơn sang Đã nhận cho {user.name}',
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route('/api/dashboard/stock_picking/filters', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_filter_options(self, **kwargs):
        """API lấy các options cho filters"""
        try:
            ScanHistory = request.env['stock.picking.scan.history']
            Picking = request.env['stock.picking']
            
            # Scan types - sử dụng tiếng Việt
            scan_types = [{'value': key, 'label': label} for key, label in self.SCAN_TYPE_LABELS_VI.items()]
            
            # States - sử dụng tiếng Việt
            states = [{'value': key, 'label': label} for key, label in self.STATE_LABELS_VI.items()]
            
            return {
                'status': 'success',
                'data': {
                    'scan_types': scan_types,
                    'states': states
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/dashboard/stock_picking/search_suggestions', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_search_suggestions(self, **kwargs):
        """API lấy gợi ý search từ dữ liệu thực tế"""
        try:
            search_field = kwargs.get('search_field', 'all')
            search_term = kwargs.get('search_term', '')
            limit = kwargs.get('limit', 10)
            
            if not search_term or len(search_term) < 2:
                return {
                    'status': 'success',
                    'data': []
                }
            
            Picking = request.env['stock.picking']
            suggestions = []
            
            # Lấy suggestions theo field
            if search_field == 'date':
                # Lấy các ngày unique
                pickings = Picking.search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('scheduled_date', '!=', False)
                ], limit=limit, order='scheduled_date desc')
                seen = set()
                for picking in pickings:
                    if picking.scheduled_date:
                        date_str = picking.scheduled_date.strftime('%Y-%m-%d')
                        if date_str not in seen and search_term.lower() in date_str.lower():
                            seen.add(date_str)
                            suggestions.append({
                                'value': date_str,
                                'label': date_str
                            })
                            
            elif search_field == 'sale_order':
                # Lấy mã SO unique
                pickings = Picking.search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('sale_id.name', 'ilike', search_term)
                ], limit=limit)
                seen = set()
                for picking in pickings:
                    if picking.sale_id and picking.sale_id.name not in seen:
                        seen.add(picking.sale_id.name)
                        suggestions.append({
                            'value': picking.sale_id.name,
                            'label': picking.sale_id.name
                        })
                        
            elif search_field == 'picking_name':
                # Lấy mã phiếu unique
                pickings = Picking.search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('name', 'ilike', search_term)
                ], limit=limit)
                for picking in pickings:
                    suggestions.append({
                        'value': picking.name,
                        'label': picking.name
                    })
                    
            elif search_field == 'customer':
                # Lấy khách hàng unique
                pickings = Picking.search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('partner_id.name', 'ilike', search_term)
                ], limit=limit)
                seen = set()
                for picking in pickings:
                    if picking.partner_id and picking.partner_id.name not in seen:
                        seen.add(picking.partner_id.name)
                        suggestions.append({
                            'value': picking.partner_id.name,
                            'label': picking.partner_id.name
                        })
                        
            elif search_field == 'shipping_method':
                # Lấy loại vận chuyển unique
                pickings = Picking.search([
                    ('picking_type_code', '=', 'outgoing'),
                    ('shipping_method.name', 'ilike', search_term)
                ], limit=limit)
                seen = set()
                for picking in pickings:
                    if picking.shipping_method and picking.shipping_method.name not in seen:
                        seen.add(picking.shipping_method.name)
                        suggestions.append({
                            'value': picking.shipping_method.name,
                            'label': picking.shipping_method.name
                        })
            
            return {
                'status': 'success',
                'data': suggestions[:limit]
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

