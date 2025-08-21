# -*- coding: utf-8 -*-
{
    'name': "QR Kho",
    'version' : '18.0.0.0.1',
    'summary': "chức năng quét QR",
    'sequence': 115,
    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customize',

    # any module necessary for this one to work correctly
    "depends": [
                    "base",
                    "product",
                    "sale",
                    "account",
                    "stock",
                    "stock_landed_costs",
                    "report_xlsx",                    
                    "purchase",
                    "delivery",
                    "crm",
                    "hr",
                    "hr_expense",
                ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',    
        'report/custom_report.xml',
        'report/stock_picking_rp.xml',
        'report/report_po_china.xml',
        'report/report_po_kk.xml',
        'views/stock_picking_qr_views.xml',
        # 'views/stock_picking_qr_scanner.xml',
        'wizard/print_poc.xml',
    ],
    
    # 'css': [
    #     'static/src/css/custom_css_kk.css',
    #     'static/src/scss/custom_kk.scss',
    # ],
    
    'assets': {
        'web.assets_backend': [
            'qr_scan_odoo_18/static/src/xml/stock_picking_qr_scanner.xml',
            # 'qr_scan_odoo_18/static/src/js/stock_picking_qr_scaner.js',
            'qr_scan_odoo_18/static/src/css/stock_picking_qr_scanner.css',
            'qr_scan_odoo_18/static/lib/html5-qrcode/html5-qrcode.min.js',
            'qr_scan_odoo_18/static/src/xml/confirmation_dialog.xml',

            
            # Components
            'qr_scan_odoo_18/static/src/js/components/confirmation_dialog.js',
            
            # Core QR functionality
            'qr_scan_odoo_18/static/src/js/core/qr_scanner.js',
            'qr_scan_odoo_18/static/src/js/core/qr_processor.js',
            
            # Utilities
            'qr_scan_odoo_18/static/src/js/utils/camera_manager.js',
            'qr_scan_odoo_18/static/src/js/utils/file_manager.js',
            
            # Handlers
            'qr_scan_odoo_18/static/src/js/handlers/base_scan_handler.js',
            'qr_scan_odoo_18/static/src/js/handlers/prepare_scan_handler.js',
            'qr_scan_odoo_18/static/src/js/handlers/shipping_scan_handler.js',
            'qr_scan_odoo_18/static/src/js/handlers/receive_scan_handler.js',
            'qr_scan_odoo_18/static/src/js/handlers/checking_scan_handler.js',
            
            # Main component
            'qr_scan_odoo_18/static/src/js/stock_picking_qr_scanner.js',
        ],
    },
    
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
    
    'icon': 'qr_scan_odoo_18/static/description/icon.png',
    'installable': True,
    'application': True,
}

