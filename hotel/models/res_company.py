# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = 'res.company'

    check_in = fields.Datetime('Check In', required=False)
    check_out = fields.Datetime('Check Out', required=False)
    extra_room_charge_id = fields.Many2one('product.product',
                                           'Extra Room Site Seen Charge',
                                           required=True)
    default_hotel_policy = fields.Selection([('prepaid', 'On Booking'),
                                             ('manual', 'On Check In'),
                                             ('picking', 'On Checkout')],
                                            'Payment Policy', default='prepaid',
                                            help="Hotel policy for payment that "
                                                 "either the guest has to payment at "
                                                 "booking time or check-in "
                                                 "check-out time.")

    @api.constrains('check_in', 'check_out')
    def check_in_out_time(self):
        for res in self:
            if res.check_in or res.check_out < 0:
                raise ValidationError(
                    "You can not add check out time in negative !!")
            if res.check_out > 24:
                raise ValidationError("You can not add more that 24 hour")
            if res.check_in >= res.check_out:
                raise ValidationError("You can not add Check-in time is \
                greater than Check-out time")
