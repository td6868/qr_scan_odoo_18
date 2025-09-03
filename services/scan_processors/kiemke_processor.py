from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class StockLocationInventoryProcessor(models.TransientModel):
    _name = 'stock.location.inventory.processor'
    _description = 'Inventory Scan Processor'
    _inherit = 'stock.location.base.processor'

    def _get_scan_type(self):
        return 'kiemke'

    def _process_specific(self, scan_history, data):
        """Áp dụng kết quả kiểm kê trực tiếp vào stock.quant"""
        try:
            records = data if isinstance(data, list) else json.loads(data or "[]")
        except Exception:
            raise ValidationError("Dữ liệu kiểm kê không hợp lệ")

        adjusted = []
        location_id = scan_history.location_id.id

        for item in records:
            product_id = item.get('product_id')
            counted_qty = float(item.get('counted_quantity', 0))
            is_new = item.get('is_new', False)
            quant_id = item.get('quant_id')

            if is_new:
                # Tạo quant mới cho sản phẩm chưa có trong vị trí
                result = self._create_new_quant(location_id, product_id, counted_qty)
                if result:
                    adjusted.append(result)
            else:
                # Cập nhật quant hiện có
                if quant_id:
                    result = self._update_existing_quant(quant_id, counted_qty)
                    if result:
                        adjusted.append(result)

        # Tạo scan history với kết quả
        scan_history.write({
            'inventory_data': json.dumps(adjusted),
            'total_products': len(adjusted),
            'products_with_changes': len([a for a in adjusted if a.get('changed', False)])
        })

        return {
            'status': 'success',
            'adjusted_count': len(adjusted),
            'adjustments': adjusted,
        }

    def _create_new_quant(self, location_id, product_id, counted_qty):
        """Tạo quant mới cho sản phẩm chưa có trong vị trí"""
        try:
            # Kiểm tra sản phẩm
            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                _logger.warning(f"[INVENTORY] Product {product_id} not found")
                return None

            # Tạo quant mới với số lượng kiểm kê
            quant = self.env['stock.quant'].create({
                'product_id': product_id,
                'location_id': location_id,
                'quantity': 0,  # Số lượng hiện tại = 0
                'inventory_quantity': counted_qty,  # Số lượng kiểm kê
            })

            # Áp dụng inventory adjustment
            quant.action_apply_inventory()

            _logger.info(f"[INVENTORY] Created new quant for {product.display_name}: 0 -> {counted_qty}")

            return {
                'product': product.display_name,
                'from': 0,
                'to': counted_qty,
                'action': 'created',
                'changed': True
            }

        except Exception as e:
            _logger.error(f"[INVENTORY] Error creating new quant: {str(e)}")
            return None

    def _update_existing_quant(self, quant_id, counted_qty):
        """Cập nhật quant hiện có"""
        try:
            quant = self.env['stock.quant'].browse(quant_id)
            if not quant.exists():
                _logger.warning(f"[INVENTORY] Quant {quant_id} not found")
                return None

            current_qty = quant.quantity

            # Chỉ cập nhật nếu có thay đổi
            if counted_qty != current_qty:
                quant.inventory_quantity = counted_qty
                quant.action_apply_inventory()  # Odoo sẽ tự sinh stock.move

                _logger.info(f"[INVENTORY] {quant.product_id.display_name}: {current_qty} -> {counted_qty}")

                return {
                    'product': quant.product_id.display_name,
                    'from': current_qty,
                    'to': counted_qty,
                    'action': 'updated',
                    'changed': True
                }
            else:
                return {
                    'product': quant.product_id.display_name,
                    'from': current_qty,
                    'to': counted_qty,
                    'action': 'no_change',
                    'changed': False
                }

        except Exception as e:
            _logger.error(f"[INVENTORY] Error updating quant {quant_id}: {str(e)}")
            return None

    def get_location_products(self, location_id):
        """Lấy danh sách sản phẩm trong vị trí"""
        try:
            quants = self.env['stock.quant'].search([
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
            _logger.error(f"[INVENTORY] Error getting location products: {str(e)}")
            return []

    def get_product_other_locations(self, product_id, exclude_location_id):
        """Lấy danh sách vị trí khác của sản phẩm"""
        try:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product_id),
                ('location_id', '!=', exclude_location_id),
                ('quantity', '>', 0)
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
            _logger.error(f"[INVENTORY] Error getting product other locations: {str(e)}")
            return []