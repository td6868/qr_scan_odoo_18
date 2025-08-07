from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    qr_code_image = fields.Binary("QR Code", attachment=True)
    qr_code_data = fields.Char("QR Code Content")
    #truong moi lich su chuan bi
    scan_history_ids = fields.One2many('stock.picking.scan.history', 'picking_id', string="Lịch sử quét QR")
    is_scanned = fields.Boolean("Đã quét", compute='_compute_is_scanned', store=True, default=False, copy=False)
    
    # Thêm trường mới cho loại vận chuyển
    shipping_type = fields.Selection([
        ('pickup', 'Khách đến lấy hàng'),
        ('viettelpost', 'Viettel Post'),
        ('delivery', 'Đặt ship : Xe khách/Xe ...')
    ], string="Loại vận chuyển", default='pickup')
    shipping_image = fields.Binary("Ảnh đơn hàng chuyển đi", attachment=True, default=False)
    shipping_date = fields.Datetime("Ngày vận chuyển", readonly=True, default=False)
    shipping_note = fields.Text("Ghi chú vận chuyển",default=False)
    shipping_phone = fields.Text("Số điện thoại giao vận", default=False)
    shipping_company = fields.Text("Nhà xe", default=False)
    is_shipped = fields.Boolean("Đã vận chuyển", default=False, readonly=True)
    
    # Thêm trường last_scan_date
    last_scan_date = fields.Datetime("Ngày quét cuối cùng", compute='_compute_last_scan_date', store=True)
    
    # Thêm trường move_line_confirmed_ids
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm',compute='_compute_move_line_confirmed_ids', string="Xác nhận sản phẩm")
    
    # Các trường liên kết với scan_history_ids mới nhất
    scan_date = fields.Datetime(related='scan_history_ids.scan_date', string="Ngày quét", readonly=True)
    scan_user_id = fields.Many2one(related='scan_history_ids.scan_user_id', string="Người quét", readonly=True)
    scan_note = fields.Text(related='scan_history_ids.scan_note', string="Ghi chú khi quét", readonly=True)
    image_proof = fields.Binary(related='scan_history_ids.image_proof', string="Ảnh chứng minh", readonly=True)
    
    def create(self, vals):
        picking = super().create(vals)
        # Không generate QR ngay khi tạo vì có thể chưa có đủ thông tin
        return picking

    def _generate_qr_code(self):
        """Tạo QR code cho picking nếu chưa có hoặc data đã thay đổi"""
        for record in self:
            qr_data = f"Picking: {record.name}\n"
            qr_data += f"Customer: {record.partner_id.name or 'N/A'}\n"
            qr_data += f"Date: {record.scheduled_date}\n"
            qr_data += f"ID: {record.id}\n"
                
            if not record.qr_code_image or record.qr_code_data != qr_data:
                record.qr_code_data = qr_data

                # Tạo mã QR từ qr_data
                qr = qrcode.QRCode(
                    version=3,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=8,  # Giảm box_size để QR không quá to
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                qr_img.save(buffer, format="PNG")
                qr_code_base64 = base64.b64encode(buffer.getvalue())
                
                # Reset trạng thái quét khi QR mới được tạo
                record.update({
                    'qr_code_image': qr_code_base64,
                })
                

    @api.depends('scan_history_ids.scan_date')
    def _compute_last_scan_date(self):
        for record in self:
            if record.scan_history_ids:
                record.last_scan_date = max(record.scan_history_ids.mapped('scan_date'))
            else:
                record.last_scan_date = False

    @api.depends('scan_history_ids')
    def _compute_is_scanned(self):
        for record in self:
            record.is_scanned = bool(record.scan_history_ids)
    def action_done(self):
        """Override action_done để tạo QR khi picking được hoàn thành"""
        result = super().action_done()
        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        """Đảm bảo QR được tạo trước khi in báo cáo"""
        pickings = self.browse(docids)
        pickings._generate_qr_code()
        return super()._get_report_values(docids, data)

    # Thêm phương thức này vào class StockPicking
    def action_print_picking(self):
        """Gọi khi người dùng nhấn nút in"""
        self._generate_qr_code()
        return self.env.ref('khoakim_18.action_report_stock_pick_customize').report_action(self)
    
    def get_current_user_info(self):
        """Method để lấy thông tin user hiện tại"""
        return {
            'user_id': self.env.user.id,
            'user_name': self.env.user.name,
            'login': self.env.user.login,
        }
    
    def update_scan_info(self, image_proof=None, scan_note=None, move_line_confirms=None, shipping_type=None, shipping_image=None, shipping_note=None, shipping_phone=None, shipping_company=None):
        """Method để cập nhật thông tin scan và/hoặc thông tin vận chuyển"""
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(f"Không thể quét QR cho phiếu có trạng thái '{self.state}'")
        
        vals = {}
        
        # Tạo lịch sử quét mới nếu có thông tin scan
        if image_proof is not None or move_line_confirms:
            scan_history = self.env['stock.picking.scan.history'].create({
                'picking_id': self.id,
                'image_proof': image_proof,
                'scan_note': scan_note,
            })
            # Tạo xác nhận sản phẩm cho lần quét này
            if move_line_confirms:
                self._create_move_line_confirms(scan_history.id, move_line_confirms)
                # Cập nhật số lượng trong stock.move
                move_confirmed_qty = {}
                for confirm in move_line_confirms:
                    move_line = self.env['stock.move.line'].browse(confirm['move_line_id'])
                    if move_line.exists():
                        move_id = move_line.move_id.id
                        if move_id not in move_confirmed_qty:
                            move_confirmed_qty[move_id] = 0
                        move_confirmed_qty[move_id] += confirm['quantity_confirmed']
                self._update_moves_quantity(move_confirmed_qty)
        
        # Cập nhật thông tin vận chuyển nếu có
        if shipping_type is not None:
            vals.update({
                'shipping_type': shipping_type,
                'is_shipped': True,
                'shipping_date': fields.Datetime.now(),
            })
            
        if shipping_image is not None:
            vals['shipping_image'] = shipping_image
            
        if shipping_note is not None:
            vals['shipping_note'] = shipping_note
        
        if shipping_phone is not None:
            vals['shipping_phone'] = shipping_phone
            
        if shipping_company is not None:
            vals['shipping_company'] = shipping_company
        
        if vals:  # Chỉ ghi nếu có giá trị cần cập nhật
            self.write(vals) 
        
        return True
    
    def _create_move_line_confirms(self, scan_history_id, move_line_confirms):
        """Tạo xác nhận sản phẩm cho lần quét"""
        for confirm in move_line_confirms:
            if not confirm.get('is_confirmed', False):
                confirm['quantity_confirmed'] = 0
            # Sử dụng move_id thay vì move_line_id
            self.env['stock.move.line.confirm'].create({
                'scan_history_id': scan_history_id,
                'move_id': confirm['move_id'],  # Thay đổi này
                'product_id': confirm['product_id'],
                'quantity_confirmed': confirm['quantity_confirmed'],
                'is_confirmed': confirm['is_confirmed'],
                'confirm_note': confirm['confirm_note'],
                
            })            

    def update_move_line_confirm(self, confirmed_lines):
        """Cập nhật xác nhận move lines - phiên bản đơn giản và cập nhật quantity"""
        
        if not confirmed_lines:
            return {'status': 'error', 'message': 'Không có dữ liệu xác nhận'}
        
        move_ids = [line['move_id'] for line in confirmed_lines]
        moves = self.env['stock.move'].browse(move_ids).with_context(active_test=False)
        
        # Kiểm tra tất cả moves có thuộc phiếu xuất kho này không
        invalid_moves = moves.filtered(lambda m: m.picking_id.id != self.id)
        if invalid_moves:
            raise ValidationError(
                f"Một số sản phẩm không thuộc phiếu xuất kho này: {', '.join(invalid_moves.mapped('product_id.name'))}"
            )
        
        confirm_vals = []
        for line in confirmed_lines:
            move_id = line.get('move_id')
            quantity = float(line.get('quantity_confirmed', 0.0))
            note = line.get('confirm_note', '')
            is_confirmed = line.get('is_confirmed', False)

            move = moves.filtered(lambda m: m.id == move_id)
            if not move:
                continue

            if quantity > move.product_uom_qty:
                raise ValidationError(
                    f"Sản phẩm '{move.product_id.display_name}' xác nhận {quantity} vượt quá nhu cầu {move.product_uom_qty}"
                )

            # Tạo bản ghi xác nhận
            confirm_vals.append({
                'move_id': move_id,
                'product_id': move.product_id.id,
                'quantity_confirmed': quantity,
                'confirm_note': note,
                'confirm_user_id': self.env.uid,
                'confirm_date': fields.Datetime.now(),
                'is_confirmed': is_confirmed,
            })

            # ✅ Cập nhật lại trường quantity nếu đã được confirm
            if is_confirmed:
                move.write({'quantity': quantity})

        if confirm_vals:
            self.env['stock.move.line.confirm'].create(confirm_vals)

        return {'status': 'success', 'message': 'Đã xác nhận và cập nhật số lượng thành công'}

    
    def _update_moves_quantity(self, move_confirmed_qty):
        """Cập nhật quantity trong stock.move"""
        for move_id, confirmed_qty in move_confirmed_qty.items():
            move = self.env['stock.move'].browse(move_id)
            
            if confirmed_qty != move.product_uom_qty:
                move.write({
                    # 'product_uom_qty': move.product_uom_qty - confirmed_qty,
                    'quantity': confirmed_qty,
                })

    @api.depends('scan_history_ids.move_line_confirmed_ids')
    def _compute_move_line_confirmed_ids(self):
        for record in self:
            record.move_line_confirmed_ids = record.scan_history_ids.mapped('move_line_confirmed_ids')

class StockMoveLineConfirm(models.Model):
    _name = 'stock.move.line.confirm'
    _description = 'Xác nhận sản phẩm trong phiếu xuất kho'
    
    scan_history_id = fields.Many2one('stock.picking.scan.history', string="Lịch sử quét", required=True, ondelete='cascade')
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất kho", related='scan_history_id.picking_id', store=True)
    move_id = fields.Many2one('stock.move', string="Sản phẩm", required=True, ondelete='cascade')  # Thay đổi chính
    product_id = fields.Many2one('product.product', string="Sản phẩm", required=True)
    quantity_confirmed = fields.Float("Số lượng xác nhận", default=0.0)
    is_confirmed = fields.Boolean("Đã xác nhận", default=False)
    confirm_note = fields.Text("Ghi chú xác nhận")
    confirm_date = fields.Datetime("Ngày xác nhận", default=fields.Datetime.now)
    confirm_user_id = fields.Many2one('res.users', "Người xác nhận", default=lambda self: self.env.user.id)
    
    # Computed fields
    move_quantity = fields.Float(
        "Số lượng nhu cầu", 
        related='move_id.product_uom_qty',
        readonly=True
    )
    
    product_name = fields.Char(
        "Tên sản phẩm", 
        related='product_id.name', 
        readonly=True
    )
    
    difference_quantity = fields.Float(
        "Chênh lệch", 
        compute='_compute_difference_quantity',
        store=True
    )
    
    @api.depends('move_id.product_uom_qty', 'quantity_confirmed')
    def _compute_difference_quantity(self):
        for record in self:
            if record.move_id:
                record.difference_quantity = record.move_id.product_uom_qty - record.quantity_confirmed
            else:
                record.difference_quantity = 0
    
    @api.constrains('quantity_confirmed')
    def _check_quantity_confirmed(self):
        for record in self:
            if record.quantity_confirmed < 0:
                raise ValidationError("Số lượng xác nhận không được âm!")

    @api.constrains('move_id', 'quantity_confirmed')
    def _check_quantity_vs_move(self):
        for record in self:
            if record.move_id and record.quantity_confirmed > record.move_id.product_uom_qty:
                raise ValidationError(
                    f"Số lượng xác nhận ({record.quantity_confirmed}) không được vượt quá "
                    f"nhu cầu ({record.move_id.product_uom_qty})"
                )
    
    def name_get(self):
        """Hiển thị tên có ý nghĩa"""
        result = []
        for record in self:
            name = f"{record.product_id.name} - {record.quantity_confirmed}"
            result.append((record.id, name))
        return result

    @api.onchange('move_id')
    def _onchange_move_id(self):
        """Auto fill product khi chọn move"""
        if self.move_id:
            self.product_id = self.move_id.product_id.id
            self.quantity_confirmed = self.move_id.product_uom_qty
            
class StockPickingScanHistory(models.Model):
    _name = 'stock.picking.scan.history'
    _description = 'Lịch sử quét QR chuẩn bị hàng'
    _order = 'scan_date desc'
    
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất kho", required=True, ondelete='cascade')
    image_proof = fields.Binary("Ảnh chứng minh", attachment=True)
    scan_date = fields.Datetime("Ngày quét", default=fields.Datetime.now)
    scan_user_id = fields.Many2one('res.users', "Người quét", default=lambda self: self.env.user.id)
    scan_note = fields.Text("Ghi chú khi quét")
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm', 'scan_history_id', string="Xác nhận sản phẩm", ondelete='cascade')