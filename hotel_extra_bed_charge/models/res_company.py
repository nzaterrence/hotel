# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    extra_bed_charge_id = fields.Many2one('product.product', 'Extra Bed Charge',
                                          required=True)
