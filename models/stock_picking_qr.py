from odoo import models, fields, api
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    qr_code_image = fields.Binary("QR Code", attachment=True)
    qr_code_data = fields.Char("QR Code Content")
    scan_history_ids = fields.One2many('stock.picking.scan.history', 'picking_id', string="Lịch sử quét QR")
    # is_scanned = fields.Boolean("Đã quét", compute='_compute_is_scanned', default=False, copy=False)
    
    # Thêm trường mới cho loại vận chuyển
    # shipping_type = fields.Selection([
    #     ('pickup', 'Khách đến lấy hàng'),
    #     ('viettelpost', 'Viettel Post'),
    #     ('delivery', 'Đặt ship : Xe khách/Xe ...')
    # ], string="Loại vận chuyển", default='pickup', store=True, compute='_compute_shipping_info')

    # shipping_date = fields.Datetime("Ngày vận chuyển", store=True, compute='_compute_shipping_info', readonly=True, default=False)

    # shipping_note = fields.Text("Ghi chú vận chuyển",default=False,store=True,compute='_compute_shipping_info')

    # is_shipped = fields.Boolean("Đã vận chuyển", default=False, readonly=True,store=True,compute='_compute_shipping_info')

    
    # Trạng thái nhận hàng
    # is_received = fields.Boolean("Đã nhận hàng", compute='_compute_inbound_info', store=True, default=False)
    # receive_date = fields.Datetime("Ngày nhận hàng", compute='_compute_inbound_info', store=True, readonly=True)
    # receive_user_id = fields.Many2one('res.users', string="Người nhận hàng", store=True, compute='_compute_inbound_info')
    # receive_note = fields.Text("Ghi chú nhận hàng", store=True, compute='_compute_inbound_info')
    
    # Trạng thái kiểm hàng
    # is_checked = fields.Boolean("Đã kiểm hàng", compute='_compute_inbound_info', store=True, default=False)
    # check_date = fields.Datetime("Ngày kiểm hàng", compute='_compute_inbound_info', store=True, readonly=True)
    # check_user_id = fields.Many2one('res.users', string="Người kiểm hàng", store=True, compute='_compute_inbound_info')
    # check_note = fields.Text("Ghi chú kiểm hàng", store=True, compute='_compute_inbound_info')
    
    # Thêm trường move_line_confirmed_ids
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm',compute='_compute_move_line_confirmed_ids', string="Xác nhận sản phẩm")

    # Các trường liên kết với scan_history_ids mới nhất
    # scan_user_id = fields.Many2one('res.users', string="Người quét", compute="_compute_shipping_info", store=True)
    # scan_note = fields.Text(string="Ghi chú", compute="_compute_shipping_info", store=True)
    
    def create(self, vals):
        picking = super().create(vals)
        return picking

    def _generate_qr_code(self):
        """Tạo QR code cho picking nếu chưa có hoặc data đã thay đổi"""
        qr_service = self.env['stock.picking.qr.service']
        for record in self:
            qr_service.generate_qr_for_picking(record)

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
                record.update({
                    'is_shipped': True,
                    'shipping_date': latest_shipping.scan_date,
                    'shipping_note': latest_shipping.scan_note,
                    'scan_user_id': latest_shipping.scan_user_id,
                    'scan_note': latest_shipping.scan_note,
                    'shipping_type': latest_shipping.shipping_type,
                })
            else:
                record.update({
                    'is_shipped': False,
                    'shipping_date': False,
                    'shipping_note': False,
                    'shipping_type': False,
                    'scan_note': False,
                    'scan_user_id': False,
                })

    @api.depends('scan_history_ids.scan_type')
    def _compute_inbound_info(self):
        for record in self:
            # Tính toán thông tin nhận hàng
            receive_history = record.scan_history_ids.filtered(lambda h: h.scan_type == 'receive')
            
            if receive_history:
                latest_receive = receive_history[0]  # Đã sort theo scan_date desc
                is_received = True
                receive_date = latest_receive.scan_date
                receive_user_id = latest_receive.scan_user_id
                receive_note = latest_receive.scan_note
            else:
                is_received = False
                receive_date = False
                receive_user_id = False
                receive_note = False

            record.update({
                'is_received': is_received,
                'receive_date': receive_date,
                'receive_user_id': receive_user_id,
                'receive_note': receive_note,
            })
            
            # Tính toán thông tin kiểm hàng
            check_history = record.scan_history_ids.filtered(lambda h: h.scan_type == 'checking')
            if check_history:
                latest_check = check_history[0]  # Đã sort theo scan_date desc
                record.is_checked = True
                record.check_date = latest_check.scan_date
                record.check_user_id = latest_check.scan_user_id
                record.check_note = latest_check.scan_note
            else:
                record.is_checked = False
                record.check_date = False
                record.check_user_id = False
                record.check_note = False
                
       
    def action_done(self):
        """Override action_done để tạo QR khi picking được hoàn thành"""
        result = super().action_done()
        return result


    # Thêm phương thức này vào class StockPicking
    # def action_print_picking(self):
    #     """Gọi khi người dùng nhấn nút in"""
    #     return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize').report_action(self)
    
    def get_current_user_info(self):
        """Method để lấy thông tin user hiện tại"""
        return {
            'user_id': self.env.user.id,
            'user_name': self.env.user.name,
            'login': self.env.user.login,
        }
    
    # def get_all_prepare_images(self):
    #     """Lấy tất cả ảnh chuẩn bị hàng"""
    #     images = []
    #     for history in self.scan_history_ids:
    #         for attachment in history.attachment_ids:
    #             images.append({
    #                 'id': attachment.id,
    #                 'name': attachment.name,
    #                 'datas': attachment.datas,
    #                 'create_date': attachment.create_date,
    #                 'description': attachment.description,
    #             })
    #     return images

    def _map_scan_mode_to_type(self, scan_mode):
        """Map scan mode to scan type"""
        mapping = {
            'prepare': 'prepare',
            'shipping': 'shipping', 
            'receive': 'receive',
            'checking': 'checking'
        }
        return mapping.get(scan_mode)

    def update_scan_info(self, images_data=None, scan_note=None, move_line_confirms=None, 
                    scan_mode='', shipping_type=None, 
                    shipping_phone=None, shipping_company=None):        
        """Method để cập nhật thông tin scan"""
        self.ensure_one()
        
        scan_type = self._map_scan_mode_to_type(scan_mode)
        scan_processor = self.env['stock.picking.scan.processor']
        processor = scan_processor.get_processor(scan_type)
        
        return processor.process_scan(
            self,
            scan_type=scan_type,
            images_data=images_data,
            scan_note=scan_note,
            move_line_confirms=move_line_confirms,
            shipping_type=shipping_type,
            shipping_phone=shipping_phone,
            shipping_company=shipping_company
        )

    def update_move_line_confirm(self, confirmed_lines):    
        """Cập nhật xác nhận move lines -cập nhật quantity"""
        
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
            })

            move.write({'quantity': quantity})

        if confirm_vals:
            self.env['stock.move.line.confirm'].create(confirm_vals)

        return {'status': 'success', 'message': 'Đã xác nhận và cập nhật số lượng thành công'}

    @api.depends('scan_history_ids.move_line_confirmed_ids')
    def _compute_move_line_confirmed_ids(self):
        for record in self:
            record.move_line_confirmed_ids = record.scan_history_ids.mapped('move_line_confirmed_ids')

