"""Wizard for updating room availability."""

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
# from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class UpdateAvailableRoomQty(models.TransientModel):
    """Update the room availability as per the dates."""

    _name = "update.available.room.qty"
    _description = "Update Room Available Qty"

    def _default_date_to(self):
        return str(datetime.today() + relativedelta(days=1))

    room_availability_id = fields.Many2one(
        'room.availability', 'Room Availability', required=True)
    date_from = fields.Date(
        string='Date From', default=str(datetime.today()), required=True)
    date_to = fields.Date(
        string='Date To', default=_default_date_to, required=True)
    room_qty_line_ids = fields.One2many(
        'update.available.room.qty.line', 'room_qty_id', string='Update Qty')

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
        """To get the default values in room availability."""
        res = super(UpdateAvailableRoomQty, self).default_get(fields)
        if self.env.context.get('active_id') and\
                self.env.context.get('active_model') == 'room.availability'\
                and self.env.context.get('active_id'):
            res['room_availability_id'] = self.env[
                'room.availability'].browse(self.env.context['active_id']).id
        return res

    @api.multi
    def update_room_qty(self):
        """Update the room quantities."""
        availability_line_obj = self.env['room.availability.line']
        period_list = []
        for rec in self:
            date_to = datetime.strptime(
                str(rec.date_to), DEFAULT_SERVER_DATE_FORMAT)
            # date_to = rec.date_to
            # date_from = rec.date_from
            date_from = datetime.strptime(
                str(rec.date_from), DEFAULT_SERVER_DATE_FORMAT)
            days_between = (date_to - date_from).days
            date_list = [(date_from + timedelta(days=i))
                         for i in range(0, days_between + 1)]
            for line in rec.room_qty_line_ids:
                for i in date_list:
                    line_rec = availability_line_obj.search([
                        ('date', '=', i.date()),
                        ('room_category_id', '=', line.hotel_room_id.id),
                        ('room_availability_id', '=', rec.room_availability_id.id)])

                    ttl_qty = line_rec and line_rec.room_qty or line.hotel_room_id.rooms_qty

                    if line.operator == 'plus':
                        ttl_qty += line.value
                    elif line.operator == 'minus':
                        ttl_qty -= line.value
                    elif line.operator == 'equals':
                        ttl_qty = line.value

                    if ttl_qty > line.hotel_room_id.rooms_qty:
                        raise ValidationError(_
                                              ("The room %s can not be\
                                                    updated. The maximum\
                                                    quantity is %d" % (line.hotel_room_id.name, line.hotel_room_id.rooms_qty)))

                    if line_rec:
                        line_rec.update({'room_qty': ttl_qty})
                    else:
                        vals = {
                            'room_availability_id':
                            rec.room_availability_id.id,
                            'date': i.date(),
                            'room_category_id': line.hotel_room_id.id,
                            'company_id':
                            rec.room_availability_id.company_id.id,
                            'room_qty': ttl_qty,
                        }
                        period_list.append((0, 0, vals))
            rec.room_availability_id.room_availability_ids = period_list
        return {'type': 'ir.actions.act_window_close'}


class UpdateAvailableRoomQtyLine(models.TransientModel):
    """Class for updating room quantity lines."""

    _name = "update.available.room.qty.line"
    _description = 'Update Available Room Qty Line'

    @api.constrains('value')
    def value_negative(self):
        """To check that value should not be negative."""
        for recs in self:
            if recs.value < 0:
                raise ValidationError(_("Value should not be negative"))

    room_qty_id = fields.Many2one(
        'update.available.room.qty', string="Update Room Qty")
    hotel_room_id = fields.Many2one('hotel.room', 'Room')
    operator = fields.Selection([('plus', '+'),
                                 ('minus', '-'),
                                 ('equals', '=')], default="equals")
    value = fields.Integer("Value")
