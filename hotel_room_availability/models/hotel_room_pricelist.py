# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class RoomPricelist(models.Model):
    _name = "room.pricelist"
    _description = 'Room Pricelist'
    _rec_name = 'company_id'

    def _default_date_from(self):
        return datetime.today().strftime('%Y-%m-%d')

    def _default_date_to(self):
        return (
            datetime.today() + relativedelta(days=+15)).strftime('%Y-%m-%d')

    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get(
            'room.pricelist'),
        required=True)
    rooms_ids = fields.Many2many('hotel.room', string='Hotel Rooms')
    date_from = fields.Date(
        string='Date From', default=_default_date_from, required=True)
    date_to = fields.Date(
        string='Date To', default=_default_date_to, required=True)
    room_pricelist_ids = fields.One2many(
        'room.pricelist.line',
        'room_pricelist_id',
        'Rooms Pricelist')
    state = fields.Selection(
        [('draft', 'Draft'), ('close', 'Closed')],
        default='draft')

    @api.constrains('date_to', 'date_from', 'company_id')
    def _check_pricelist_date(self):
        for rec in self:
            company_id = rec.company_id
            if company_id:
                self.env.cr.execute('''
                    SELECT id
                    FROM room_pricelist
                    WHERE (date_from <= %s and %s <= date_to)
                        AND company_id=%s
                        AND id <> %s''',
                                    (rec.date_to,
                                     rec.date_from, company_id.id, rec.id))
                if any(self.env.cr.fetchall()):
                    raise ValidationError(
                        _('''You can't create 2 Pricelist that overlap!.'''))

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
        raise UserError(_('You cannot duplicate a room Pricelist.'))


class RoomPricelistLine(models.Model):
    _name = "room.pricelist.line"
    _description = 'Room Pricelist Line'

    @api.depends('date', 'company_id', 'room_pricelist_id_computed.date_to',
                 'room_pricelist_id_computed.date_from')
    def _compute_room_pricelist(self):
        """Links the room pricelist line to the corresponding room
        """
        for rec in self:
            room_pricelist = self.env['room.pricelist'].search([
                ('date_to', '>=', rec.date),
                ('date_from', '<=', rec.date),
                ('company_id', '=', rec.company_id.id)], limit=1)
            if room_pricelist:
                rec.room_pricelist_id_computed = room_pricelist.id
                rec.room_pricelist_id = room_pricelist.id

    def _search_room_pricelist(self, operator, value):
        assert operator == 'in'
        ids = []
        for room in self.env['room.pricelist'].browse(value):
            self._cr.execute("""
                    SELECT l.id
                        FROM room_pricelist_line l
                    WHERE %(date_to)s >= l.date
                        AND %(date_from)s <= l.date
                        AND %(company_id)s = l.company_id
                    GROUP BY l.id""", {'date_from': room.date_from,
                                       'date_to': room.date_to,
                                       'company_id': room.company_id.id})
            ids.extend([row[0] for row in self._cr.fetchall()])
        return [('id', 'in', ids)]

    room_pricelist_id_computed = fields.Many2one(
        'room.pricelist',
        string='Room Pricelists',
        compute='_compute_room_pricelist',
        index=True,
        ondelete='cascade',
        search='_search_room_pricelist')
    room_pricelist_id = fields.Many2one(
        'room.pricelist',
        compute='_compute_room_pricelist',
        store=True)
    room_id = fields.Many2one('hotel.room', 'Room', required=True)
    date = fields.Date(
        'Date', default=fields.Date.context_today, required=True)
    room_price = fields.Integer('Room Price')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env[
            'res.company']._company_default_get('room.pricelist'))


