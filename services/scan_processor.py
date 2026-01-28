from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class UniversalScanProcessor(models.TransientModel):
    _name = 'universal.scan.processor'
    _description = 'Universal Scan Processor Service'

    def get_processor(self, model_name, scan_type):
        """Factory method to get appropriate processor based on model and scan_type"""
        processors = {
            'stock.picking': {
                'prepare': 'stock.picking.prepare.processor',
                'shipping': 'stock.picking.shipping.processor',
                'receive': 'stock.picking.receive.processor',
                'checking': 'stock.picking.checking.processor',
            },
            'stock.location': {
                'kiemke': 'stock.location.inventory.processor',
            }
        }
        
        model_processors = processors.get(model_name)
        if not model_processors:
            raise ValidationError(f"Không hỗ trợ model: {model_name}")
            
        processor_model = model_processors.get(scan_type)
        if not processor_model:
            raise ValidationError(f"Không hỗ trợ loại scan '{scan_type}' cho model '{model_name}'")
        
        return self.env[processor_model].create({})

class StockPickingScanProcessor(models.TransientModel):
    _name = 'stock.picking.scan.processor'
    _description = 'Stock Picking Scan Processor Service (Deprecated - use universal.scan.processor)'

    def get_processor(self, scan_type):
        """Backward compatibility method"""
        universal_processor = self.env['universal.scan.processor']
        return universal_processor.get_processor('stock.picking', scan_type)

