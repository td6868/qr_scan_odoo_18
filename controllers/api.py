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
        mode = params.get('mode')  # Get mode from App
        _logger.info(">>> Extracted picking_id: %s (type: %s), mode: %s", picking_id, type(picking_id), mode)
        
        # VALIDATION: Check session
        user_id = request.session.uid if getattr(request.session, 'uid', False) else None
        if not user_id:
            _logger.warning("Session expired or missing in picking_detail")
            return {
                'status': 'error',
                'message': 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.',
                'error_code': 'SESSION_EXPIRED'
            }


        picking = self._get_picking(picking_id)
        if not picking or not picking.exists():
            _logger.warning("Picking ID %s NOT FOUND", picking_id)
            return {'status': 'error', 'message': 'Phiếu không tồn tại trên hệ thống'}
        
        # ========== EARLY VALIDATION - Kiểm tra ngay khi quét QR ==========
        
        # RULE 1: Không cho phép quét những đơn đã có trạng thái done hoặc cancel
        if picking.state == 'done':
            return {
                'status': 'error',
                'message': f"❌ Không thể quét phiếu {picking.name}\n\nLý do: Phiếu này đã hoàn tất (Done).\nKhông thể quét lại phiếu đã hoàn tất!",
                'error_code': 'PICKING_DONE'
            }
        
        if picking.state == 'cancel':
            return {
                'status': 'error',
                'message': f"❌ Không thể quét phiếu {picking.name}\n\nLý do: Phiếu này đã bị hủy (Cancelled).\nVui lòng kiểm tra lại!",
                'error_code': 'PICKING_CANCELLED'
            }
        
        # RULE 2: Kiểm tra trạng thái Sale Order liên quan
        if picking.sale_id and picking.sale_id.state == 'cancel':
            return {
                'status': 'error',
                'message': f"❌ Không thể quét phiếu {picking.name}\n\nLý do: Đơn hàng {picking.sale_id.name} đã bị hủy.\nPhiếu giao hàng này không còn hiệu lực!",
                'error_code': 'SALE_ORDER_CANCELLED'
            }
        
        # RULE 3 & 4: Kiểm tra theo mode (prepare hoặc shipping)
        if mode == 'prepare':
            # RULE 3: Chỉ được quét chuẩn bị những đơn có trạng thái quét là "đã giao việc"
            has_assigned_task = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'assigned_task')
            if not has_assigned_task:
                return {
                    'status': 'error',
                    'message': f"❌ Không thể chuẩn bị phiếu {picking.name}\n\nLý do: Phiếu này chưa được giao việc!\nVui lòng giao việc cho nhân viên trước khi quét chuẩn bị.",
                    'error_code': 'NOT_ASSIGNED'
                }
            
            # Kiểm tra đã chuẩn bị chưa
            has_prepare_history = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'prepare')
            if has_prepare_history:
                return {
                    'status': 'error',
                    'message': f"⚠️ Phiếu {picking.name} đã được chuẩn bị rồi!\n\nNgười chuẩn bị: {has_prepare_history[0].scan_user_id.name}\nThời gian: {has_prepare_history[0].scan_date}\n\nNếu cần đóng gói, vui lòng chọn chế độ 'Đóng gói' thay vì 'Chuẩn bị'.",
                    'error_code': 'ALREADY_PREPARED'
                }
        
        elif mode == 'shipping':
            # RULE 4: Muốn quét đóng gói được thì phải qua bước chuẩn bị
            has_prepare_history = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'prepare')
            if not has_prepare_history:
                return {
                    'status': 'error',
                    'message': f"❌ Không thể đóng gói phiếu {picking.name}\n\nLý do: Phiếu này chưa được chuẩn bị!\nVui lòng quét QR và chọn 'Chuẩn bị hàng' trước khi đóng gói.",
                    'error_code': 'NOT_PREPARED'
                }
            
            # Kiểm tra đã đóng gói chưa
            has_shipping_history = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'shipping')
            if has_shipping_history:
                return {
                    'status': 'error',
                    'message': f"⚠️ Phiếu {picking.name} đã được đóng gói rồi!\n\nNgười đóng gói: {has_shipping_history[0].scan_user_id.name}\nThời gian: {has_shipping_history[0].scan_date}\n\nKhông thể đóng gói lại phiếu đã hoàn tất!",
                    'error_code': 'ALREADY_SHIPPED'
                }
        
        # ========== END EARLY VALIDATION ==========
            
        _logger.info("Found picking: %s with %s moves", picking.name, len(picking.move_ids))
            
        grouped_data = {}
        for move in picking.move_ids:
            if move.state == 'cancel': continue
            key = (move.product_id.id, move.product_uom.id, move.location_id.id)
            if key not in grouped_data:
                # Lấy số lượng tồn kho tại vị trí nguồn
                qty_available = move.product_id.with_context(location=move.location_id.id).qty_available
                grouped_data[key] = {
                    'move_ids': [move.id],
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.display_name,
                    'uom': move.product_uom.name,
                    'location_name': move.location_id.display_name,
                    'quantity': move.product_uom_qty,
                    'quantity_confirmed': move.quantity,
                    'quantity_available': qty_available,  # Số lượng tồn kho
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
            # Get user from session
            user_id = request.session.uid if getattr(request.session, 'uid', False) else None
            
            if not user_id:
                _logger.warning("Session expired in picking_prepare")
                return {
                    'status': 'error',
                    'message': 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.',
                    'error_code': 'SESSION_EXPIRED'
                }
            
            _logger.info("API call picking_prepare by User ID: %s", user_id)
            
            images = params.get('images', [])
            images_data = [{'data': img.get('data'), 'name': img.get('name'), 'description': 'Chuẩn bị từ App'} for img in images]
            
            picking.update_scan_info(
                images_data=images_data,
                scan_note=params.get('scan_note', ''),
                move_line_confirms=params.get('move_line_confirms', []),
                scan_mode='prepare',
                scan_user_id=int(user_id),
                auto_validate=True
            )
            
            return {'status': 'success', 'message': 'Chuẩn bị và xác nhận hàng thành công!'}
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
            # Get user from session
            user_id = request.session.uid if getattr(request.session, 'uid', False) else None
            
            if not user_id:
                _logger.warning("Session expired in picking_package")
                return {
                    'status': 'error',
                    'message': 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.',
                    'error_code': 'SESSION_EXPIRED'
                }
            
            _logger.info("API call picking_package by User ID: %s", user_id)
            
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
                scan_user_id=int(user_id),
                auto_validate=True
            )
            
            return {'status': 'success', 'message': 'Đóng gói và xác nhận phiếu thành công!'}
        except Exception as e:
            _logger.error("Package API Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}