class HotelReservationLine(models.Model):
    _inherit = "hotel_reservation.line"

    @api.multi
    def get_price_from_rateplan(self, room):
        for rec in self:
            check_out_date = rec.checkout + relativedelta(days=-1)
            if room:
                self._cr.execute(
                    """SELECT AVG(room_price) FROM room_pricelist_line
                    WHERE room_id=%s AND date BETWEEN %s AND %s
                    AND company_id=%s""",
                    (room.id, rec.checkin, check_out_date, rec.company_id.id))
                rate_plan = self._cr.fetchone()[0]
                if rate_plan:
                    return rate_plan
        return False

    @api.multi
    def get_total_room_price(self, room, rateplan_date):
        self._cr.execute(
            """SELECT AVG(room_price) FROM room_pricelist_line
            WHERE room_id=%s AND date=%s""",
            (room.id, rateplan_date))
        rate = self._cr.fetchone()[0]
        if rate:
            return rate
        return False

    @api.model
    def get_room_price_from_daterange(self, room_id, start_date, end_date):
        datas = []
        hotel_room_obj = self.env['hotel.room']
        if room_id and start_date and end_date:
            date_start = datetime.strptime(
                start_date, DEFAULT_SERVER_DATE_FORMAT)
            date_end = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)
            room = hotel_room_obj.browse(room_id)
            while(date_start <= date_end):
                price = self.get_total_room_price(
                    room, date_start.date()) or room.list_price
                vals = {
                    'date': str(date_start.date()),
                    'price': price or 0,
                }
                datas.append(vals)
                date_start += relativedelta(days=1)
        return datas

    @api.onchange('room_id')
    def onchange_room_id(self):
        vals = {}
        domain = {}
        if self.room_id:
            vals['qty'] = 1.0

        room = self.room_id.with_context(
            lang=self.reservation_id.partner_id.lang,
            partner=self.reservation_id.partner_id.id,
            quantity=vals.get('qty') or self.qty,
            date=self.reservation_id.date_order,
            uom=self.room_id.product_id.uom_id.id,
            pricelist=self.reservation_id.pricelist_id.id
        )

        vals['name'] = room.name
        vals['room_number_id'] = []
        self._compute_tax_id()

        if self.reservation_id.pricelist_id and self.reservation_id.partner_id:
            if self.get_price_from_rateplan(room):
                vals['price_unit'] = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self.get_price_from_rateplan(room),
                    room.taxes_id, self.tax_id,
                    self.company_id)
            else:
                vals['price_unit'] = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self._get_display_price(room),
                    room.taxes_id, self.tax_id,
                    self.company_id)
        self.update(vals)
        if self.checkin and self.checkout and self.room_id:
            self._cr.execute("""SELECT room_number_id FROM
                                hotel_room_move_line WHERE (%s,%s) OVERLAPS
                                (check_in, check_out) AND state != 'cancel'
                                AND company_id=%s
                                """,
                             (self.checkin, self.checkout, self.company_id.id))
            datas = self._cr.fetchall()
            record_ids = [data[0] for data in datas]
            domain = {'room_number_id': [('id', 'not in', record_ids),
                                         ('room_id', '=', self.room_id.id),
                                         ('state', '=', 'available')]}
        return {'domain': domain}

    @api.onchange('qty')
    def room_qty_change(self):
        if not self.qty or not self.room_id:
            self.price_unit = 0.0
            return
        if self.reservation_id.pricelist_id and self.reservation_id.partner_id:
            room = self.room_id.with_context(
                lang=self.reservation_id.partner_id.lang,
                partner=self.reservation_id.partner_id.id,
                quantity=self.qty,
                date=self.reservation_id.date_order,
                uom=self.room_id.product_id.uom_id.id,
                pricelist=self.reservation_id.pricelist_id.id
            )
            if self.get_price_from_rateplan(room):
                self.price_unit = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self.get_price_from_rateplan(room),
                    room.taxes_id, self.tax_id,
                    self.company_id)
            else:
                self.price_unit = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self._get_display_price(room),
                    room.taxes_id, self.tax_id,
                    self.company_id)


class HotelFolioLine(models.Model):
    _inherit = 'hotel.folio.line'

    @api.multi
    def get_price_from_rateplan(self, room):
        for rec in self:
            check_out_date = rec.checkout_date + relativedelta(days=-1)
            if room:
                self._cr.execute(
                    """SELECT AVG(room_price) FROM room_pricelist_line
                    WHERE room_id=%s AND date BETWEEN %s AND %s
                    AND company_id=%s""",
                    (room.id, rec.checkin_date, check_out_date,
                     self.env.user.company_id.id))
                rate_plan = self._cr.fetchone()[0]
                if rate_plan:
                    return rate_plan
        return False

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [
            ('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or \
                (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
#            vals['product_uom_qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.folio_id.partner_id.lang,
            partner=self.folio_id.partner_id.id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.folio_id.date_order,
            pricelist=self.folio_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        result = {'domain': domain}

        title = False
        message = False
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False
                return result

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        self._compute_tax_id()

        if self.folio_id.pricelist_id and self.folio_id.partner_id:
            if self.get_price_from_rateplan(self.room_id):
                vals['price_unit'] = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self.get_price_from_rateplan(self.room_id),
                    product.taxes_id, self.tax_id,
                    self.company_id)
            else:
                vals['price_unit'] = self.env[
                    'account.tax']._fix_tax_included_price_company(
                        self._get_display_price(product),
                    product.taxes_id, self.tax_id,
                    self.company_id)
        self.update(vals)
        return result
