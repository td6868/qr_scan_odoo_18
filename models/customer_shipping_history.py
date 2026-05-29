# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CustomerShippingHistory(models.Model):
    _name = 'customer.shipping.history'
    _description = 'Lịch sử gửi xe theo khách hàng'
    _order = 'shipping_date desc'
    _rec_name = 'display_name'

    # Core relations
    partner_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        required=True,
        index=True,
        ondelete='cascade'
    )
    park_info = fields.Text(
        string='Thông tin gửi xe',
        help='Thông tin gửi xe đã sử dụng'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn hàng',
        ondelete='set null'
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Phiếu xuất kho',
        ondelete='set null'
    )

    # Shipping details
    shipping_date = fields.Datetime(
        string='Ngày gửi',
        default=fields.Datetime.now,
        required=True
    )
    shipping_method_id = fields.Many2one(
        'delivery.carrier',
        string='Phương thức vận chuyển'
    )
    
    # ========== TÍCH HỢP MODULE NHÀ XE (PHASE 2) ==========
    # Uncomment các dòng sau khi cài đặt module 'shipping_carrier'
    # và thêm 'shipping_carrier' vào depends trong __manifest__.py
    # 
    # shipping_carrier_company_id = fields.Many2one(
    #     'shipping.carrier.company',
    #     string='Nhà xe',
    #     tracking=True,
    #     help='Nhà xe vận chuyển được chọn'
    # )
    # 
    # shipping_route_id = fields.Many2one(
    #     'shipping.route',
    #     string='Tuyến đường',
    #     tracking=True,
    #     help='Tuyến đường vận chuyển'
    # )

    # Recipient info - NEW: Link to child contact
    recipient_partner_id = fields.Many2one(
        'res.partner',
        string='Địa chỉ người nhận',
        domain="[('parent_id', '=', partner_id), ('type', '=', 'delivery')]",
        help='Child contact (delivery address) của khách hàng cho người nhận này'
    )
    
    # Recipient info - OLD: Keep for backward compatibility and manual override
    recipient_name = fields.Char(
        string='Người nhận',
        compute='_compute_recipient_info',
        store=True,
        readonly=False,
        help='Tên người nhận - tự động lấy từ recipient_partner_id hoặc nhập thủ công'
    )
    recipient_phone = fields.Char(
        string='SĐT người nhận',
        compute='_compute_recipient_info',
        store=True,
        readonly=False,
        help='SĐT người nhận - tự động lấy từ recipient_partner_id hoặc nhập thủ công'
    )
    recipient_address = fields.Text(
        string='Địa chỉ nhận',
        compute='_compute_recipient_info',
        store=True,
        readonly=False,
        help='Địa chỉ nhận - tự động lấy từ recipient_partner_id hoặc nhập thủ công'
    )

    # Metadata
    created_by = fields.Many2one(
        'res.users',
        string='Người tạo',
        default=lambda self: self.env.user,
        readonly=True
    )
    note = fields.Text(string='Ghi chú')

    # Display name
    display_name = fields.Char(
        string='Tên hiển thị',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('partner_id', 'park_info', 'shipping_date')
    def _compute_display_name(self):
        for record in self:
            partner_name = record.partner_id.name or 'N/A'
            park_info = (record.park_info or 'N/A').strip()
            if len(park_info) > 30:
                park_info = park_info[:30] + '...'
            date_str = record.shipping_date.strftime('%d/%m/%Y') if record.shipping_date else 'N/A'
            record.display_name = f"{partner_name} - {park_info} ({date_str})"
    
    @api.depends('recipient_partner_id')
    def _compute_recipient_info(self):
        """Sync recipient info from recipient_partner_id"""
        for record in self:
            if record.recipient_partner_id:
                # Lấy thông tin từ child contact
                record.recipient_name = record.recipient_partner_id.name
                record.recipient_phone = record.recipient_partner_id.phone or record.recipient_partner_id.mobile
                # Ghép địa chỉ từ các field của partner
                address_parts = []
                if record.recipient_partner_id.street:
                    address_parts.append(record.recipient_partner_id.street)
                if record.recipient_partner_id.street2:
                    address_parts.append(record.recipient_partner_id.street2)
                if record.recipient_partner_id.city:
                    address_parts.append(record.recipient_partner_id.city)
                if record.recipient_partner_id.state_id:
                    address_parts.append(record.recipient_partner_id.state_id.name)
                record.recipient_address = ', '.join(address_parts) if address_parts else False
            # Nếu không có recipient_partner_id, giữ nguyên giá trị hiện tại (cho phép nhập thủ công)
    
    def _normalize_text(self, text):
        """Normalize text for comparison: lowercase, strip, remove extra spaces"""
        if not text:
            return ''
        return ' '.join(str(text).lower().strip().split())
    
    def _find_or_create_recipient_contact(self, partner_id, recipient_name, recipient_phone, recipient_address):
        """
        Tìm hoặc tạo child contact (delivery address) cho partner
        
        Args:
            partner_id: ID của partner chính (khách hàng)
            recipient_name: Tên người nhận
            recipient_phone: SĐT người nhận
            recipient_address: Địa chỉ người nhận
            
        Returns:
            res.partner record (child contact) hoặc False nếu không có thông tin
        """
        if not partner_id or not (recipient_name or recipient_phone or recipient_address):
            return False
        
        Partner = self.env['res.partner']
        
        # Normalize data để so sánh
        norm_name = self._normalize_text(recipient_name)
        norm_phone = self._normalize_text(recipient_phone)
        norm_address = self._normalize_text(recipient_address)
        
        # Tìm child contacts hiện có của partner
        existing_contacts = Partner.search([
            ('parent_id', '=', partner_id),
            ('type', '=', 'delivery')
        ])
        
        # Tìm contact khớp với thông tin
        same_name_contact = False
        for contact in existing_contacts:
            contact_name = self._normalize_text(contact.name)
            contact_phone = self._normalize_text(contact.phone or contact.mobile)
            contact_address_parts = []
            if contact.street:
                contact_address_parts.append(contact.street)
            if contact.street2:
                contact_address_parts.append(contact.street2)
            contact_address = self._normalize_text(' '.join(contact_address_parts))
            
            # So sánh: khớp nếu name và (phone hoặc address) giống nhau
            name_match = norm_name and contact_name and norm_name == contact_name
            phone_match = norm_phone and contact_phone and norm_phone == contact_phone
            address_match = norm_address and contact_address and (
                norm_address in contact_address or contact_address in norm_address
            )
            
            if name_match and (phone_match or address_match):
                vals_to_update = {}
                if recipient_phone and contact.mobile != recipient_phone:
                    vals_to_update['mobile'] = recipient_phone
                if recipient_address and contact.street != recipient_address:
                    vals_to_update['street'] = recipient_address
                if vals_to_update:
                    contact.write(vals_to_update)
                return contact

            # Nếu cùng tên nhưng SĐT/địa chỉ đã đổi, ưu tiên cập nhật contact cũ
            # để sale.order.partner_shipping_id và stock.picking.partner_id không giữ thông tin cũ.
            if name_match and not same_name_contact:
                same_name_contact = contact

        if same_name_contact:
            vals_to_update = {}
            if recipient_phone and same_name_contact.mobile != recipient_phone:
                vals_to_update['mobile'] = recipient_phone
            if recipient_address and same_name_contact.street != recipient_address:
                vals_to_update['street'] = recipient_address
            if vals_to_update:
                same_name_contact.write(vals_to_update)
            return same_name_contact
        
        # Không tìm thấy -> tạo mới child contact
        contact_vals = {
            'parent_id': partner_id,
            'type': 'delivery',
            'name': recipient_name or 'Người nhận',
        }
        
        if recipient_phone:
            contact_vals['mobile'] = recipient_phone
        
        if recipient_address:
            # Parse địa chỉ đơn giản: lưu vào street
            contact_vals['street'] = recipient_address
        
        new_contact = Partner.create(contact_vals)
        return new_contact
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create để tự động tạo/tìm recipient_partner_id"""
        for vals in vals_list:
            # Nếu có thông tin người nhận nhưng chưa có recipient_partner_id
            if vals.get('partner_id') and not vals.get('recipient_partner_id'):
                recipient_name = vals.get('recipient_name')
                recipient_phone = vals.get('recipient_phone')
                recipient_address = vals.get('recipient_address')
                
                # Tìm hoặc tạo child contact
                recipient_contact = self._find_or_create_recipient_contact(
                    vals['partner_id'],
                    recipient_name,
                    recipient_phone,
                    recipient_address
                )
                
                if recipient_contact:
                    vals['recipient_partner_id'] = recipient_contact.id
        
        return super().create(vals_list)

    def name_get(self):
        result = []
        for record in self:
            name = record.display_name or f"History #{record.id}"
            result.append((record.id, name))
        return result

    @api.model
    def get_history_by_partner(self, partner_id):
        """
        Get unique recipient contacts (child delivery addresses) for a partner
        Used by popover to show unique addresses instead of all history records
        
        Returns list of unique contacts with last used date
        """
        if not partner_id:
            return []
        
        # Use SQL for better performance: get unique contacts with max date
        self.env.cr.execute("""
            SELECT 
                recipient_partner_id,
                MAX(shipping_date) as last_used
            FROM customer_shipping_history
            WHERE partner_id = %s 
                AND recipient_partner_id IS NOT NULL
            GROUP BY recipient_partner_id
            ORDER BY last_used DESC
        """, (partner_id,))
        
        contact_data = self.env.cr.fetchall()
        
        if not contact_data:
            return []
        
        Partner = self.env['res.partner']
        result = []
        
        for contact_id, last_used in contact_data:
            contact = Partner.browse(contact_id)
            if not contact.exists():
                continue
            
            # Format address
            address_parts = []
            if contact.street:
                address_parts.append(contact.street)
            if contact.street2:
                address_parts.append(contact.street2)
            if contact.city:
                address_parts.append(contact.city)
            if contact.state_id:
                address_parts.append(contact.state_id.name)
            
            result.append({
                'id': contact.id,
                'name': contact.name or '',
                'phone': contact.phone or contact.mobile or '',
                'address': ', '.join(address_parts) if address_parts else '',
                'last_used': last_used.strftime('%d/%m/%Y %H:%M') if last_used else '',
            })
        
        return result

    @api.model
    def get_available_delivery_addresses(self, partner_id):
        """Get available child contacts/delivery addresses of the commercial customer."""
        if not partner_id:
            return []

        partner = self.env['res.partner'].browse(partner_id)
        if not partner.exists():
            return []

        root_partner = partner.commercial_partner_id or partner
        contacts = self.env['res.partner'].search([
            ('parent_id', '=', root_partner.id),
            ('type', 'in', ['delivery', 'contact', 'other']),
        ], order='type desc, name asc')

        result = []
        for contact in contacts:
            address_parts = []
            if contact.street:
                address_parts.append(contact.street)
            if contact.street2:
                address_parts.append(contact.street2)
            if contact.city:
                address_parts.append(contact.city)
            if contact.state_id:
                address_parts.append(contact.state_id.name)
            if contact.country_id:
                address_parts.append(contact.country_id.name)

            result.append({
                'id': contact.id,
                'name': contact.name or '',
                'phone': contact.mobile or contact.phone or '',
                'address': ', '.join(address_parts) if address_parts else '',
                'type': contact.type or '',
                'last_used': '',
            })

        return result

    @api.model
    def get_history_for_apply(self, contact_id):
        """
        Get contact data for applying to wizard - called from JS popover
        Now receives contact_id instead of history_id
        """
        if not contact_id:
            return False

        Partner = self.env['res.partner']
        contact = Partner.browse(contact_id)
        
        if not contact.exists():
            return False

        # Format address from contact
        address_parts = []
        if contact.street:
            address_parts.append(contact.street)
        if contact.street2:
            address_parts.append(contact.street2)
        if contact.city:
            address_parts.append(contact.city)
        if contact.state_id:
            address_parts.append(contact.state_id.name)
        
        # Get the latest history with this contact to get park_info
        latest_history = self.search([
            ('recipient_partner_id', '=', contact_id)
        ], order='shipping_date desc', limit=1)
        
        return {
            'park_info': latest_history.park_info if latest_history else '',
            'recipient_name': contact.name or '',
            'recipient_phone': contact.phone or contact.mobile or '',
            'recipient_address': ', '.join(address_parts) if address_parts else '',
        }
