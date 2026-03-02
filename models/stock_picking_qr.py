from odoo import models, fields, api, _
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    qr_code_image = fields.Binary("QR Code", attachment=True)
    qr_code_data = fields.Char("QR Code Content")
    scan_history_ids = fields.One2many('stock.picking.scan.history', 'picking_id', string="Lịch sử quét QR")
    image_count = fields.Integer("Số lượng ảnh", related='scan_history_ids.image_count', readonly=True)
    is_prepared = fields.Boolean("Đã chuẩn bị", default=False, copy=False)
    is_shipped = fields.Boolean("Đã giao hàng", default=False, copy=False)
    
    # Trường hiển thị trạng thái quét mới nhất
    latest_scan_type = fields.Selection([
        ('prepare', 'Chuẩn bị hàng'),
        ('shipping', 'Vận chuyển'),
        ('receive', 'Nhận hàng'),
        ('checking', 'Nhập kho'),
        ('assigned_task', 'Đã giao việc'),
    ], string="Trạng thái quét mới nhất", compute='_compute_latest_scan_type', store=True)

    is_assigned = fields.Boolean("Đã giao việc", compute='_compute_latest_scan_type', store=True)
    
    # Trường lưu thời gian giao việc (để sort)
    assigned_task_date = fields.Datetime(
        string="Thời gian giao việc",
        compute='_compute_latest_scan_type',
        store=True,
        help="Thời gian giao việc cho nhân viên (scan_date của assigned_task)"
    )
    
    # Trường phương thức vận chuyển - có thể chỉnh sửa bởi nhân viên kho
    shipping_method = fields.Many2one(
        'delivery.carrier',
        string="Phương thức vận chuyển",
        compute='_compute_shipping_method',
        store=True,
        readonly=False,
        help="Phương thức vận chuyển. Mặc định lấy từ đơn hàng nhưng có thể thay đổi."
    )
    
    # Trường ghi chú giao hàng
    delivery_note = fields.Text(
        string="Ghi chú giao hàng",
        help="Ghi chú dành cho nhân viên giao hàng và kho",
        copy=False
    )
    
    # ========== SHIPPING CARRIER COMPANY FIELDS ==========
    shipping_carrier_company_id = fields.Many2one(
        'shipping.carrier.company',
        string='Nhà xe',
        tracking=True,
        help='Nhà xe vận chuyển hàng hóa'
    )
    
    shipping_route_id = fields.Many2one(
        'shipping.route',
        string='Tuyến đường',
        domain="[('company_ids', '=', shipping_carrier_company_id)]",
        tracking=True,
        help='Tuyến đường sẽ gửi xe'
    )

    demo_bus_company = fields.Text(string="Thông tin gửi xe")
    
    # Thông tin gửi xe
    actual_shipping_date = fields.Datetime('Thời gian gửi xe thực tế', tracking=True)
    shipping_confirmed_by = fields.Many2one('res.users', 'Người xác nhận gửi xe', readonly=True)
    shipping_driver_phone = fields.Char('SĐT tài xế', tracking=True)
    shipping_vehicle_number = fields.Char('Biển số xe', tracking=True)
    shipping_tracking_number = fields.Char('Mã vận đơn', tracking=True)
    shipping_qr_code_image = fields.Binary('QR Code phiếu gửi xe', attachment=True)
    shipping_qr_code_data = fields.Char('Nội dung QR phiếu gửi xe')
    
    # Trạng thái gửi xe
    is_sent_to_carrier = fields.Boolean('Đã gửi xe', default=False, copy=False, tracking=True)

    sender_info = fields.Char(
        string='Người gửi (Phiếu gửi xe)',
        compute='_compute_print_info',
        store=True, readonly=False, copy=False
    )
    recipient_info = fields.Char(
        string='Người nhận (Phiếu gửi xe)',
        compute='_compute_print_info',
        store=True, readonly=False, copy=False
    )
    
    @api.depends('user_id', 'partner_id', 'sale_id.user_id')
    def _compute_print_info(self):
        for record in self:
            if not record.sender_info or record.sender_info == 'OdooBot':
                # Ưu tiên lấy nhân viên kinh doanh từ đơn hàng (sale_id.user_id)
                # Nếu không có, lấy người chịu trách nhiệm phiếu (user_id)
                # Cuối cùng lấy user hiện tại
                sender_name = record.sale_id.user_id.name or record.user_id.name or self.env.user.name
                record.sender_info = sender_name
            if not record.recipient_info:
                record.recipient_info = record.partner_id.name or ''
    
    @api.depends('sale_id.shipping_method')
    def _compute_shipping_method(self):
        """Tính toán shipping_method từ sale order, nhưng cho phép override"""
        for record in self:
            # Chỉ set giá trị mặc định nếu chưa có
            if not record.shipping_method and record.sale_id and record.sale_id.shipping_method:
                record.shipping_method = record.sale_id.shipping_method
    
    @api.depends('scan_history_ids.scan_type', 'scan_history_ids.scan_date')
    def _compute_latest_scan_type(self):
        """Tính toán trạng thái quét mới nhất từ lịch sử quét"""
        for record in self:
            latest_scan = record.scan_history_ids.sorted('scan_date', reverse=True)[:1]
            record.latest_scan_type = latest_scan.scan_type if latest_scan else False
            
            # Kiểm tra xem đã từng có bản ghi assigned_task chưa
            record.is_assigned = any(h.scan_type == 'assigned_task' for h in record.scan_history_ids)
            
            # Lấy thời gian giao việc (assigned_task) đầu tiên
            assigned_task_history = record.scan_history_ids.filtered(
                lambda h: h.scan_type == 'assigned_task'
            ).sorted('scan_date')[:1]  # Lấy assigned_task đầu tiên (cũ nhất)
            record.assigned_task_date = assigned_task_history.scan_date if assigned_task_history else False

    def assign_task(self):
        """Giao việc cho user - tạo bản ghi lịch sử quét"""
        self.ensure_one()
        self.env['stock.picking.scan.history'].create({
            'picking_id': self.id,
            'scan_type': 'assigned_task',
            'scan_user_id': self.env.uid,
            'scan_date': fields.Datetime.now(),
            'scan_note': 'Đã giao việc'
        })
        return self.action_open_print_wizard()
    
    # Thêm trường move_line_confirmed_ids
    move_line_confirmed_ids = fields.One2many('stock.move.line.confirm',compute='_compute_move_line_confirmed_ids', string="Xác nhận sản phẩm")
    
    def create(self, vals):
        picking = super().create(vals)
        return picking

    def _generate_qr_code(self):
        """Tạo QR code cho record sử dụng multi-model service"""
        qr_service = self.env['multi.model.qr.service']
        for record in self:
            qr_service.generate_qr_for_record(record)

    @api.depends('scan_history_ids')
    def _compute_is_scanned(self):
        for record in self:
            record.is_scanned = bool(record.scan_history_ids)                
       
    # def action_done(self):
    #     """Override action_done để tạo QR khi picking được hoàn thành"""
    #     result = super().action_done()
    #     return result
    
    def get_current_user_info(self):
        """Method để lấy thông tin user hiện tại"""
        return {
            'user_id': self.env.user.id,
            'user_name': self.env.user.name,
            'login': self.env.user.login,
        }

    def _map_scan_mode_to_type(self, scan_mode):
        """Map scan mode to scan type"""
        mapping = {
            'prepare': 'prepare',
            'shipping': 'shipping', 
            'receive': 'receive',
            'checking': 'checking'
        }
        return mapping.get(scan_mode)

    def update_scan_info(self, **kwargs):        
        """Method để cập nhật thông tin scan"""
        self.ensure_one()
        
        scan_mode = kwargs.get('scan_mode', '')
        scan_type = self._map_scan_mode_to_type(scan_mode)
        universal_processor = self.env['universal.scan.processor']
        processor = universal_processor.get_processor('stock.picking', scan_type)
        
        # Ghi đè scan_type để controller luồng xử lý biết được loại hành động
        kwargs['scan_type'] = scan_type
        
        return processor.process_scan(self, **kwargs)


    def action_validate_qr_scan(self, scan_mode):
        """Kiểm tra xem record có được phép quét ở mode này không bằng cách sử dụng backend logic"""
        self.ensure_one()
        try:
            scan_type = self._map_scan_mode_to_type(scan_mode)
            processor = self.env['universal.scan.processor'].get_processor('stock.picking', scan_type)
            
            # Gọi các hàm validate trong backend
            processor._validate_record_state(self)
            
            # Đối với shipping, cần giả lập shipping_type để bypass check required nếu chỉ validate bước đầu
            kwargs = {}
            if scan_mode == 'shipping':
                kwargs['shipping_type'] = 'validate_only'
                
            processor._validate_scan_specific(self, **kwargs)
            return {'status': 'success'}
        except ValidationError as e:
            return {'status': 'error', 'message': e.args[0]}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @api.depends('scan_history_ids.move_line_confirmed_ids')
    def _compute_move_line_confirmed_ids(self):
        for record in self:
            record.move_line_confirmed_ids = record.scan_history_ids.mapped('move_line_confirmed_ids')
            
    def action_view_image_proof(self):
        self.ensure_one()
        domain = [('picking_id', '=', self.id)]
        image_proof_ids = self.env['stock.picking.scan.history'].search(domain)
        """Hiển thị ảnh chứng minh"""
        result = {
            'name': 'Ảnh chứng minh',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.scan.history',
            'domain': domain,
            'context': {'create': False},
        }          
        result.update({
            "view_mode": 'kanban,form',
            "domain": domain,
        })  
        return result
    
    def action_print_picking(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize').report_action(self)
        else:
            return self.env.ref('qr_scan_odoo_18.action_report_purchase_order_customize').report_action(self)

    def action_print_picking_2(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize_2').report_action(self)    

    def action_print_packing_ticket(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_packing_ticket').report_action(self)    
    
    def action_open_print_wizard(self):
        self.ensure_one()
        return {
            'name': _('Chọn loại phiếu in'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_ids': [self.id],
                'default_picking_id': self.id,
            }
        }
    
    def _get_print_report_options(self):
        """Trả về danh sách các lựa chọn in phiếu. Có thể override để thêm loại mới."""
        self.ensure_one()
        options = [('type_1', 'In phiếu')]
        # Kiểm tra code linh hoạt hơn (hỗ trợ cả outgoing và delivery)
        if self.picking_type_id.code in ['outgoing', 'delivery']:
            options.append(('type_2', 'In phiếu (Điền)'))
            options.append(('type_3', 'In phiếu (Gửi xe)'))
        return options

    def _get_report_method_mapping(self):
        """Trả về mapping giữa loại report và method xử lý tương ứng."""
        return {
            'type_1': 'action_print_picking',
            'type_2': 'action_print_picking_2',
            'type_3': 'action_print_packing_ticket',
            # Dễ dàng thêm các loại mới tại đây
        }

    def action_perform_print(self, report_type):
        """Thực hiện in dựa trên loại report đã chọn."""
        self.ensure_one()
        mapping = self._get_report_method_mapping()
        method_name = mapping.get(report_type)
        
        if method_name and hasattr(self, method_name):
            return getattr(self, method_name)()
            
        return False
    
    @api.onchange('shipping_carrier_company_id')
    def _onchange_shipping_carrier_company_id(self):
        self.shipping_route_id = False    

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
        ('checking', 'Nhập kho'),
        ('assigned_task', 'Đã giao việc'),
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
        ('bus', 'Xe khách / Nhà xe'),
        # ('pickup', 'Khách lấy tại quầy'),
        # ('viettel', 'Viettel Post'),
    ], string="Loại vận chuyển")
    shipping_phone = fields.Char(related = 'picking_id.shipping_driver_phone', readonly=True, string="SĐT tài xế")
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
                
            attachment = self.env['ir.attachment'].sudo().create({
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

    def _compute_display_name(self):
        for record in self:
            if record.scan_date:
                local_dt = fields.Datetime.context_timestamp(
                    record,
                    record.scan_date
                )
                scan_date_7 = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                record.display_name = f"{record.picking_id.name} - {scan_date_7}"
            else:
                record.display_name = record.picking_id.name
