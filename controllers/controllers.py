# -*- coding: utf-8 -*-
# from odoo import http


# class TinhNangQrKho(http.Controller):
#     @http.route('/tinh_nang_qr_kho/tinh_nang_qr_kho', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tinh_nang_qr_kho/tinh_nang_qr_kho/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('tinh_nang_qr_kho.listing', {
#             'root': '/tinh_nang_qr_kho/tinh_nang_qr_kho',
#             'objects': http.request.env['tinh_nang_qr_kho.tinh_nang_qr_kho'].search([]),
#         })

#     @http.route('/tinh_nang_qr_kho/tinh_nang_qr_kho/objects/<model("tinh_nang_qr_kho.tinh_nang_qr_kho"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tinh_nang_qr_kho.object', {
#             'object': obj
#         })

