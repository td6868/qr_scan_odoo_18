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
    ], string="Loại vận chuyển", default='pickup', compute='_compute_shipping_info')
    shipping_date = fields.Datetime("Ngày vận chuyển", compute='_compute_shipping_info', readonly=True, default=False)
    shipping_note = fields.Text("Ghi chú vận chuyển",default=False,compute='_compute_shipping_info')
    is_shipped = fields.Boolean("Đã vận chuyển", default=False, readonly=True,compute='_compute_shipping_info')
    
    # Thêm trường last_scan_date
    # last_scan_date = fields.Datetime("Ngày quét cuối cùng", compute='_compute_last_scan_date', store=True)
    
    # Thêm trường move_line_confirmed_ids
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm',compute='_compute_move_line_confirmed_ids', string="Xác nhận sản phẩm")
    
    # Các trường liên kết với scan_history_ids mới nhất
    # scan_date = fields.Datetime(related='scan_history_ids.scan_date', string="Ngày quét", readonly=True)
    scan_user_id = fields.Many2one('res.users', string="Người quét", compute="_compute_shipping_info",)
    scan_note = fields.Text(string="Ghi chú", compute="_compute_shipping_info",)
    # prepare_image_count = fields.Integer("Số ảnh chuẩn bị", compute='_compute_prepare_image_count')
    # first_prepare_image = fields.Binary("Ảnh chuẩn bị đầu tiên", compute='_compute_first_prepare_image')
    
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
                

    @api.depends('scan_history_ids')
    def _compute_is_scanned(self):
        for record in self:
            record.is_scanned = bool(record.scan_history_ids)
            
    @api.depends('scan_history_ids.scan_type', 'scan_history_ids.shipping_type')
    def _compute_shipping_info(self):
        for record in self:
            shipping_history = record.scan_history_ids.filtered(lambda h: h.scan_type == 'shipping')
            if shipping_history:
                latest_shipping = shipping_history[0]  # Đã sort theo scan_date desc
                record.is_shipped = True
                record.shipping_date = latest_shipping.scan_date
                record.shipping_note = latest_shipping.scan_note
                record.shipping_type = latest_shipping.shipping_type
                record.scan_user_id = latest_shipping.scan_user_id
                record.scan_note = latest_shipping.scan_note
            else:
                record.is_shipped = False
                record.shipping_date = False
                record.shipping_note = False
                record.shipping_type = False
                record.scan_note = False
                record.scan_user_id = False
                
       
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
        
    @api.depends('scan_history_ids.attachment_ids')
    def _compute_prepare_image_count(self):
        for record in self:
            record.prepare_image_count = sum(len(history.attachment_ids) for history in record.scan_history_ids)

    @api.depends('scan_history_ids.attachment_ids')
    def _compute_first_prepare_image(self):
        for record in self:
            first_image = False
            for history in record.scan_history_ids:
                if history.attachment_ids:
                    first_image = history.attachment_ids[0].datas
                    break
            record.first_prepare_image = first_image

    def get_all_prepare_images(self):
        """Lấy tất cả ảnh chuẩn bị hàng"""
        images = []
        for history in self.scan_history_ids:
            for attachment in history.attachment_ids:
                images.append({
                    'id': attachment.id,
                    'name': attachment.name,
                    'datas': attachment.datas,
                    'create_date': attachment.create_date,
                    'description': attachment.description,
                })
        return images
           
    def update_scan_info(self, images_data=None, scan_note=None, move_line_confirms=None, 
                    scan_type='prepare', shipping_type=None, 
                    shipping_phone=None, shipping_company=None):        
        """Method để cập nhật thông tin scan"""
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(f"Không thể quét QR cho phiếu có trạng thái '{self.state}'")
        
        # Tạo scan_history record
        scan_vals = {
            'picking_id': self.id,
            'scan_type': scan_type,
            'scan_note': scan_note,
        }
        
        # Thêm thông tin shipping nếu là shipping scan
        if scan_type == 'shipping':
            scan_vals.update({
                'shipping_type': shipping_type,
                'shipping_phone': shipping_phone,
                'shipping_company': shipping_company,
            })
        
        scan_history = self.env['stock.picking.scan.history'].create(scan_vals)
        
        # Lưu ảnh
        if images_data:
            scan_history.save_images(images_data)
                
        # Xử lý move_line_confirms (chỉ cho prepare scan)
        if move_line_confirms and scan_type == 'prepare':
            self._create_move_line_confirms(scan_history.id, move_line_confirms)
            move_confirmed_qty = {}
            for confirm in move_line_confirms:
                move_line = self.env['stock.move.line'].browse(confirm['move_line_id'])
                if move_line.exists():
                    move_id = move_line.move_id.id
                    if move_id not in move_confirmed_qty:
                        move_confirmed_qty[move_id] = 0
                    move_confirmed_qty[move_id] += confirm['quantity_confirmed']
            self._update_moves_quantity(move_confirmed_qty)
        
        return True
       
    def _create_move_line_confirms(self, scan_history_id, move_line_confirms):
        """Tạo xác nhận sản phẩm cho lần quét"""
        for confirm in move_line_confirms:
            # if not confirm.get('is_confirmed', False):
            #     confirm['quantity_confirmed'] = 0
            # Sử dụng move_id thay vì move_line_id
            self.env['stock.move.line.confirm'].create({
                'scan_history_id': scan_history_id,
                'move_id': confirm['move_id'],  # Thay đổi này
                'product_id': confirm['product_id'],
                'quantity_confirmed': confirm['quantity_confirmed'],
                # 'is_confirmed': confirm['is_confirmed'],
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
            # is_confirmed = line.get('is_confirmed', False)

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
                # 'is_confirmed': is_confirmed,
            })

            # ✅ Cập nhật lại trường quantity nếu đã được confirm
            # if is_confirmed:
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
    # is_confirmed = fields.Boolean("Đã xác nhận", default=False)
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
    _description = 'Lịch sử quét QR'
    _order = 'scan_date desc'
    
    # Thêm trường phân loại scan
    scan_type = fields.Selection([
        ('prepare', 'Chuẩn bị hàng'),
        ('shipping', 'Vận chuyển')
    ], string="Loại quét", required=True, default='prepare')
    
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất kho", required=True, ondelete='cascade')
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        string='Ảnh chứng minh',
        domain=[('res_model', '=', 'stock.picking.scan.history')],
        auto_join=True
    )
    image_count = fields.Integer("Số lượng ảnh", compute='_compute_image_count')
    
    scan_date = fields.Datetime("Ngày quét", default=fields.Datetime.now)
    scan_user_id = fields.Many2one('res.users', "Người quét", default=lambda self: self.env.user.id)
    scan_note = fields.Text("Ghi chú khi quét")
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm', 'scan_history_id', string="Xác nhận sản phẩm", ondelete='cascade')   
    
    # Các trường shipping chuyển từ stock.picking sang
    shipping_type = fields.Selection([
        ('pickup', 'Khách đến lấy hàng'),
        ('viettelpost', 'Viettel Post'),
        ('delivery', 'Đặt ship : Xe khách/Xe ...')
    ], string="Loại vận chuyển")
    shipping_phone = fields.Text("Số điện thoại giao vận")
    shipping_company = fields.Text("Nhà xe") 
    
    @api.depends('attachment_ids')
    def _compute_image_count(self):
        for record in self:
            record.image_count = len(record.attachment_ids)
    
    def save_images(self, images_data):
        """Lưu nhiều ảnh chuẩn bị vào ir.attachment"""
        attachments = []
        for i, img_data in enumerate(images_data):
            if not img_data.get('data'):
                continue
                
            attachment = self.env['ir.attachment'].create({
                'name': img_data.get('name', f'Prepare_Image_{i+1}_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'),
                'type': 'binary',
                'datas': img_data['data'],
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'image/jpeg',
                'description': img_data.get('description', f'Ảnh minh chứng chuẩn bị hàng #{i+1}'),
            })
            attachments.append(attachment.id)
        return attachments