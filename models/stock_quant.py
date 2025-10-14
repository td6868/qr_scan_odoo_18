# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def get_location_products(self, location_id):
        """Lấy danh sách sản phẩm trong vị trí cụ thể"""
        try:
            quants = self.search([
                ('location_id', '=', location_id),
                ('quantity', '>', 0)
            ])

            result = []
            for quant in quants:
                result.append({
                    'id': quant.id,
                    'product_id': [quant.product_id.id, quant.product_id.name, quant.product_id.default_code],
                    'quantity': quant.quantity,
                    'product_uom_id': [quant.product_uom_id.id, quant.product_uom_id.name],
                    'reserved_quantity': quant.reserved_quantity,
                    'available_quantity': quant.quantity - quant.reserved_quantity
                })

            return result

        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error getting location products: {str(e)}")
            return []

    def get_product_other_locations(self, product_id, exclude_location_id):
        """Lấy danh sách vị trí khác của sản phẩm"""
        try:
            quants = self.search([
                ('product_id', '=', product_id),
                ('location_id', '!=', exclude_location_id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal')
            ])

            result = []
            for quant in quants:
                result.append({
                    'location_id': quant.location_id.id,
                    'location_name': quant.location_id.complete_name,
                    'quantity': quant.quantity,
                    'uom_name': quant.product_uom_id.name,
                    'reserved_quantity': quant.reserved_quantity,
                    'available_quantity': quant.quantity - quant.reserved_quantity
                })

            return result

        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error getting product other locations: {str(e)}")
            return []


    def update_inventory_count(self, counted_quantity):
        """Cập nhật số lượng kiểm kê cho quant hiện có"""
        try:
            if counted_quantity < 0:
                raise ValidationError("Số lượng kiểm kê không được âm")

            current_qty = self.quantity
            if counted_quantity == current_qty:
                return {
                    'success': True,
                    'message': 'Không có thay đổi số lượng',
                    'from': current_qty,
                    'to': counted_quantity
                }

            diff_qty = counted_quantity - current_qty
            # Lấy inventory location từ product property
            inventory_location = self.product_id.with_company(self.company_id).property_stock_inventory


            move_vals = {
                'name': f'Inventory Adjustment - {self.product_id.display_name}',
                'product_id': self.product_id.id,
                'product_uom': self.product_id.uom_id.id,
                'product_uom_qty': abs(diff_qty),
                'location_id': inventory_location.id if diff_qty > 0 else self.location_id.id,
                'location_dest_id': self.location_id.id if diff_qty > 0 else inventory_location.id,
                'move_line_ids': [(0, 0, {
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'qty_done': abs(diff_qty),
                    'location_id': inventory_location.id if diff_qty > 0 else self.location_id.id,
                    'location_dest_id': self.location_id.id if diff_qty > 0 else inventory_location.id,
                })]
            }

            move = self.env['stock.move'].sudo().create(move_vals)
            move._action_confirm()
            move._action_done()

            # Cập nhật quantity của quant thành counted_quantity
            self.sudo().write({'quantity': counted_quantity})
            self.sudo().write({'inventory_quantity': counted_quantity})

            _logger.info(f"[STOCK.QUANT] Updated inventory for {self.product_id.display_name}: {current_qty} -> {counted_quantity}")

            return {
                'success': True,
                'message': f'Đã cập nhật số lượng từ {current_qty} thành {counted_quantity}',
                'from': current_qty,
                'to': counted_quantity
            }

        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error updating inventory count: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_location_summary(self, location_id):
        """Lấy tổng quan vị trí kho"""
        try:
            quants = self.search([
                ('location_id', '=', location_id),
                ('quantity', '>', 0)
            ])

            summary = {
                'total_products': len(quants),
                'total_quantity': sum(quants.mapped('quantity')),
                'total_reserved': sum(quants.mapped('reserved_quantity')),
                'total_available': sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity')),
                'products': []
            }

            for quant in quants:
                summary['products'].append({
                    'product_name': quant.product_id.display_name,
                    'product_code': quant.product_id.default_code or '',
                    'quantity': quant.quantity,
                    'reserved': quant.reserved_quantity,
                    'available': quant.quantity - quant.reserved_quantity,
                    'uom': quant.product_uom_id.name
                })

            return summary

        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error getting location summary: {str(e)}")
            return {
                'total_products': 0,
                'total_quantity': 0,
                'total_reserved': 0,
                'total_available': 0,
                'products': []
            }

    @api.model
    def get_product_available_quantity(self, product_id):
        """
        Lấy số lượng có sẵn của một sản phẩm cụ thể trên toàn bộ kho.
        """
        try:
            domain = [
                ('product_id', '=', product_id),
                ('location_id.usage', '=', 'internal')
            ]
            _logger.info(f"[STOCK.QUANT] Searching quants for product {product_id} with domain: {domain}")

            quants = self.search(domain)
            _logger.info(f"[STOCK.QUANT] Found {len(quants)} quants for product {product_id}")
            
            total_quantity = 0
            
            for quant in quants:
                _logger.info(f"[STOCK.QUANT] Quant ID {quant.id}: quantity={quant.quantity}, reserved={quant.reserved_quantity}")
                total_quantity += quant.quantity
            
            total_available_quantity = total_quantity
            _logger.info(f"[STOCK.QUANT] Product {product_id}: Total quantity={total_quantity}, Available={total_available_quantity}")
            
            if total_available_quantity < 0:
                _logger.warning(f"[STOCK.QUANT] Negative available quantity for product {product_id}")
                raise ValidationError("Số lượng tồn kho không đủ để chuẩn bị hàng!")
            
            return max(0, total_available_quantity)  # Ensure we don't return negative
        
        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error getting product available quantity for product {product_id}: {str(e)}", exc_info=True)
            return 0


    @api.model
    def search_products_for_inventory(self, search_term='', limit=20):
        """
        Tìm kiếm sản phẩm để thêm vào kiểm kê
        """
        try:
            _logger.info(f"[STOCK.QUANT] Searching with term: '{search_term}'")
            
            # Kiểm tra có sản phẩm nào không - thử nhiều điều kiện khác nhau
            _logger.info("[STOCK.QUANT] Checking product.product table...")
            
            # 1. Kiểm tra tất cả sản phẩm
            all_products = self.env['product.product'].search([], limit=10)
            _logger.info(f"[STOCK.QUANT] Total products (all types): {len(all_products)}")   
                              
            # Thử domain đơn giản hơn
            if not search_term:
                # Không có search term - lấy tất cả sản phẩm có thể stockable
                domain = ['|', ('type', '=', 'product'), ('type', '=', 'consu')]
            else:
                # Có search term - tìm theo nhiều trường
                domain = [
                    '|', ('type', '=', 'product'), ('type', '=', 'consu'),
                    '|', '|',
                    ('name', 'ilike', search_term),
                    ('default_code', 'ilike', search_term),
                    ('barcode', 'ilike', search_term)
                ]  
            
            _logger.info(f"[STOCK.QUANT] Using domain: {domain}")
            products = self.env['product.product'].search(domain, limit=limit)
            _logger.info(f"[STOCK.QUANT] Found {len(products)} products with new domain")

            result = []
            for product in products:
                result.append({
                    'id': product.id,
                    'name': product.display_name,
                    'default_code': product.default_code or '',
                    'uom_name': product.uom_id.name,
                    'type': product.type,
                })
            
            _logger.info(f"[STOCK.QUANT] Returning {len(result)} products")
            return result
            
        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error searching products: {str(e)}")
            import traceback
            _logger.error(f"[STOCK.QUANT] Traceback: {traceback.format_exc()}")
            return []
        
    @api.model
    def add_product_to_inventory(self, location_id, product_id, quantity=0):
        """
        Thêm sản phẩm vào inventory của location
        """
        try:
            _logger.info(f"[STOCK.QUANT] Adding product {product_id} to location {location_id} with quantity {quantity}")
            
            # Kiểm tra location và product tồn tại
            location = self.env['stock.location'].browse(location_id)
            product = self.env['product.product'].browse(product_id)
            
            if not location.exists():
                raise ValueError(f"Location {location_id} not found")
            if not product.exists():
                raise ValueError(f"Product {product_id} not found")
            
            # Tìm quant hiện tại hoặc tạo mới
            existing_quant = self.search([
                ('location_id', '=', location_id),
                ('product_id', '=', product_id),
                ('lot_id', '=', False)
            ], limit=1)
            
            if existing_quant:
                # Cập nhật quantity của quant hiện tại
                _logger.info(f"[STOCK.QUANT] Updating existing quant {existing_quant.id}")
                existing_quant.quantity = quantity
                result_quant = existing_quant
            else:
                # Tạo quant mới
                _logger.info(f"[STOCK.QUANT] Creating new quant")
                result_quant = self.create({
                    'product_id': product_id,
                    'location_id': location_id,
                    'quantity': quantity,
                    'lot_id': False,
                    'package_id': False,
                    'owner_id': False,
                })
            
            # Tạo stock move để ghi nhận thay đổi inventory
            if quantity != 0:
                inventory_location = self.env.ref('stock.location_inventory', raise_if_not_found=False)
                if not inventory_location:
                    # Fallback: tìm inventory location từ company
                    inventory_location = product.with_company(location.company_id or self.env.company).property_stock_inventory
                
                if inventory_location:
                    move_vals = {
                        'name': f'Inventory Adjustment - {product.display_name}',
                        'product_id': product_id,
                        'product_uom': product.uom_id.id,
                        'product_uom_qty': abs(quantity),
                        'location_id': inventory_location.id if quantity > 0 else location_id,
                        'location_dest_id': location_id if quantity > 0 else inventory_location.id,
                        'state': 'done',
                        'is_inventory': True,
                    }
                    
                    move = self.env['stock.move'].create(move_vals)
                    move._action_done()
                    _logger.info(f"[STOCK.QUANT] Created inventory move {move.id}")
            
            return {
                'success': True,
                'quant_id': result_quant.id,
                'message': f'Added {product.display_name} to {location.display_name}',
                'product_name': product.display_name,
                'location_name': location.display_name,
                'quantity': quantity
            }
            
        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error adding product to inventory: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @api.model
    def remove_product_from_inventory(self, location_id, product_id):
        """
        Xóa sản phẩm khỏi inventory của location (set quantity = 0)
        """
        try:
            _logger.info(f"[STOCK.QUANT] Removing product {product_id} from location {location_id}")
            
            # Kiểm tra location và product tồn tại
            location = self.env['stock.location'].browse(location_id)
            product = self.env['product.product'].browse(product_id)
            
            if not location.exists():
                raise ValueError(f"Location {location_id} not found")
            if not product.exists():
                raise ValueError(f"Product {product_id} not found")
            
            # Tìm quant hiện tại
            existing_quant = self.search([
                ('location_id', '=', location_id),
                ('product_id', '=', product_id),
                ('lot_id', '=', False)
            ], limit=1)
            
            if not existing_quant:
                return {
                    'success': False,
                    'error': f'Sản phẩm {product.display_name} không tồn tại trong vị trí {location.display_name}'
                }
            
            current_quantity = existing_quant.quantity
            
            # Kiểm tra có reserved quantity không
            if existing_quant.reserved_quantity > 0:
                return {
                    'success': False,
                    'error': f'Không thể xóa sản phẩm {product.display_name} vì đang có {existing_quant.reserved_quantity} {product.uom_id.name} được đặt trước'
                }
            
            # Tạo stock move để move toàn bộ quantity về inventory location
            if current_quantity >= 0:
                inventory_location = self.env.ref('stock.location_inventory', raise_if_not_found=False)
                if not inventory_location:
                    # Fallback: tìm inventory location từ company
                    inventory_location = product.with_company(location.company_id or self.env.company).property_stock_inventory
                
                if inventory_location:
                    move_vals = {
                        'name': f'Remove from Inventory - {product.display_name}',
                        'product_id': product_id,
                        'product_uom': product.uom_id.id,
                        'product_uom_qty': current_quantity,
                        'location_id': location_id,
                        'location_dest_id': inventory_location.id,
                        'state': 'done',
                        'is_inventory': True,
                    }
                    
                    move = self.env['stock.move'].create(move_vals)
                    move._action_done()
                    _logger.info(f"[STOCK.QUANT] Created removal move {move.id}")
            
            # Xóa quant nếu quantity = 0 và không có reserved
            if existing_quant.quantity == 0 and existing_quant.reserved_quantity == 0:
                existing_quant.sudo().unlink()
                _logger.info(f"[STOCK.QUANT] Deleted empty quant {existing_quant.id}")
            
            return {
                'success': True,
                'message': f'Đã xóa {product.display_name} khỏi {location.display_name}',
                'product_name': product.display_name,
                'location_name': location.display_name,
                'removed_quantity': current_quantity
            }
            
        except Exception as e:
            _logger.error(f"[STOCK.QUANT] Error removing product from inventory: {str(e)}")
            import traceback
            _logger.error(f"[STOCK.QUANT] Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
