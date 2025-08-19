from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError

class ProductOrderChina(models.Model):
    _inherit = 'product.order.china'
    
    qr_code_image = fields.Binary("QR code", attachment=True)
    qr_code_data  = fields.Char("QR code data")
    
    scan_history_ids = fields.One2many('stock.picking.scan.history', 'picking_id', string="Lịch sử quét")
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm',compute='_compute_move_line_confirmed_ids', string="Xác nhận sản phẩm")
    scan_user_id = fields.Many2one('res.users', string="Người quét", compute="_compute_shipping_info",)
    scan_note = fields.Char(string="Ghi chú", compute="_compute_shipping_info",)
    shipping_type = fields.Selection([
        ('pickup', 'Đến lấy hàng'),
        ('viettelpost', 'CPN/ViettelPost'),
        ('delivery', 'Gửi xe hàng'),
        ('other', 'Khác')
    ], string="Loại vận chuyển", default='pickup', compute='_compute_shipping_info')
    shipping_date = fields.Datetime("Ngày vận chuyển", compute='_compute_shipping_info', readonly=True, default=False)
    shipping_note = fields.Char("Ghi chú vận chuyển",default=False,compute='_compute_shipping_info')
    is_shipped = fields.Boolean("Đã vận chuyển", default=False, readonly=True,compute='_compute_shipping_info')

    def create(self, vals):
        picking = super().create(vals)
        return picking

    def _generate_qr_code(self):
        for record in self:
            qr_data = f"Model: product.order.china\n"
            qr_data =f"Kiện hàng: {record.name}\n"
            qr_data +=f"ID: {record.id}\n"
            
            if not record.qr_code_data or record.qr_code_data != qr_data:
                record.qr_code_data = qr_data

                # Tạo QR code
                qr = qrcode.QRCode(
                    version=3,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                qr_img.save(buffer, format="PNG")
                qr_code_base64 = base64.b64encode(buffer.getvalue())
                
                record.update({
                    'qr_code_image': qr_code_base64,
                })
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
    
    def action_print_picking(self):
        """Gọi khi người dùng nhấn nút in"""
        return self.env.ref('qr_scan_odoo_18.action_report_purchase_order_china').report_action(self)
    
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
                    scan_type='receive', shipping_type=None, 
                    shipping_phone=None, shipping_company=None):        
        """Method để cập nhật thông tin scan"""
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(f"Không thể quét QR cho phiếu có trạng thái '{self.state}'")
        
        # Tạo scan_history record
        scan_vals = {
            'order_id': self.id,
            'scan_type': scan_type,
            'scan_note': scan_note,
        }
        
        # Thêm thông tin shipping nếu là shipping scan
        if scan_type == 'receive':
            scan_vals.update({
                'shipping_type': shipping_type,
                'shipping_phone': shipping_phone,
                'shipping_company': shipping_company,
            })
        
        scan_history = self.env['product.order.china.scan.history'].create(scan_vals)
        
        # Lưu ảnh
        if images_data:
            scan_history.save_images(images_data)
                
        # Xử lý move_line_confirms (cho checking scan)
        if move_line_confirms and scan_type == 'checking':
            self._create_order_line_confirms(scan_history.id, move_line_confirms)
            order_confirmed_qty = {}
            for confirm in move_line_confirms:
                order_line_id = confirm['order_line_id']
                order_confirmed_qty.setdefault(order_line_id, 0)
                order_confirmed_qty[order_line_id] += confirm['quantity_checked']
            self._update_order_lines_quantity(order_confirmed_qty)
        
        return True
    
    def _create_order_line_confirms(self, scan_history_id, order_line_confirms):
        """Tạo xác nhận sản phẩm cho lần quét nhập kho (checking)."""
        for confirm in order_line_confirms:
            self.env['product.order.china.line.confirm'].create({
                'scan_history_id': scan_history_id,              # Gắn vào lịch sử quét
                'order_line_id': confirm['order_line_id'],       # Dòng sản phẩm của đơn nhập
                'product_id': confirm['product_id'],             # Sản phẩm
                'quantity_checked': confirm['quantity_checked'], # Số lượng đã kiểm
                'confirm_note': confirm.get('confirm_note', ''), # Ghi chú (nếu có)
            })
    def update_move_line_confirm(self, confirmed_lines):    
        """Cập nhật xác nhận move lines - phiên bản đơn giản và cập nhật quantity"""
        
        if not confirmed_lines:
            return {'status': 'error', 'message': 'Không có dữ liệu xác nhận'}
        
        order_ids = [line['order_line_id'] for line in confirmed_lines]

        orders = self.env['product.order.china'].browse(order_ids).with_context(active_test=False)
        
        # Kiểm tra tất cả orders có thuộc phiếu xuất kho này không
        invalid_orders = orders.filtered(lambda m: m.picking_id.id != self.id)
        if invalid_orders:
            raise ValidationError(
                f"Một số sản phẩm không thuộc phiếu xuất kho này: {', '.join(invalid_orders.mapped('product_id.name'))}"
            )
        
        confirm_vals = []
        for line in confirmed_lines:
            order_id = line.get('order_line_id')
            quantity = float(line.get('qty_purchase', 0.0))
            note = line.get('confirm_note', '')
            # is_confirmed = line.get('is_confirmed', False)

            order = orders.filtered(lambda m: m.id == order_line_id)
            if not order:
                continue

            if quantity > order.qty_purchase_order:
                raise ValidationError(
                    f"Sản phẩm '{order.product_id.display_name}' xác nhận {quantity} vượt quá nhu cầu {order.qty_purchase_order}"
                )

            # Tạo bản ghi xác nhận
            confirm_vals.append({
                'order_line_id': order_id,
                'product_id': order.product_id.id,
                'quantity_checked': qty_purchase,

                'confirm_note': note,
                'confirm_user_id': self.env.uid,
                'confirm_date': fields.Datetime.now(),
                # 'is_confirmed': is_confirmed,
            })

            # ✅ Cập nhật lại trường quantity nếu đã được confirm
            # if is_confirmed:
            order.write({'qty_purchase': quantity_checked})

        if confirm_vals:
            self.env['product.order.china.line.confirm'].create(confirm_vals)

        return {'status': 'success', 'message': 'Đã xác nhận và cập nhật số lượng thành công'}
    
    def _update_order_lines_quantity(self, order_confirmed_qty):
        """Cập nhật quantity trong stock.move"""
        for order_id, confirmed_qty in order_confirmed_qty.items():
            order = self.env['product.order.china'].browse(order_id)
            
            if confirmed_qty != order.qty_purchase_order:
                order.write({
                    # 'product_uom_qty': move.product_uom_qty - confirmed_qty,
                    'qty_purchase': confirmed_qty,
                })
