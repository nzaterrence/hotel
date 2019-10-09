# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HotelRoom(models.Model):
    _inherit = 'hotel.room'

    updated_room_qty = fields.Integer('Update Qty', default=0)


class RoomAvailability(models.Model):
    _name = "room.availability"
    _description = 'Room Availability'
    _rec_name = 'company_id'

    @api.model
    def _default_date_from(self):
        return time.strftime('%Y-%m-01')

    @api.model
    def _default_date_to(self):
        return (datetime.today() + relativedelta(
            months=+1, day=1, days=-1)).strftime('%Y-%m-%d')

    company_id = fields.Many2one(
        'res.company', 'Hotel',
        default=lambda self: self.env['res.company']._company_default_get(
            'room.availability'),
        required=True)
    rooms_ids = fields.Many2many('hotel.room', string='Hotel Rooms')
    date_from = fields.Date(
        string='Date From', default=_default_date_from, required=True)
    date_to = fields.Date(
        string='Date To', default=_default_date_to, required=True)
    room_availability_ids = fields.One2many(
        'room.availability.line',
        'room_availability_id',
        'Rooms Availability')
    state = fields.Selection(
        [('draft', 'Draft'), ('close', 'Closed')],
        default='draft')

    @api.constrains('date_from', 'date_to')
    def check_in_out_dates(self):
        """
        When date_to is less then date_from or
        date_to should be greater than the date_from date.
        """
        if self.date_to and self.date_from:
            if self.date_to < self.date_from:
                raise ValidationError(_('End date should be greater \
                                         than Start date.'))

    def copy(self, *args, **argv):
        raise UserError(_('You cannot duplicate a room availability.'))


class RoomAvailabilityLine(models.Model):
    _name = "room.availability.line"
    _description = 'Room Availability Line'

    @api.multi
    @api.depends('date', 'company_id', 'room_availability_id_computed.date_to',
                 'room_availability_id_computed.date_from')
    def _compute_room_availability(self):
        """Links the room availability line to the corresponding room
        """
        for rec in self:
            room_available = self.env['room.availability'].search([
                ('date_to', '>=', rec.date),
                ('date_from', '<=', rec.date),
                ('company_id', '=', rec.company_id.id)], limit=1)
            if room_available:
                rec.room_availability_id_computed = room_available.id
                rec.room_availability_id = room_available.id

    def _search_room_availability(self, operator, value):
        assert operator == 'in'
        ids = []
        for room_available in self.env['room.availability'].browse(value):
            self._cr.execute("""
                    SELECT l.id
                        FROM room_availability_line l
                    WHERE %(date_to)s >= l.date
                        AND %(date_from)s <= l.date
                        AND %(company_id)s = l.company_id
                    GROUP BY l.id""", {
                'date_from': room_available.date_from,
                'date_to': room_available.date_to,
                'company_id': room_available.company_id.id})
            ids.extend([row[0] for row in self._cr.fetchall()])
        return [('id', 'in', ids)]

    room_availability_id_computed = fields.Many2one(
        'room.availability',
        string='Room Availabilities',
        compute='_compute_room_availability',
        index=True,
        ondelete='cascade',
        search='_search_room_availability')
    room_availability_id = fields.Many2one(
        'room.availability',
        compute='_compute_room_availability',
        store=True)
    room_category_id = fields.Many2one(
        'hotel.room', 'Room Category', required=True)
    date = fields.Date(
        'Date', default=fields.Date.context_today, required=True)
    room_qty = fields.Integer('Room Qty')
    room_cost_price = fields.Float('Room Price')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get(
            'room.availability'))
    close = fields.Boolean("Close")


