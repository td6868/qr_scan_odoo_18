# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class tinh_nang_qr_kho(models.Model):
#     _name = 'tinh_nang_qr_kho.tinh_nang_qr_kho'
#     _description = 'tinh_nang_qr_kho.tinh_nang_qr_kho'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