class ProductOrderChinaLineConfirm(models.Model):
    _name = 'product.order.china.line.confirm'
    _description = 'Xác nhận sản phẩm nhập kho'

    scan_history_id = fields.Many2one('product.order.china.scan.history',string="Lịch sử quét",
        required=True,
        ondelete='cascade'
    )
    order_id = fields.Many2one(
        'product.order.china',
        string="Đơn nhập kho",
        related='scan_history_id.order_id',
        store=True
    )
    order_line_id = fields.Many2one(
        'product.order.china.line',
        string="Dòng sản phẩm",
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string="Sản phẩm",
        required=True
    )
    quantity_checked = fields.Float("Số lượng đã kiểm", default=0.0)
    confirm_note = fields.Char("Ghi chú kiểm hàng")
    confirm_date = fields.Datetime("Ngày xác nhận", default=fields.Datetime.now)
    confirm_user_id = fields.Many2one(
        'res.users', 
        string="Người xác nhận", 
        default=lambda self: self.env.user.id
    )

    # Computed fields
    order_quantity = fields.Float(
        "Số lượng đã đặt", 
        related='order_line_id.qty_purchase_order',
        readonly=True
    )
    
    product_name = fields.Char(
        "Tên sản phẩm",
        related='product_id.name',
        store=True
    )
    
    difference_quantity = fields.Float(
        "Chênh lệch", 
        compute='_compute_difference_quantity',
        store=True
    )

    @api.depends('order_line_id.product_qty', 'quantity_checked')
    def _compute_difference_quantity(self):
        for record in self:
            if record.order_line_id:
                record.difference_quantity = record.order_line_id.product_qty - record.quantity_checked
            else:
                record.difference_quantity = 0

    @api.constrains('quantity_checked')
    def _check_quantity_checked(self):
        for record in self:
            if record.quantity_checked < 0:
                raise ValidationError("Số lượng đã kiểm không được âm!")

    @api.constrains('order_line_id', 'quantity_checked')
    def _check_quantity_vs_order(self):
        for record in self:
            if record.order_line_id and record.quantity_checked > record.order_line_id.qty_purchase_order:
                raise ValidationError(
                    f"Số lượng kiểm ({record.quantity_checked}) không được vượt quá "
                    f"yêu cầu ({record.order_line_id.qty_purchase_order})"
                )

    @api.onchange('order_line_id')
    def _onchange_order_line_id(self):
        """Auto fill product khi chọn dòng sản phẩm"""
        if self.order_line_id:
            self.product_id = self.order_line_id.product_id.id
            self.quantity_checked = self.order_line_id.qty_purchase_order

class StockPickingScanHistory(models.Model):
    _name = 'product.order.china.scan.history'
    _description = 'Lịch sử quét QR'
    _order = 'scan_date desc'
    
    # Thêm trường phân loại scan
    scan_type = fields.Selection([
        ('receive', 'Nhập kho'),
        ('checking', 'Kiểm kho')
    ], string="Loại quét", required=True, default='receive')
    
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
    scan_note = fields.Char("Ghi chú khi quét")
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm', 'scan_history_id', string="Xác nhận sản phẩm", ondelete='cascade')   
    
    # Các trường shipping chuyển từ stock.picking sang
    shipping_type = fields.Selection([
        ('pickup', 'Đến lấy hàng'),
        ('viettelpost', 'CPN/ViettelPost'),
        ('delivery', 'Gửi xe hàng'),
        ('other', 'Khác')
    ], string="Loại vận chuyển")
    shipping_phone = fields.Char("Số điện thoại giao vận")
    shipping_company = fields.Char("Nhà xe") 
    
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
    
    

