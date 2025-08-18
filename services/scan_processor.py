from odoo import models, fields, api
from odoo.exceptions import ValidationError

class StockPickingScanProcessor(models.TransientModel):
    _name = 'stock.picking.scan.processor'
    _description = 'Scan Processor Service'

    def get_processor(self, scan_type):
        """Factory method to get appropriate processor"""
        processors = {
            'prepare': 'stock.picking.prepare.processor',
            'shipping': 'stock.picking.shipping.processor',
            'receive': 'stock.picking.receive.processor',
            'checking': 'stock.picking.checking.processor',
        }
        
        processor_model = processors.get(scan_type)
        if not processor_model:
            raise ValidationError(f"Không hỗ trợ loại scan: {scan_type}")
        
        return self.env[processor_model].create({})

class BaseScanProcessor(models.AbstractModel):
    _name = 'stock.picking.base.processor'
    _description = 'Base Scan Processor'

    def process_scan(self, picking, **kwargs):
        """Template method for processing scans"""
        self._validate_picking_state(picking)
        self._validate_scan_specific(picking, **kwargs)
        
        scan_history = self._create_scan_history(picking, **kwargs)
        self._process_images(scan_history, kwargs.get('images_data'))
        self._process_move_confirmations(scan_history, kwargs.get('move_line_confirms'))
        
        return True

    def _validate_picking_state(self, picking):
        """Base validation for picking state"""
        if picking.state in ['done', 'cancel']:
            raise ValidationError(f"Không thể quét QR cho phiếu có trạng thái '{picking.state}'")

    def _validate_scan_specific(self, picking, **kwargs):
        """Override in subclasses for specific validation"""
        pass

    def _create_scan_history(self, picking, **kwargs):
        """Create scan history record"""
        scan_vals = {
            'picking_id': picking.id,
            'scan_type': self._get_scan_type(),
            'scan_note': kwargs.get('scan_note'),
        }
        
        # Add specific fields
        scan_vals.update(self._get_specific_scan_vals(**kwargs))
        
        return self.env['stock.picking.scan.history'].create(scan_vals)

    def _get_scan_type(self):
        """Override in subclasses"""
        raise NotImplementedError

    def _get_specific_scan_vals(self, **kwargs):
        """Override in subclasses for specific fields"""
        return {}

    def _process_images(self, scan_history, images_data):
        if not images_data:
            return
        """Process and save images"""
        if images_data:
            scan_history.save_images(images_data)

    def _process_move_confirmations(self, scan_history, move_line_confirms):
        """Process move line confirmations"""
        if move_line_confirms and self._supports_move_confirmations():
            self._create_move_line_confirms(scan_history, move_line_confirms)
            self._update_moves_quantity(scan_history.picking_id, move_line_confirms)

    def _supports_move_confirmations(self):
        """Override in subclasses that support move confirmations"""
        return False

    def _create_move_line_confirms(self, scan_history, move_line_confirms):
        """Create move line confirmations"""
        for confirm in move_line_confirms:
            self.env['stock.move.line.confirm'].create({
                'scan_history_id': scan_history.id,
                'move_id': confirm['move_id'],
                'product_id': confirm['product_id'],
                'quantity_confirmed': confirm['quantity_confirmed'],
                'confirm_note': confirm['confirm_note'],
            })

    def _update_moves_quantity(self, picking, move_line_confirms):
        """Update quantity in stock.move"""
        move_confirmed_qty = {}
        for confirm in move_line_confirms:
            move_id = confirm['move_id']
            move_confirmed_qty.setdefault(move_id, 0)
            move_confirmed_qty[move_id] += confirm['quantity_confirmed']
        
        for move_id, confirmed_qty in move_confirmed_qty.items():
            move = self.env['stock.move'].browse(move_id)
            if confirmed_qty != move.product_uom_qty:
                move.write({'quantity': confirmed_qty})
