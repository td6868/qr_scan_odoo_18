# -*- coding: utf-8 -*-
from odoo import http, SUPERUSER_ID
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
        
        # RULE 1: Không cho phép quét CHUẨN BỊ những đơn đã có trạng thái done
        # (Mode 'shipping' cần phiếu done nên được phép)
        if mode == 'prepare' and picking.state == 'done':
            return {
                'status': 'error',
                'message': f"❌ Không thể quét chuẩn bị phiếu {picking.name}\n\nLý do: Phiếu này đã hoàn tất (Done).\n\nNếu cần gửi xe, vui lòng chọn chế độ 'Gửi xe' thay vì 'Chuẩn bị'.",
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
            # RULE 4.1: Phiếu phải ở trạng thái Done mới được gửi xe
            if picking.state != 'done':
                return {
                    'status': 'error',
                    'message': f"❌ Không thể gửi xe phiếu {picking.name}\n\nLý do: Phiếu chưa hoàn thành (Done)!\nTrạng thái hiện tại: {dict(picking._fields['state'].selection).get(picking.state)}\n\nVui lòng hoàn thành phiếu xuất kho trước khi gửi xe.",
                    'error_code': 'NOT_DONE'
                }
            
            # RULE 4.2: Phiếu phải đã qua bước chuẩn bị (latest_scan_type = 'prepare')
            # if picking.latest_scan_type != 'prepare':
            #     current_status = dict(picking._fields['latest_scan_type'].selection).get(picking.latest_scan_type) if picking.latest_scan_type else 'Chưa quét'
            #     return {
            #         'status': 'error',
            #         'message': f"❌ Không thể gửi xe phiếu {picking.name}\n\nLý do: Phiếu chưa được chuẩn bị!\nTrạng thái quét hiện tại: {current_status}\n\nVui lòng quét QR và chọn 'Chuẩn bị hàng' trước khi gửi xe.",
            #         'error_code': 'NOT_PREPARED'
            #     }
            
            # RULE 4.3: Kiểm tra đã gửi xe chưa (COMMENTED: Cho phép load màn hình gửi xe để nhập chi phí)
            # has_shipping_history = picking.scan_history_ids.filtered(lambda h: h.scan_type == 'shipping')
            # if has_shipping_history:
            #     return {
            #         'status': 'error',
            #         'message': f"⚠️ Phiếu {picking.name} đã được xác nhận gửi xe rồi!\n\nNgười xác nhận: {has_shipping_history[0].scan_user_id.name}\nThời gian: {has_shipping_history[0].scan_date}\n\nKhông thể xác nhận lại phiếu đã hoàn tất!",
            #         'error_code': 'ALREADY_SHIPPED'
            #     }
        
        # ========== END EARLY VALIDATION ==========
            
        _logger.info("Found picking: %s with %s moves", picking.name, len(picking.move_ids))
        
        # Mode 'shipping' chỉ cần thông tin giao hàng, không cần danh sách sản phẩm
        if mode == 'shipping':
            # Lấy thông tin người gửi (NVKD từ sale order hoặc user_id)
            salesperson = picking.sale_id.user_id if picking.sale_id and picking.sale_id.user_id else picking.user_id
            
            # Fallback động nếu stored field chưa có giá trị
            sender_name = picking.sender_info
            if not sender_name or sender_name == 'OdooBot':
                sender_name = (salesperson.name if salesperson else '') or ''
            
            recipient_name = picking.recipient_info
            if not recipient_name:
                recipient_name = picking.partner_id.name or ''

            return {
                'status': 'success',
                'mode': 'shipping',
                'picking': {
                    'id': picking.id,
                    'name': picking.name,
                    'origin': picking.origin or '',
                    'state': picking.state,
                    'scheduled_date': picking.scheduled_date.isoformat() if picking.scheduled_date else None,
                    
                    # Thông tin người gửi
                    'sender_info': sender_name,
                    'sender_phone': salesperson.mobile or salesperson.phone if salesperson else '',
                    'sender_email': salesperson.email if salesperson else '',
                    
                    # Thông tin người nhận
                    'recipient_info': recipient_name,
                    'recipient_phone': picking.partner_id.phone or '',
                    'recipient_address': picking.partner_id.contact_address if picking.partner_id else '',
                    
                    # Thông tin nhà xe
                    # 'shipping_carrier_company_id': picking.shipping_carrier_company_id.id if picking.shipping_carrier_company_id else None,
                    # 'shipping_carrier_name': picking.shipping_carrier_company_id.name if picking.shipping_carrier_company_id else '',
                    # 'shipping_carrier_phone': picking.shipping_carrier_company_id.phone if picking.shipping_carrier_company_id else '',
                    # 'shipping_route_id': picking.shipping_route_id.id if picking.shipping_route_id else None,
                    # 'shipping_route_name': picking.shipping_route_id.name if picking.shipping_route_id else '',
                    # 'available_routes': [{'id': r.id, 'name': r.name} for r in picking.shipping_carrier_company_id.route_ids] if getattr(picking.shipping_carrier_company_id, 'route_ids', False) else [],

                    'shipping_carrier_company_id': None,
                    'shipping_carrier_name': picking.demo_bus_company or '',
                    'shipping_carrier_phone': '',
                    'shipping_route_id': None,
                    'shipping_route_name': '',
                    'available_routes': [],
                    
                    # Trạng thái
                    'is_prepared': picking.is_prepared,
                    'is_shipped': getattr(picking, 'is_shipped', False),
                    'is_sent_to_carrier': getattr(picking, 'is_sent_to_carrier', False),
                }
            }
            
        # Mode 'prepare' cần danh sách sản phẩm để xác nhận
        grouped_data = {}
        for move in picking.move_ids:
            if move.state == 'cancel': continue
            key = (move.product_id.id, move.product_uom.id, move.location_id.id)
            if key not in grouped_data:
                # Lấy số lượng tồn kho theo vị trí nguồn (product.product with context location)
                product_loc = move.product_id.with_context(location=move.location_id.id)
                qty_available = product_loc.qty_available
                free_qty = product_loc.free_qty

                grouped_data[key] = {
                    'move_ids': [move.id],
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.display_name,
                    'uom': move.product_uom.name,
                    'location_name': move.location_id.display_name,
                    'quantity': move.product_uom_qty,
                    'quantity_confirmed': move.quantity,
                    'quantity_available': qty_available,  # Số lượng tồn kho
                    'free_qty': free_qty,  # Số lượng khả dụng (product.product.free_qty)
                }
            else:
                grouped_data[key]['move_ids'].append(move.id)
                grouped_data[key]['quantity'] += move.product_uom_qty
                grouped_data[key]['quantity_confirmed'] += move.quantity

        return {
            'status': 'success',
            'mode': 'prepare',
            'picking': {
                'id': picking.id,
                'name': picking.name,
                'state': picking.state,
                'partner_name': picking.partner_id.name or 'N/A',
                'partner_phone': picking.partner_id.phone or '',
                'is_prepared': picking.is_prepared,
                'is_shipped': getattr(picking, 'is_shipped', False),
                'is_sent_to_carrier': getattr(picking, 'is_sent_to_carrier', False),
                # 'shipping_carrier_company_id': picking.shipping_carrier_company_id.id if picking.shipping_carrier_company_id else None,
                # 'shipping_carrier_name': picking.shipping_carrier_company_id.name or '',
                # 'shipping_carrier_phone': picking.shipping_carrier_company_id.phone or '',
                'shipping_carrier_company_id': None,
                'shipping_carrier_name': picking.demo_bus_company or '',
                'shipping_carrier_phone': '',
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
                shipping_route_id=params.get('shipping_route_id'),
                shipping_driver_phone=params.get('shipping_driver_phone'),
                shipping_vehicle_number=params.get('shipping_vehicle_number'),
                shipping_tracking_number=params.get('shipping_tracking_number'),
                scan_user_id=int(user_id),
                auto_validate=True
            )
            
            return {'status': 'success', 'message': 'Đóng gói và xác nhận phiếu thành công!'}
        except Exception as e:
            _logger.error("Package API Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/qr/parse', type='json', auth='none', methods=['POST'], csrf=False)
    def parse_qr_code(self, **params):
        """Parse QR code và trả về thông tin model"""
        try:
            qr_content = params.get('qr_content')
            if not qr_content:
                return {'status': 'error', 'message': 'Thiếu nội dung QR code'}
            
            qr_service = request.env['multi.model.qr.service'].sudo()
            parsed = qr_service.parse_qr_data(qr_content)
            
            if not parsed.get('is_valid'):
                return {'status': 'error', 'message': 'QR code không hợp lệ'}
            
            result = {
                'status': 'success',
                'model': parsed['model'],
                'record_id': parsed['record_id'],
            }
            
            _logger.info("QR Parsed: %s", result)
            return result
            
        except Exception as e:
            _logger.error("Parse QR Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/picking/expenses', type='json', auth='none', methods=['POST'], csrf=False)
    def get_picking_expenses(self, **params):
        """Lấy danh sách chi phí liên quan đến picking / sale order
        
        Params:
            picking_id: ID phiếu xuất kho
        Returns:
            expenses: list of hr.expense records
            expense_products: list of product có thể dùng làm chi phí
        """
        try:
            picking_id = params.get('picking_id')
            picking = self._get_picking(picking_id)
            if not picking or not picking.exists():
                return {'status': 'error', 'message': 'Phiếu không tồn tại'}

            sale = picking.sale_id

            # Lấy danh sách expense đã có (liên kết qua sale order)
            expenses = []
            if sale:
                exp_records = request.env['hr.expense'].with_user(SUPERUSER_ID).search([
                    ('sale_id', '=', sale.id)
                ], order='date desc')
                for exp in exp_records:
                    expenses.append({
                        'id': exp.id,
                        'name': exp.name,
                        'total_amount_currency': exp.total_amount_currency,
                        'date': exp.date.isoformat() if exp.date else '',
                        'description': exp.description or '',
                        'state': exp.state,
                        'employee_name': exp.employee_id.name if exp.employee_id else '',
                        'product_name': exp.product_id.name if exp.product_id else '',
                    })

            # Lấy danh sách sản phẩm chi phí (expense products)
            expense_products = []
            products = request.env['product.product'].with_user(SUPERUSER_ID).search([
                ('can_be_expensed', '=', True)
            ], limit=50)
            
            # Ưu tiên "Chi phí vận chuyển đơn hàng" lên đầu tiên
            products = sorted(products, key=lambda p: 0 if p.name == 'Chi phí vận chuyển đơn hàng' else 1)
            
            for p in products:
                expense_products.append({
                    'id': p.id,
                    'name': p.name,
                    'account_id': p.property_account_expense_id.id if p.property_account_expense_id else None,
                    'account_name': p.property_account_expense_id.name if p.property_account_expense_id else '',
                })

            # Thông tin mặc định (NVKD để điền employee_id)
            salesperson = sale.user_id if sale and sale.user_id else None
            employee = None
            if salesperson:
                employee = request.env['hr.employee'].with_user(SUPERUSER_ID).search([
                    ('user_id', '=', salesperson.id)
                ], limit=1)

            default_product = next((p for p in expense_products if p['name'] == 'Chi phí vận chuyển đơn hàng'), None)
            default_product_id = default_product['id'] if default_product else (expense_products[0]['id'] if expense_products else None)

            return {
                'status': 'success',
                'sale_name': sale.name if sale else '',
                'sale_id': sale.id if sale else None,
                'picking_name': picking.name,
                'employee_id': employee.id if employee else None,
                'employee_name': employee.name if employee else (salesperson.name if salesperson else ''),
                'expenses': expenses,
                'expense_products': expense_products,
                'default_expense_product_id': default_product_id,
            }

        except Exception as e:
            _logger.error("Get Expenses Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/picking/expense/save', type='json', auth='none', methods=['POST'], csrf=False)
    def save_picking_expense(self, **params):
        """Tạo mới hoặc cập nhật chi phí vận chuyển
        
        Params:
            picking_id: ID phiếu xuất kho
            expense_id: (optional) ID expense để cập nhật
            product_id: ID sản phẩm chi phí
            total_amount_currency: Số tiền
            description: Nội dung ghi chú
        """
        try:
            user_id = request.session.uid if getattr(request.session, 'uid', False) else None
            if not user_id:
                return {'status': 'error', 'message': 'Phiên đăng nhập hết hạn', 'error_code': 'SESSION_EXPIRED'}

            picking_id = params.get('picking_id')
            picking = self._get_picking(picking_id)
            if not picking or not picking.exists():
                return {'status': 'error', 'message': 'Phiếu không tồn tại'}

            sale = picking.sale_id
            if not sale:
                return {'status': 'error', 'message': 'Phiếu này không liên kết với đơn hàng nào!'}

            product_id = params.get('product_id')
            total_amount = params.get('total_amount_currency', 0)
            description = params.get('description', '')

            # Tự động gán danh mục "Chi phí vận chuyển đơn hàng" nếu rỗng
            if not product_id:
                default_prod = request.env['product.product'].sudo().search([
                    ('name', '=', 'Chi phí vận chuyển đơn hàng'), 
                    ('can_be_expensed', '=', True)
                ], limit=1)
                if default_prod:
                    product_id = default_prod.id

            if not product_id:
                return {'status': 'error', 'message': 'Vui lòng chọn danh mục chi phí!'}
            if not total_amount or float(total_amount) <= 0:
                return {'status': 'error', 'message': 'Vui lòng nhập số tiền chi phí!'}

            product = request.env['product.product'].sudo().browse(int(product_id))

            # Lấy employee của NVKD
            salesperson = sale.user_id
            employee = None
            if salesperson:
                employee = request.env['hr.employee'].with_user(SUPERUSER_ID).search([
                    ('user_id', '=', salesperson.id)
                ], limit=1)

            expense_env = request.env['hr.expense'].with_user(user_id).sudo()
            expense_id = params.get('expense_id')

            if expense_id:
                # Cập nhật expense đã có
                expense = expense_env.browse(int(expense_id))
                if not expense.exists():
                    return {'status': 'error', 'message': 'Chi phí không tồn tại'}
                expense.write({
                    'total_amount_currency': float(total_amount),
                    'description': description,
                    'product_id': int(product_id),
                })
                msg = 'Cập nhật chi phí thành công!'
            else:
                # Tạo mới expense
                from odoo import fields as odoo_fields
                expense_name = f"Chi phí Vận chuyển - Gửi xe - {sale.name}"
                account = product.property_account_expense_id
                
                vals = {
                    'name': expense_name,
                    'product_id': int(product_id),
                    'total_amount_currency': float(total_amount),
                    'description': description,
                    'date': odoo_fields.Date.today(),
                    'payment_mode': 'company_account',
                    'sale_id': sale.id,
                }
                if employee:
                    vals['employee_id'] = employee.id
                if account:
                    vals['account_id'] = account.id

                expense = expense_env.create(vals)
                msg = 'Thêm chi phí vận chuyển thành công!'

            return {
                'status': 'success',
                'message': msg,
                'expense_id': expense.id,
            }

        except Exception as e:
            _logger.error("Save Expense Error: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}