class HotelReservationLine(models.Model):
    _inherit = "hotel_reservation.line"

    @api.multi
    def get_qty_from_avaliability(self, room, checkin, checkout):
        if not checkin:
            checkin = self.checkin
        if not checkout:
            checkout = self.checkout

        check_out_date = checkout
        if checkin != checkout:
            check_out_date = checkout + relativedelta(days=-1)
        self._cr.execute("""SELECT MIN(room_qty) FROM room_availability_line
                                WHERE room_category_id=%s
                                AND company_id=%s
                                AND date BETWEEN %s AND %s""",
                         (room.id, self.env.user.company_id.id, checkin, check_out_date))
        qty = self._cr.fetchone()[0]
        if qty:
            return qty
        return False

    @api.multi
    def check_room_closing_status(self, room, checkin=False, checkout=False):
        if not checkin:
            checkin = self.checkin
        if not checkout:
            checkout = self.checkout
        check_out_date = checkout
        if checkin != checkout:
            check_out_date = (self.checkout + relativedelta(days=-1))
        self._cr.execute("""SELECT id FROM room_availability_line
                            WHERE room_category_id=%s AND close=True
                            AND date BETWEEN %s AND %s
                            AND company_id=%s""",
                         (room.id, checkin, check_out_date,
                          self.env.user.company_id.id))
        status = self._cr.fetchone()
        if status:
            return True
        return False

    @api.onchange('checkin', 'checkout')
    def onchange_reservation_date(self):
        if not (self.reservation_id.checkin and self.reservation_id.checkout):
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select checkin checkout date!'),
            }
            return {'warning': warning}
        room_obj = self.env['hotel.room']
        if self.checkin or self.checkout:
            self.room_id = False
            room_list = room_obj.search([('status', '=', 'available')]).ids
            for room_id in room_list:
                room = room_obj.browse(room_id)
                self._cr.execute("""SELECT room_id, sum(room_qty) as qty FROM
                                hotel_room_move WHERE state != 'cancel' AND
                                room_id=%s AND (%s,%s) OVERLAPS
                                (check_in, check_out)
                                AND company_id=%s
                                GROUP BY room_id""",
                                 (room_id, self.checkin, self.checkout,
                                  self.company_id.id))
                data = self._cr.dictfetchone()
                room_qty = room.rooms_qty
                if self.check_room_closing_status(room):
                    room_list.remove(room_id)
                elif self.get_qty_from_avaliability(
                        room, self.checkin, self.checkout):
                    room_qty = self.get_qty_from_avaliability(
                        room, self.checkin, self.checkout)
                if data is not None and room_qty <= data.get('qty'):
                    room_list.remove(room_id)
            domain = {'room_id': [('id', 'in', room_list)]}
            return {'domain': domain}

    @api.multi
    def get_available_room_qty(self, room, checkin, checkout):
        self._cr.execute("""SELECT sum(room_qty) as qty FROM
                            hotel_room_move WHERE state != 'cancel'
                            AND room_id=%s AND
                            (%s,%s) OVERLAPS (check_in, check_out)
                            AND company_id=%s""",
                         (room.id, checkin, checkout, self.env.user.company_id.id))
        room_reserved_qty = self._cr.fetchone()[0]
        available_room_qty = room and room.rooms_qty
        room_avilability_qty = self.get_qty_from_avaliability(room, checkin, checkout)
        
        if room_avilability_qty:
            available_room_qty = room_avilability_qty
        if room_reserved_qty:
            available_room_qty -= room_reserved_qty
        return available_room_qty

    @api.multi
    def get_total_room_qty(self, room, checkin, checkout):
        self._cr.execute("""SELECT MIN(room_qty) FROM room_availability_line
                            WHERE room_category_id=%s AND
                            date BETWEEN %s AND %s
                            AND company_id=%s""",
                         (room.id, checkin, checkout, self.env.user.company_id.id))
        qty = self._cr.fetchone()[0]
        if qty:
            return qty
        return False

    @api.multi
    def get_room_value_from_daterange(self, room_id, start_date, end_date):
        datas = []
        hotel_room_obj = self.env['hotel.room']
        if room_id and start_date and end_date:
            date_start = datetime.strptime(
                start_date, DEFAULT_SERVER_DATE_FORMAT)
            date_end = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)
            room = hotel_room_obj.browse(room_id)
            while(date_start <= date_end):
                qty = self.get_total_room_qty(
                    room,
                    date_start.date(), date_start.date()) or room.rooms_qty
                booked_qty = self.get_booked_room_qty(
                    room_id, date_start.date(), date_start.date())
                room_status = self.check_room_closing_status(
                    room, date_start.date(), date_start.date())
                vals = {
                    'date': str(date_start.date()),
                    'total_qty': qty or 0,
                    'closed': room_status,
                    'booked': booked_qty or 0,
                    'avail': qty - booked_qty or 0
                }
                datas.append(vals)
                date_start += relativedelta(days=1)
        return datas


class HotelFolioLine(models.Model):
    _inherit = "hotel.folio.line"

    @api.multi
    def get_qty_from_avaliability(self, room, checkin, checkout):
        if not checkin:
            checkin = self.checkin
        if not checkout:
            checkout = self.checkout

        check_out_date = checkout
        if checkin != checkout:
            check_out_date = datetime.strptime(
                str(checkout), DEFAULT_SERVER_DATE_FORMAT) +\
                relativedelta(days=-1)
        self._cr.execute("""SELECT MIN(room_qty) FROM room_availability_line
                            WHERE room_category_id=%s AND
                            date BETWEEN %s AND %s
                            AND company_id=%s""",
                         (room.id, checkin, check_out_date,
                          self.env.user.company_id.id))
        qty = self._cr.fetchone()[0]
        if qty:
            return qty
        return False

    @api.multi
    def check_room_closing_status(self, room):
        for rec in self:
            check_out_date = rec.checkout_date + relativedelta(days=-1)
            self._cr.execute("""SELECT id FROM room_availability_line
                                WHERE room_category_id=%s AND close=True
                                AND date BETWEEN %s AND %s
                                AND company_id=%s""",
                             (room.id, rec.checkin_date,
                              check_out_date, self.env.user.company_id.id))
            status = self._cr.fetchone()
            if status:
                return True
        return False

    @api.onchange('checkin_date', 'checkout_date')
    def onchange_folio_date(self):
        if self.checkin_date and self.checkout_date:
            room_obj = self.env['hotel.room']
            self.room_id = False
            checkin_date = self.checkin_date
            checkout_date = self.checkout_date
            dur = checkout_date - checkin_date
            self.product_uom_qty = dur.days
            room_list = room_obj.search([('status', '=', 'available')]).ids
            for room_id in room_list:
                room = room_obj.browse(room_id)
                self._cr.execute("""SELECT room_id, sum(room_qty) as qty FROM
                                hotel_room_move WHERE  state != 'cancel'
                                AND room_id = %s
                                AND (%s,%s) OVERLAPS
                                (check_in, check_out) and state != 'cancel'
                                AND company_id=%s
                                GROUP BY room_id""",
                                 (room_id, self.checkin_date,
                                  self.checkout_date, self.env.user.company_id.id))
                data = self._cr.dictfetchone()
                room_qty = room and room.rooms_qty
                if self.check_room_closing_status(room):
                    room_list.remove(room_id)

                elif self.get_qty_from_avaliability(room, self.checkin_date,
                                                    self.checkout_date):
                    room_qty = self.get_qty_from_avaliability(room, self.checkin_date,
                                                              self.checkout_date)
                if data is not None and room and room_qty <= data.get('qty'):
                    room_list.remove(data.get('room_id'))

            domain = {'room_id': [('id', 'in', room_list)]}
            return {'domain': domain}
