from odoo import models, fields, api, _
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    qr_code_image = fields.Binary("QR Code", attachment=True)
    qr_code_data = fields.Char("QR Code Content")
    scan_history_ids = fields.One2many('stock.picking.scan.history', 'picking_id', string="Lịch sử quét QR")
    image_count = fields.Integer("Số lượng ảnh", related='scan_history_ids.image_count', readonly=True)
    ship_inf_state = fields.Selection([
        ('none', 'Không áp dụng'),
        ('not_received', 'Chưa nhận'),
        ('received', 'Đã nhận'),
        ('completed', 'Hoàn thành'),
    ], string='Trạng thái giao vận', default='none', copy=False, tracking=True,
       help='Trạng thái theo dõi thông tin gửi xe/giao hàng')
    
    # Trường hiển thị trạng thái quét mới nhất
    latest_scan_type = fields.Selection([
        ('prepare', 'Chuẩn bị hàng'),
        ('shipping', 'Vận chuyển'),
        ('receive', 'Nhận hàng'),
        ('checking', 'Nhập kho'),
        ('assigned_task', 'Đã giao việc'),
        ('delivery_complete', 'Hoàn thành giao hàng'),
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
    
    # Trường loại vận chuyển (bao cước)
    type_shipping_cost = fields.Selection(
        selection=[
            ('1', 'Khách hàng trả phí'),
            ('2', 'Bao cước toàn bộ'),
            ('3', 'Bao cước một phần'),
        ],
        string='Loại vận chuyển',
        help='Thông tin bao cước để giao vận biết ai trả phí vận chuyển',
        copy=False,
        tracking=True,
    )
    
    # Trường ghi chú giao hàng
    delivery_note = fields.Text(
        string="Ghi chú giao hàng",
        help="Ghi chú dành cho nhân viên giao hàng và kho",
        copy=False
    )

    wh_user_id = fields.Many2one(
        'res.users',
        string='NV kho',
        tracking=True,
        copy=False,
        help='Nhân viên kho được giao xử lý phiếu'
    )
    
    cancel_reason = fields.Text(
        string='Lý do từ chối',
        tracking=True,
        copy=False,
        help='Lý do thủ kho từ chối nhận việc'
    )
    
    # ========== Tracking việc Sale giao việc cho Thủ kho ==========
    sale_assigned_date = fields.Datetime(
        string='Thời gian sale giao việc',
        tracking=True,
        copy=False,
        help='Thời gian sale giao việc cho thủ kho'
    )
    sale_assigned_user_id = fields.Many2one(
        'res.users',
        string='Sale giao việc',
        tracking=True,
        copy=False,
        help='Nhân viên sale đã giao việc cho thủ kho'
    )
    
    # ========== Tracking việc Thủ kho xác nhận nhận việc ==========
    warehouse_acknowledged = fields.Boolean(
        string='Thủ kho đã nhận việc',
        default=False,
        tracking=True,
        copy=False,
        help='Thủ kho đã xác nhận nhận việc từ sale'
    )
    warehouse_acknowledged_date = fields.Datetime(
        string='Thời gian thủ kho nhận việc',
        tracking=True,
        copy=False,
        help='Thời gian thủ kho xác nhận nhận việc'
    )
    wh_ack_user_id = fields.Many2one(
        'res.users',
        string='Thủ kho nhận việc',
        tracking=True,
        copy=False,
        help='Nhân viên thủ kho đã xác nhận nhận việc'
    )
    
    # Cảnh báo khi sale giao việc lại sau khi thủ kho đã nhận
    needs_recheck = fields.Boolean(
        string='⚠️ Cần xem lại',
        compute='_compute_needs_recheck',
        store=True,
        help='Sale đã giao việc lại sau khi thủ kho nhận việc. Cần kiểm tra thông tin cập nhật.'
    )
    
    # ========== Thông tin gửi xe ==========
    park_info = fields.Text(
        string='Thông tin gửi xe',
        tracking=True,
        help='Thông tin gửi xe vận chuyển hàng hóa'
    )
    
    # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
    # Uncomment các dòng sau khi cài đặt module 'shipping_carrier'
    # và thêm 'shipping_carrier' vào depends trong __manifest__.py
    # 
    shipping_carrier_company_id = fields.Many2one(
        'shipping.carrier.company',
        string='Nhà xe',
        tracking=True,
        help='Nhà xe vận chuyển hàng hóa'
    )
    # 
    shipping_route_id = fields.Many2one(
        'shipping.route',
        string='Tuyến đường',
        tracking=True,
        help='Tuyến đường vận chuyển'
    )
    # 
    # # Computed fields để hiển thị thông tin nhà xe
    # carrier_phone = fields.Char(
    #     related='shipping_carrier_company_id.phone',
    #     string='SĐT Nhà xe',
    #     readonly=True
    # )
    # 
    # carrier_address = fields.Text(
    #     related='shipping_carrier_company_id.address',
    #     string='Địa chỉ gửi hàng',
    #     readonly=True
    # )

    # Thông tin gửi xe
    actual_shipping_date = fields.Datetime('Thời gian gửi xe thực tế', tracking=True)
    shipping_confirmed_by = fields.Many2one('res.users', 'Người xác nhận gửi xe', readonly=True)
    shipping_driver_phone = fields.Char('SĐT tài xế', tracking=True)
    shipping_vehicle_number = fields.Char('Biển số xe', tracking=True)
    shipping_tracking_number = fields.Char('Mã vận đơn', tracking=True)
    shipping_qr_code_image = fields.Binary('QR Code phiếu gửi xe', attachment=True)
    shipping_qr_code_data = fields.Char('Nội dung QR phiếu gửi xe')

    def _is_tracked_shipping_method(self):
        """Kiểm tra xem phương thức vận chuyển có thuộc loại cần quét gửi xe (Xe tải/Xe bus, Grab) hay không.
        Chỉ áp dụng cho phiếu xuất hàng (outgoing).
        """
        self.ensure_one()
        if self.picking_type_code != 'outgoing':
            return False
        if not self.shipping_method:
            return False
        name = (self.shipping_method.name or '').lower()
        return any(x in name for x in ['xe tải', 'xe bus', 'grab'])

    def action_complete_delivery(self, images_data=None, note=''):
        """Xác nhận đã giao hàng thành công (chuyển sang Hoàn thành và lưu ảnh)"""
        self.ensure_one()
        if self.ship_inf_state != 'received':
            raise ValidationError("Chỉ có thể hoàn thành phiếu đang ở trạng thái 'Đã nhận'!")
            
        # Tạo bản ghi lịch sử quét với kiểu delivery_complete
        scan_vals = {
            'picking_id': self.id,
            'scan_type': 'delivery_complete',
            'scan_note': note,
            'scan_user_id': self.env.user.id,
        }
        scan_history = self.env['stock.picking.scan.history'].sudo().create(scan_vals)
        if images_data and hasattr(scan_history, 'save_images'):
            scan_history.save_images(images_data)
            
        self.write({
            'ship_inf_state': 'completed',
        })
        return scan_history

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

    # ========== Thông tin người nhận chi tiết ==========
    recipient_name = fields.Char(
        string='Tên người nhận',
        tracking=True,
        copy=False,
        help='Tên người nhận hàng thực tế (từ wizard giao việc)'
    )
    recipient_phone = fields.Char(
        string='SĐT người nhận',
        tracking=True,
        copy=False,
        help='Số điện thoại người nhận hàng thực tế'
    )
    recipient_address = fields.Text(
        string='Địa chỉ người nhận',
        tracking=True,
        copy=False,
        help='Địa chỉ giao hàng thực tế (từ wizard giao việc)'
    )
    
    @api.depends('user_id', 'wh_user_id', 'partner_id', 'sale_id.user_id')
    def _compute_print_info(self):
        for record in self:
            if not record.sender_info or record.sender_info == 'OdooBot':
                # Ưu tiên lấy nhân viên kinh doanh từ đơn hàng (sale_id.user_id)
                # Nếu không có, lấy nhân viên kho được giao (wh_user_id)
                # Nếu vẫn không có, lấy người chịu trách nhiệm phiếu (user_id)
                # Cuối cùng lấy user hiện tại
                sender_name = record.sale_id.user_id.name or record.wh_user_id.name or record.user_id.name or self.env.user.name
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
    
    @api.depends('warehouse_acknowledged', 'sale_assigned_date', 'warehouse_acknowledged_date')
    def _compute_needs_recheck(self):
        """
        Cảnh báo khi sale giao việc lại sau khi thủ kho đã nhận việc
        Điều này có nghĩa là có thông tin mới cần thủ kho kiểm tra lại
        """
        for rec in self:
            rec.needs_recheck = (
                rec.warehouse_acknowledged and 
                rec.sale_assigned_date and 
                rec.warehouse_acknowledged_date and
                rec.sale_assigned_date > rec.warehouse_acknowledged_date
            )

    def assign_task(self):
        """Giao việc cho user - tạo bản ghi lịch sử quét"""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            raise ValidationError("Không thể giao việc/giao việc lại cho phiếu xuất kho đã hoàn tất hoặc đã hủy.")
        self.env['stock.picking.scan.history'].create({
            'picking_id': self.id,
            'scan_type': 'assigned_task',
            'scan_user_id': self.env.uid,
            'scan_date': fields.Datetime.now(),
            'scan_note': 'Đã giao việc'
        })
        return self.action_open_print_wizard()
    
    def action_acknowledge_task(self):
        """Thủ kho xác nhận đã nhận việc từ sale"""
        self.ensure_one()
        
        if not self.sale_assigned_date:
            raise ValidationError("Phiếu này chưa được sale giao việc!")
        
        if self.warehouse_acknowledged:
            raise ValidationError("Phiếu này đã được xác nhận nhận việc rồi!")
        
        # Update các field xác nhận nhận việc
        self.write({
            'warehouse_acknowledged': True,
            'warehouse_acknowledged_date': fields.Datetime.now(),
            'wh_ack_user_id': self.env.uid,
            'cancel_reason': False,
        })
        
        # Post message to sale order chatter
        if self.sale_id:
            message = f"""<p><strong>✅ Thủ kho đã nhận việc</strong></p>
            <ul>
                <li><strong>Phiếu xuất kho:</strong> {self.name}</li>
                <li><strong>Thủ kho:</strong> {self.env.user.name}</li>
                <li><strong>Thời gian:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            <p><em>Đơn hàng sẽ sớm được giao!</em></p>"""
            
            self.sale_id.message_post(
                body=Markup(message),
                subject='Thủ kho đã nhận việc',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        
        return True

    def action_cancel_task(self):
        """Thủ kho hủy việc giao việc (mở wizard từ chối)"""
        self.ensure_one()
        
        if not self.sale_assigned_date:
            raise ValidationError("Phiếu này chưa được sale giao việc!")
        
        if self.warehouse_acknowledged:
            raise ValidationError("Phiếu này đã được xác nhận nhận việc rồi!")
        
        return {
            'name': _('Lý do từ chối giao việc'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_picking_id': self.id,
            }
        }

    def _get_stock_increase_moves(self):
        """Các move làm tăng tồn do nhập kho hoặc khách trả hàng."""
        self.ensure_one()
        return self.move_ids_without_package.filtered(
            lambda m: m.state == 'done'
            and m.product_id
            and m.quantity > 0
            and m.location_dest_id.usage == 'internal'
            and m.location_id.usage in ('supplier', 'customer')
        )

    def _update_products_latest_stock_increase_date(self):
        """Cập nhật ngày tăng tồn gần nhất lên product.product."""
        for picking in self:
            effective_dt = picking.date_done or fields.Datetime.now()
            effective_date = fields.Datetime.context_timestamp(picking, effective_dt).date()

            latest_by_product = {}
            for move in picking._get_stock_increase_moves():
                product = move.product_id
                current_date = latest_by_product.get(product.id)
                if not current_date or effective_date > current_date:
                    latest_by_product[product.id] = effective_date

            for product_id, increase_date in latest_by_product.items():
                product = self.env['product.product'].browse(product_id)
                if not product.latest_stock_increase_date or increase_date >= product.latest_stock_increase_date:
                    product.latest_stock_increase_date = increase_date

    def button_validate(self):
        result = super().button_validate()
        self._update_products_latest_stock_increase_date()
        return result

    def action_fill_all_quantities(self):
        """Điền toàn bộ số lượng thực hiện bằng đúng nhu cầu trên các stock move."""
        for picking in self:
            moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
            for move in moves:
                move.quantity = move.product_uom_qty
        return True

    def action_clear_reserved_quantities(self):
        """Xóa toàn bộ số lượng đang điền/dự trữ trên các stock move."""
        for picking in self:
            moves = picking.move_ids_without_package.filtered(lambda m: m.state not in ('done', 'cancel'))
            for move in moves:
                move.quantity = 0.0
        return True
    
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
    
    def _prepare_picking_report_rows(self):
        """Chuẩn bị dữ liệu dòng in phiếu theo sản phẩm (O(n)).

        Tối ưu hơn so với cách group trực tiếp trong QWeb (filtered/mapped lồng nhau).
        Trả về list dict: product, first_move, total_qty.
        """
        self.ensure_one()
        rows_by_product = {}

        for move in self.move_ids_without_package:
            if move.quantity <= 0:
                continue

            product = move.product_id
            if not product:
                continue

            key = product.id
            row = rows_by_product.get(key)
            if row is None:
                rows_by_product[key] = {
                    'product': product,
                    'first_move': move,
                    'total_qty': move.quantity,
                }
            else:
                row['total_qty'] += move.quantity

        return list(rows_by_product.values())

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

    def action_print_picking_origin_name(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code in ['outgoing', 'delivery']:
            return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize_origin_name').report_action(self)

    def action_print_packing_ticket(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_packing_ticket').report_action(self) 

    def action_print_primetech(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize_signature').report_action(self)

    def action_print_covatech(self):
        self.ensure_one()
        picking_code = self.picking_type_id.code
        if picking_code == 'outgoing':
            return self.env.ref('qr_scan_odoo_18.action_report_stock_pick_customize_covatech').report_action(self)
    
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
            options.append(('type_3', 'In phiếu (Tên gốc)'))
            options.append(('type_4', 'PRIMETECH'))
            options.append(('type_5', 'COVATECH'))
        return options

    def _get_report_method_mapping(self):
        """Trả về mapping giữa loại report và method xử lý tương ứng."""
        return {
            'type_1': 'action_print_picking',
            'type_2': 'action_print_picking_2',
            'type_3': 'action_print_picking_origin_name',
            'type_4': 'action_print_primetech',
            'type_5': 'action_print_covatech'
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
    
    # Lịch cron các phiếu xuất kho backorders
    def cron_assign_backorders(self):
        pickings = self.search([
            ('state', 'in', ['waiting', 'confirmed']),
            ('backorder_id', '!=', False),
            ('picking_type_code', '=', 'outgoing'),
            ('sale_id', '!=', False),
        ], order='id')

        total = len(pickings)
        batch_size = 100

        _logger.info("Cron assign backorders: found %s pickings", total)

        for start in range(0, total, batch_size):
            batch = pickings[start:start + batch_size]
            try:
                _logger.info(
                    "Cron assign backorders: processing batch %s-%s",
                    start + 1,
                    min(start + batch_size, total),
                )
                batch.action_assign()
            except Exception:
                _logger.exception(
                    "Cron assign backorders: failed batch %s-%s",
                    start + 1,
                    min(start + batch_size, total),
                )

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
        ('delivery_complete', 'Hoàn thành giao hàng'),
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
