# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import os
from odoo.modules import get_resource_path
from datetime import datetime, timedelta


class StockPickingDashboardAPI(http.Controller):
    
    @http.route('/dashboard/stock_picking', type='http', auth='user', website=True)
    def render_dashboard(self, **kwargs):
        """Phục vụ file index.html của React Dashboard"""
        # Đường dẫn tới file index.html trong static
        path = get_resource_path('qr_scan_odoo_18', 'static', 'dashboard', 'index.html')
        if not path or not os.path.exists(path):
            return "Dashboard files not found. Please build the frontend and copy to static/dashboard."
            
        with open(path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        return html_content
    
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
        'prepare': 'Chuẩn bị hàng',
        'shipping': 'Đóng gói',
        'receive': 'Nhận hàng',
        'checking': 'Nhập kho',
        'assigned_task': 'Đã giao việc',
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
            
            # Fetch với prefetch để giảm số lần query database
            pickings = Picking.search(
                domain, 
                limit=limit, 
                offset=(page - 1) * limit, 
                order='scheduled_date desc'
            )
            
            # Prefetch related fields để tránh N+1 query problem
            pickings.mapped('sale_id.name')
            pickings.mapped('sale_id.user_id.name')
            pickings.mapped('partner_id.name')
            pickings.mapped('shipping_method.name')
            
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
                
                data.append({
                    'id': picking.id,
                    'name': picking.name,
                    'date': picking.scheduled_date.strftime('%Y-%m-%d %H:%M:%S') if picking.scheduled_date else '',
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
        """API lấy danh sách phiếu đã chuẩn bị (Xe tải/Xe bus)"""
        try:
            # Domain: Phương thức vận chuyển chứa "Xe tải" hoặc "Xe bus" + scan_type = prepare
            domain = [
                ('picking_type_code', '=', 'outgoing'),
                ('scan_history_ids.scan_type', '=', 'prepare'),
                '|',
                ('shipping_method.name', 'ilike', 'xe tải'),
                ('shipping_method.name', 'ilike', 'xe bus'),
            ]
            
            Picking = request.env['stock.picking']
            pickings = Picking.search(domain, order='scheduled_date desc')
            
            data = []
            for picking in pickings:
                # Get latest scan
                latest_scan = picking.scan_history_ids.filtered(lambda s: s.scan_type == 'prepare').sorted('scan_date', reverse=True)[:1]
                
                data.append({
                    'id': picking.id,
                    'name': picking.name,
                    'date': picking.scheduled_date.strftime('%Y-%m-%d %H:%M:%S') if picking.scheduled_date else '',
                    'sale_order': picking.sale_id.name if picking.sale_id else '',
                    'customer': picking.partner_id.name if picking.partner_id else '',
                    'salesperson': picking.sale_id.user_id.name if picking.sale_id and picking.sale_id.user_id else '',
                    'shipping_method': picking.shipping_method.name if picking.shipping_method else '',
                    'scan_date': latest_scan.scan_date.strftime('%Y-%m-%d %H:%M:%S') if latest_scan and latest_scan.scan_date else '',
                    'scan_user': latest_scan.scan_user_id.name if latest_scan and latest_scan.scan_user_id else '',
                })
            
            return {
                'status': 'success',
                'data': data,
                'total': len(data)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
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