class StockMoveLineConfirm(models.Model):
    _name = 'stock.move.line.confirm'
    _description = 'Xác nhận sản phẩm'
    
    scan_history_id = fields.Many2one('stock.picking.scan.history', string="Lịch sử quét", required=True, ondelete='cascade')
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất kho", related='scan_history_id.picking_id', store=True)
    move_id = fields.Many2one('stock.move', string="Sản phẩm", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Sản phẩm", required=True)
    quantity_confirmed = fields.Float("Số lượng xác nhận", default=0.0)
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
    
    scan_type = fields.Selection([
        ('prepare', 'Chuẩn bị hàng'),
        ('shipping', 'Vận chuyển'),
        ('receive', 'Nhận hàng'),
        ('checking', 'Nhập kho')
    ], string="Loại quét", required=True,)
    
    picking_id = fields.Many2one('stock.picking', string="Phiếu xuất/nhập kho", required=True, ondelete='cascade')
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
        if not images_data or len(images_data) == 0:
            return []
        """Lưu nhiều ảnh vào ir.attachment"""
        attachments = []
        for i, img_data in enumerate(images_data):
            if not img_data or (isinstance(img_data, str)) or not img_data.get('data'):
                continue
                
            attachment = self.env['ir.attachment'].create({
                'name': img_data.get('name', f'Prepare_Image_{i+1}_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'),
                'type': 'binary',
                'datas': img_data['data'],
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'image/jpeg',
                'description': img_data.get('description', f'Ảnh minh chứng #{i+1}'),
            })
            attachments.append(attachment.id)
        return attachments