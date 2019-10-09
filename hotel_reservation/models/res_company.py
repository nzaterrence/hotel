# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models

Validation_Selection = [(1, 'Yes'),(0, 'No')]

class ResCompany(models.Model):
    _inherit = 'res.company'

    hotel_policy = fields.Html('Hotel Policy')
    adults_details_validation = fields.Selection(Validation_Selection,
                                                 default=0,
                                                 string="Adults Details Validation")
    send_confirmation_email = fields.Selection(Validation_Selection, default=0,
                                               string="Automatic Send Confirmation Email ")
