from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    qr_code_image = fields.Binary("QR Code", attachment=True)
    qr_code_data = fields.Char("QR Code Content")
    image_proof = fields.Binary("Ảnh chứng minh", attachment=True)
    scan_date = fields.Datetime("Ngày quét", readonly=True)
    scan_user_id = fields.Many2one('res.users', "Người quét", readonly=True)
    scan_note = fields.Text("Ghi chú khi quét")
    is_scanned = fields.Boolean("Đã quét", default=False, readonly=True)
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm', 'picking_id', string="Xác nhận sản phẩm")
    
    # Thêm trường mới cho loại vận chuyển
    shipping_type = fields.Selection([
        ('pickup', 'Khách đến lấy hàng'),
        ('viettelpost', 'Viettel Post'),
        ('delivery', 'Đặt ship : Xe khách/Xe ...')
    ], string="Loại vận chuyển", default='pickup')
    shipping_image = fields.Binary("Ảnh đơn hàng chuyển đi", attachment=True)
    shipping_date = fields.Datetime("Ngày vận chuyển", readonly=True)
    shipping_note = fields.Text("Ghi chú vận chuyển")
    shipping_phone = fields.Text("Số điện thoại giao vận")
    shipping_company = fields.Text("Nhà xe")
    is_shipped = fields.Boolean("Đã vận chuyển", default=False, readonly=True)

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
                
                # Thêm danh sách sản phẩm
                # qr_data += "Products:\n"
                # for move in record.move_ids_without_package:
                #     product_name = move.product_id.name or move.sale_line_id.name
                #     quantity = move.product_uom_qty
                #     uom = move.product_uom.name
                #     qr_data += f"- {product_name}: {quantity} {uom}\n"
                
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
                    'is_scanned': False,
                    'scan_date': False,
                    'scan_user_id': False,
                    'scan_note': False,
                    'image_proof': False,
                    'is_shipped' : False,
                    'shipping_date' : False,
                    'shipping_note' : False,
                    'shipping_phone' :False,
                    'shipping_company' : False,
                    'shipping_image' : False,
                    'shipping_type' : False,
                })

    def action_done(self):
        """Override action_done để tạo QR khi picking được hoàn thành"""
        result = super().action_done()
        self._generate_qr_code()
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
    
    def update_scan_info(self, image_proof=None, scan_note=None, shipping_type=None, shipping_image=None, shipping_note=None, shipping_phone=None,shipping_company=None):
        """Method để cập nhật thông tin scan và/hoặc thông tin vận chuyển"""
        self.ensure_one()
        vals = {}
        
        # Cập nhật thông tin scan nếu có
        if image_proof is not None:
            vals.update({
                'image_proof': image_proof,
                'scan_note': scan_note,
                'is_scanned': True,
                'scan_date': fields.Datetime.now(),
                'scan_user_id': self.env.user.id,
            })
        
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
            
    
    def update_move_line_confirm(self, move_line_confirms):
        """Method để cập nhật thông tin xác nhận sản phẩm"""
        self.ensure_one()
        
        # Dictionary để track số lượng xác nhận theo move_id
        move_confirmed_qty = {}
        
        # XỬ LÝ LOGIC TRƯỚC KHI XÓA/TẠO RECORDS
        for confirm in move_line_confirms:
            # Nếu không tick chọn, force quantity_confirmed = 0
            if not confirm.get('is_confirmed', False):
                confirm['quantity_confirmed'] = 0
                
            # LẤY MOVE TỪ MOVE_LINE
            move_line = self.env['stock.move.line'].browse(confirm['move_line_id'])
            if move_line.exists():  # Kiểm tra move_line có tồn tại
                move_id = move_line.move_id.id
                
                # Cộng dồn số lượng theo move_id
                if move_id not in move_confirmed_qty:
                    move_confirmed_qty[move_id] = 0
                move_confirmed_qty[move_id] += confirm['quantity_confirmed']
        
        # CẬP NHẬT STOCK.MOVE TRƯỚC
        self._update_moves_quantity(move_confirmed_qty)
        
        # SAU ĐÓ MỚI XÓA CÁC XÁC NHẬN CŨ
        self.move_line_confirmed_ids.unlink()
        
        # CUỐI CÙNG TẠO CÁC XÁC NHẬN MỚI
        for confirm in move_line_confirms:
            # Kiểm tra move_line vẫn tồn tại sau khi cập nhật
            move_line = self.env['stock.move.line'].browse(confirm['move_line_id'])
            if move_line.exists():
                self.env['stock.move.line.confirm'].create({
                    'picking_id': self.id,
                    'move_line_id': confirm['move_line_id'],
                    'product_id': confirm['product_id'],
                    'quantity_confirmed': confirm['quantity_confirmed'],
                    'is_confirmed': confirm['is_confirmed'],
                    'confirm_note': confirm['confirm_note'],
                })
        
        return True
    
    def _update_moves_quantity(self, move_confirmed_qty):
        """Cập nhật quantity trong stock.move"""
        for move_id, confirmed_qty in move_confirmed_qty.items():
            move = self.env['stock.move'].browse(move_id)
            
            if confirmed_qty != move.product_uom_qty:
                move.write({
                    # 'product_uom_qty': move.product_uom_qty - confirmed_qty,
                    'quantity': confirmed_qty,
                })


class StockMoveLineConfirm(models.Model):
    _name = 'stock.move.line.confirm'
    _description = 'Xác nhận sản phẩm trong phiếu xuất kho'
    
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất kho", required=True, ondelete='cascade')
    move_line_id = fields.Many2one('stock.move.line', string="Chi tiết sản phẩm", required=True)
    product_id = fields.Many2one('product.product', string="Sản phẩm", required=True)
    quantity_confirmed = fields.Float("Số lượng xác nhận", default=0.0)
    is_confirmed = fields.Boolean("Đã xác nhận", default=False)
    confirm_note = fields.Text("Ghi chú xác nhận")
    confirm_date = fields.Datetime("Ngày xác nhận", default=fields.Datetime.now)
    confirm_user_id = fields.Many2one('res.users', "Người xác nhận", default=lambda self: self.env.user.id)
    
    # Computed fields
    move_line_quantity = fields.Float(
        "Số lượng move line", 
        related='move_line_id.quantity', 
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
    
    @api.depends('move_line_id.quantity', 'quantity_confirmed')
    def _compute_difference_quantity(self):
        for record in self:
            if record.move_line_id:
                record.difference_quantity = record.move_line_id.quantity - record.quantity_confirmed
            else:
                record.difference_quantity = 0
    
    @api.constrains('quantity_confirmed')
    def _check_quantity_confirmed(self):
        for record in self:
            if record.quantity_confirmed < 0:
                raise ValidationError("Số lượng xác nhận không được âm!")

    @api.constrains('move_line_id', 'quantity_confirmed')
    def _check_quantity_vs_move_line(self):
        for record in self:
            if record.move_line_id and record.quantity_confirmed > record.move_line_id.quantity:
                raise ValidationError(
                    f"Số lượng xác nhận ({record.quantity_confirmed}) không được vượt quá "
                    f"số lượng trong move line ({record.move_line_id.quantity})"
                )
    
    def name_get(self):
        """Hiển thị tên có ý nghĩa"""
        result = []
        for record in self:
            name = f"{record.product_id.name} - {record.quantity_confirmed}"
            result.append((record.id, name))
        return result

    @api.onchange('move_line_id')
    def _onchange_move_line_id(self):
        """Auto fill product khi chọn move line"""
        if self.move_line_id:
            self.product_id = self.move_line_id.product_id.id
            self.quantity_confirmed = self.move_line_id.quantity
            