class BaseScanProcessor(models.AbstractModel):
    _name = 'base.scan.processor'
    _description = 'Base Scan Processor for All Models'

    def process_scan(self, record, **kwargs):
        """Template method for processing scans"""
        self._validate_record_state(record)
        self._validate_scan_specific(record, **kwargs)
        
        scan_history = self._create_scan_history(record, **kwargs)
        self._process_images(scan_history, kwargs.get('images_data'))
        self._process_additional_data(scan_history, **kwargs)
        
        # Auto-validate if requested or if it's picking prepare/package
        if kwargs.get('auto_validate', True):
            self._auto_validate(record, **kwargs)  # Pass kwargs để lấy scan_user_id
            
        return scan_history

    def _auto_validate(self, record, **kwargs):
        """Logic to auto-validate record after scan"""
        if not hasattr(record, 'button_validate'):
            return
            
        if record.state in ['done', 'cancel']:
            _logger.info("Skipping auto-validate: record %s already in state %s", record.name, record.state)
            return
        
        try:
            _logger.info("Auto-validating record %s (state: %s)", record.name, record.state)
            
            # Get user from scan_user_id if available (important for auth='none' APIs)
            user_id = kwargs.get('scan_user_id')
            if user_id:
                # Use sudo() with specified user to avoid "partner_id IN (false)" error
                record_with_user = record.sudo().with_user(user_id)
            else:
                # Fallback to sudo() without specific user
                record_with_user = record.sudo()
            
            record_with_user.button_validate()
            _logger.info("Auto-validation successful for %s", record.name)
        except Exception as e:
            _logger.error("Auto-validate failed for %s: %s", record.name, str(e), exc_info=True)
            raise  # Re-raise exception để transaction rollback đúng cách

    def _validate_record_state(self, record):
        """Base validation for record state - override in subclasses"""
        pass

    def _validate_scan_specific(self, record, **kwargs):
        """Override in subclasses for specific validation"""
        pass

    def _create_scan_history(self, record, **kwargs):
        """Create scan history record - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _create_scan_history")

    def _get_scan_type(self):
        """Override in subclasses"""
        raise NotImplementedError("Subclasses must implement _get_scan_type")

    def _process_images(self, scan_history, images_data):
        """Process and save images"""
        if images_data and hasattr(scan_history, 'save_images'):
            scan_history.save_images(images_data)

    def _process_additional_data(self, scan_history, **kwargs):
        """Process additional data - override in subclasses"""
        pass

class StockPickingBaseScanProcessor(BaseScanProcessor):
    _name = 'stock.picking.base.processor'
    _description = 'Base Scan Processor for Stock Picking'

    def _validate_record_state(self, picking):
        """Validate picking state"""
        if picking.state in ['done', 'cancel']:
            raise ValidationError(f"Không thể quét QR cho phiếu có trạng thái '{picking.state}'")

    def _create_scan_history(self, picking, **kwargs):
        """Create picking scan history record"""
        # Get user_id from kwargs (passed from API) or use env.user as fallback
        user_id = kwargs.get('scan_user_id')
        if not user_id:
            # Fallback to env.user, but use sudo to avoid singleton error
            user_id = self.env.user.id if self.env.user else 1
        
        scan_vals = {
            'picking_id': picking.id,
            'scan_type': self._get_scan_type(),
            'scan_note': kwargs.get('scan_note'),
            'scan_user_id': user_id,  # Explicitly set user
        }
        
        # Add specific fields
        scan_vals.update(self._get_specific_scan_vals(**kwargs))
        
        # Use sudo() to ensure creation works with auth='none'
        return self.env['stock.picking.scan.history'].sudo().create(scan_vals)

    def _get_specific_scan_vals(self, **kwargs):
        """Override in subclasses for specific fields"""
        return {}

    def _process_additional_data(self, scan_history, **kwargs):
        """Process move line confirmations for stock picking"""
        move_line_confirms = kwargs.get('move_line_confirms')
        if move_line_confirms and self._supports_move_confirmations():
            self._create_move_line_confirms(scan_history, move_line_confirms)
            self._update_moves_quantity(scan_history.picking_id, move_line_confirms)

    def _supports_move_confirmations(self):
        """Override in subclasses that support move confirmations"""
        return False

    def _create_move_line_confirms(self, scan_history, move_line_confirms):
        """Create move line confirmations"""
        for confirm_data in move_line_confirms:
            # Handle both move_id (single) and move_ids (array from grouping)
            move_ids = confirm_data.get('move_ids', [])
            if not move_ids:
                # Fallback for old format
                move_id = confirm_data.get('move_id')
                if move_id:
                    move_ids = [move_id]
            
            if not move_ids:
                continue
                
            # Get common data
            product_id = confirm_data.get('product_id')
            quantity_confirmed = float(confirm_data.get('quantity_confirmed', 0))
            line_note = confirm_data.get('line_note', '') or confirm_data.get('confirm_note', '')
            
            # Create confirmation for each move in the group
            for move_id in move_ids:
                self.env['stock.move.line.confirm'].sudo().create({
                    'scan_history_id': scan_history.id,
                    'move_id': move_id,
                    'product_id': product_id,
                    'quantity_confirmed': quantity_confirmed / len(move_ids),  # Split quantity evenly
                    'confirm_note': line_note,
                })

    def _update_moves_quantity(self, picking, move_line_confirms):
        """Update quantity in stock.move"""
        move_confirmed_qty = {}
        for confirm in move_line_confirms:
            # Handle both move_id and move_ids
            move_ids = confirm.get('move_ids', [])
            if not move_ids:
                move_id = confirm.get('move_id')
                if move_id:
                    move_ids = [move_id]
            
            quantity_confirmed = float(confirm.get('quantity_confirmed', 0))
            qty_per_move = quantity_confirmed / len(move_ids) if move_ids else 0
            
            for move_id in move_ids:
                move_confirmed_qty.setdefault(move_id, 0)
                move_confirmed_qty[move_id] += qty_per_move
        
        for move_id, confirmed_qty in move_confirmed_qty.items():
            move = self.env['stock.move'].browse(move_id)
            if move.exists():
                move.write({'quantity': confirmed_qty})

class StockLocationBaseScanProcessor(models.TransientModel):
    _name = 'stock.location.base.processor'
    _description = 'Base Scan Processor for Stock Location'

    # --- Common validation ---
    def _validate_record_state(self, location):
        """Check if location is active before scanning"""
        if not location.active:
            raise ValidationError(f"Không thể quét QR cho vị trí không hoạt động: {location.name}")

    # --- Common scan history creation ---
    def _create_scan_history(self, location, scan_type, **kwargs):
        """Create a new scan history record"""
        scan_vals = {
            'location_id': location.id,
            'scan_type': self._get_scan_type(),
            'scan_note': kwargs.get('scan_note'),
            'user_id': kwargs.get('scan_user_id', self.env.user.id if self.env.user else 1),
            'scan_date': fields.Datetime.now(),
        }
        history = self.env['stock.location.scan.history'].create(scan_vals)
        return history

    # --- Hook for additional processing (subclasses override) ---
    def _process_additional_data(self, scan_history, **kwargs):
        """Process extra data (e.g. inventory counts, delivery info, etc.)"""
        data = kwargs.get('data')
        if data:
            return self._process_specific(scan_history, data)
        return None

    def _process_specific(self, scan_history, data):
        """To be implemented by subclasses (inventory, inbound, outbound, etc.)"""
        raise NotImplementedError("Subclasses must implement _process_specific()")
