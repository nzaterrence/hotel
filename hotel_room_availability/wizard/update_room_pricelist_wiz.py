"""Wizard for updating the pricelist of hotel rooms."""

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class UpdateRoomPricelist(models.TransientModel):
    """Class to update the room pricelist lines."""

    _name = "update.room.pricelist"
    _description = "Update Room Pricelist"

    def _default_date_to(self):
        return str(datetime.today() + relativedelta(days=1))

    room_pricelist_id = fields.Many2one(
        'room.pricelist', 'Room pricelist', required=True)
    date_from = fields.Date(
        string='Date From', default=str(datetime.today()), required=True)
    date_to = fields.Date(
        string='Date To', default=_default_date_to, required=True)
    room_pricelist_line_ids = fields.One2many(
        'update.room.pricelist.line', 'room_pricelist_id',
        string='Update Pricelist')

    @api.constrains('date_from', 'date_to')
    def check_start_end_date(self):
        """
        When enddate should be greater than the startdate.
        """
        if self.date_to and self.date_from:
            if self.date_to < self.date_from:
                raise ValidationError(_('End Date should be greater \
                                         than Start Date.'))

    @api.model
    def default_get(self, fields):
        """To get the default prices in the pricelist."""
        res = super(UpdateRoomPricelist, self).default_get(fields)
        if self.env.context.get('active_id') and\
                self.env.context.get('active_model') == 'room.pricelist' and\
                self.env.context.get('active_id'):
            res['room_pricelist_id'] = self.env[
                'room.pricelist'].browse(self.env.context['active_id']).id
        return res

    @api.multi
    def update_room_price(self):
        """To update the price prices."""
        pricelist_line_obj = self.env['room.pricelist.line']
        for rec in self:
            period_list = []
            date_to = datetime.strptime(
                str(rec.date_to), DEFAULT_SERVER_DATE_FORMAT)
            date_from = datetime.strptime(
                str(rec.date_from), DEFAULT_SERVER_DATE_FORMAT)
            days_between = (date_to - date_from).days
            date_list = [(date_from + timedelta(days=i))
                         for i in range(0, days_between + 1)]
            for line in rec.room_pricelist_line_ids:
                for i in date_list:
                    line_rec = pricelist_line_obj.search([
                        ('date', '=', i.date()),
                        ('room_id', '=', line.hotel_room_id.id),
                        ('room_pricelist_id', '=',
                            rec.room_pricelist_id.id), ])

                    ttl_price = line_rec and line_rec.room_price or\
                        line.hotel_room_id.product_id.lst_price

                    if line.operator == 'fix_rate':
                        ttl_price = line.price
                    elif line.operator == '%':
                        ttl_price += ttl_price * line.price // 100

                    if line_rec:
                        line_rec.update({'room_price': ttl_price})
                    else:
                        vals = {
                            'room_pricelist_id': rec.room_pricelist_id.id,
                            'date': i.date(),
                            'room_id': line.hotel_room_id.id,
                            'company_id':
                            rec.room_pricelist_id.company_id.id,
                            'room_price': ttl_price,
                        }
                        period_list.append((0, 0, vals))
            rec.room_pricelist_id.room_pricelist_ids = period_list
        return {'type': 'ir.actions.act_window_close'}


class UpdateRoomPricelistLine(models.TransientModel):
    """Class for updating room quantity lines."""
    _name = "update.room.pricelist.line"
    _description = 'Update Room Pricelist Line'

    @api.constrains('price')
    def price_negative(self):
        """To check that price should not be negative."""
        for recs in self:
            if recs.price < 0:
                raise ValidationError(_("Price should not be negative"))

    room_pricelist_id = fields.Many2one(
        'update.room.pricelist', string="Update Room Pricelist")
    hotel_room_id = fields.Many2one('hotel.room', 'Room')
    operator = fields.Selection([('fix_rate', 'Fix Rate'),
                                 ('%', '%')], default="fix_rate")
    price = fields.Integer("Price")
