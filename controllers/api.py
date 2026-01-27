# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)
_logger.info("=" * 80)
_logger.info("QR SCAN API CONTROLLER MODULE LOADED")
_logger.info("=" * 80)

class QRScanAPI(http.Controller):

    def _get_picking(self, picking_id):
        # Convert to int safely
        try:
            pid = int(picking_id)
            return request.env['stock.picking'].sudo().browse(pid)
        except:
            return None

    @http.route('/api/login', type='json', auth='none', methods=['POST'], csrf=False)
    def login(self, **params):
        _logger.info("Mobile App Login Attempt: %s", params)
        db = params.get('db')
        login = params.get('login')
        password = params.get('password')
        
        if not db or not login or not password:
            return {'status': 'error', 'message': 'Thiếu tham số đăng nhập'}

        try:
            uid = request.session.authenticate(db, login, password)
            if uid:
                user = request.env['res.users'].sudo().browse(uid)
                _logger.info("Login successful for user: %s (UID: %s)", user.name, uid)
                return {
                    'status': 'success',
                    'uid': uid,
                    'name': user.name,
                    'session_id': request.session.sid,
                    'db': db
                }
            return {'status': 'error', 'message': 'Sai tài khoản hoặc mật khẩu'}
        except Exception as e:
            _logger.error("Login Error: %s", str(e))
            return {'status': 'error', 'message': f'Lỗi hệ thống: {str(e)}'}

    @http.route('/api/picking/detail', type='json', auth='none', methods=['POST'], csrf=False)
    def picking_detail(self, **params):
        _logger.info("="*80)
        _logger.info(">>> PICKING DETAIL API CALLED")
        _logger.info(">>> Raw params: %s", params)
        _logger.info(">>> Request data: %s", request.httprequest.get_data())
        _logger.info("="*80)
        
        # Sử dụng auth='none' để bypass session check tự động của Odoo
        picking_id = params.get('picking_id')
        _logger.info(">>> Extracted picking_id: %s (type: %s)", picking_id, type(picking_id))
        
        picking = self._get_picking(picking_id)
        if not picking or not picking.exists():
            _logger.warning("Picking ID %s NOT FOUND", picking_id)
            return {'status': 'error', 'message': 'Phiếu không tồn tại trên hệ thống'}
            
        _logger.info("Found picking: %s with %s moves", picking.name, len(picking.move_ids))
            
        grouped_data = {}
        for move in picking.move_ids:
            if move.state == 'cancel': continue
            key = (move.product_id.id, move.product_uom.id, move.location_id.id)
            if key not in grouped_data:
                grouped_data[key] = {
                    'move_ids': [move.id],
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.display_name,
                    'uom': move.product_uom.name,
                    'location_name': move.location_id.display_name,
                    'quantity': move.product_uom_qty,
                    'quantity_confirmed': move.quantity,
                }
            else:
                grouped_data[key]['move_ids'].append(move.id)
                grouped_data[key]['quantity'] += move.product_uom_qty
                grouped_data[key]['quantity_confirmed'] += move.quantity

        return {
            'status': 'success',
            'picking': {
                'id': picking.id,
                'name': picking.name,
                'state': picking.state,
                'partner_name': picking.partner_id.name or 'N/A',
                'is_prepared': picking.is_prepared,
                'is_shipped': getattr(picking, 'is_shipped', False),
            },
            'move_lines': list(grouped_data.values())
        }

    @http.route('/api/picking/prepare', type='json', auth='none', methods=['POST'], csrf=False)
    def picking_prepare(self, **params):
        picking_id = params.get('picking_id')
        _logger.info(">>> API call: picking_prepare for ID: %s", picking_id)
        
        picking = self._get_picking(picking_id)
        if not picking or not picking.exists():
            return {'status': 'error', 'message': 'Phiếu không tồn tại'}
            
        try:
            # Get user from session if available
            user_id = request.session.uid if hasattr(request.session, 'uid') else 1  # fallback to admin
            
            images = params.get('images', [])
            images_data = [{'data': img.get('data'), 'name': img.get('name'), 'description': 'Chuẩn bị từ App'} for img in images]
            
            picking.update_scan_info(
                images_data=images_data,
                scan_note=params.get('scan_note', ''),
                move_line_confirms=params.get('move_line_confirms', []),
                scan_mode='prepare',
                scan_user_id=user_id  # Pass user explicitly
            )
            return {'status': 'success', 'message': 'Lưu chuẩn bị thành công'}
        except Exception as e:
            _logger.error("Prepare API Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/picking/package', type='json', auth='none', methods=['POST'], csrf=False)
    def picking_package(self, **params):
        picking_id = params.get('picking_id')
        _logger.info(">>> API call: picking_package for ID: %s", picking_id)
        
        picking = self._get_picking(picking_id)
        if not picking or not picking.exists():
            return {'status': 'error', 'message': 'Phiếu không tồn tại'}
            
        try:
            # Get user from session if available
            user_id = request.session.uid if hasattr(request.session, 'uid') else 1
            
            images = params.get('images', [])
            images_data = [{'data': img.get('data'), 'name': img.get('name'), 'description': 'Đóng gói từ App'} for img in images]
            
            picking.update_scan_info(
                images_data=images_data,
                scan_note=params.get('scan_note', ''),
                move_line_confirms=params.get('move_line_confirms', []),
                scan_mode='shipping',
                shipping_type=params.get('shipping_type'),
                shipping_phone=params.get('shipping_phone'),
                shipping_company=params.get('shipping_company'),
                scan_user_id=user_id
            )
            
            if picking.state not in ['done', 'cancel']:
                picking.button_validate()
            return {'status': 'success', 'message': 'Lưu đóng gói thành công'}
        except Exception as e:
            _logger.error("Package API Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}
