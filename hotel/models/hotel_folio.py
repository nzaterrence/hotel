# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt, DEFAULT_SERVER_DATE_FORMAT

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from decimal import Decimal
import odoo.addons.decimal_precision as dp

import logging

_logger = logging.getLogger(__name__)
try:
    import forex_python
    from forex_python.converter import CurrencyRates
except Exception as e:
    _logger.error("#WKDEBUG-1  python forex_python library not installed.")


class HotelFolio(models.Model):
    _name = 'hotel.folio'
    _description = 'Hotel folio'

    @api.multi
    def name_get(self):
        res = []
        fname = ''
        for rec in self:
            if rec.order_id:
                fname = str(rec.name)
                res.append((rec.id, fname))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        args += ([('name', operator, name)])
        folio = self.search(args, limit=100)
        return folio.name_get()

    @api.model
    def _needaction_count(self, domain=None):
        """
         Show a count of draft state folio on the menu badge.
         @param self: object pointer
        """
        return self.search_count([('state', '=', 'draft')])

    @api.multi
    def _compute_count_currency(self):
        """Compute field for smart button(one2many)."""
        for recs in self:
            recs.count_currency = len(recs.currrency_ids.ids)

    @api.multi
    def copy(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        return super(HotelFolio, self).copy(default=default)

    @api.depends('checkin_date', 'checkout_date')
    def compute_no_days(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                checkin_date = datetime.strptime(str(rec.checkin_date),
                                                 DEFAULT_SERVER_DATE_FORMAT)
                checkout_date = datetime.strptime(str(rec.checkout_date),
                                                  DEFAULT_SERVER_DATE_FORMAT)
                dur = checkout_date - checkin_date
                rec.stay_days = dur.days

    @api.depends('folio_lines.checkin_date', 'folio_lines.checkout_date')
    def compute_check_in_out(self):
        for rec in self:
            checkin_list = []
            checkout_list = []
            for line in rec.folio_lines:
                if line.checkin_date:
                    checkin_list.append(line.checkin_date)
                if line.checkout_date:
                    checkout_list.append(line.checkout_date)
            rec.update({
                       'checkin_date': checkin_list and min(checkin_list) or
                       str(datetime.today()),
                       'checkout_date': checkout_list and max(checkout_list) or
                       str((datetime.today() + timedelta(days=1)))
                       })

    @api.depends('order_id.state')
    def _mapping_state(self):
        for rec in self:
            rec.status = rec.state
            
    name = fields.Char('Folio Number', readonly=True, index=True,
                       default='New')
    order_id = fields.Many2one('sale.order', 'Order', delegate=True,
                               required=True, ondelete='cascade')
    checkin_date = fields.Date('Check In', readonly=True,
                               compute="compute_check_in_out",
                               store=True, track_visibility='always')
    checkout_date = fields.Date('Check Out', readonly=True,
                                compute="compute_check_in_out",
                                store=True, track_visibility='always')
    folio_lines = fields.One2many('hotel.folio.line', 'folio_id',
                                  readonly=True,
                                  states={'draft': [('readonly', False)],
                                          'sent': [('readonly', False)],
                                          'sale': [('readonly', False)]},
                                  help="Hotel room reservation detail.")
    service_lines = fields.One2many('hotel.service.line', 'folio_id',
                                    readonly=True,
                                    states={'draft': [('readonly', False)],
                                            'sent': [('readonly', False)],
                                            'sale': [('readonly', False)]},
                                    help="Hotel services detail provide to"
                                         "customer and it will include in "
                                         "main Invoice.")
    hotel_policy = fields.Selection([('prepaid', 'On Booking'),
                                     ('manual', 'On Check In'),
                                     ('picking', 'On Checkout')],
                                    'Payment Policy', default=lambda self: self.env.user.company_id.default_hotel_policy,
                                    help="Hotel policy for payment that "
                                         "either the guest has to payment at "
                                         "booking time or check-in "
                                         "check-out time.")
    stay_days = fields.Integer(compute="compute_no_days",
                               string="Duration in Days", copy=False,
                               readonly=True, store=True,
                               track_visibility='always',
                               old_name='duration')
    currrency_ids = fields.One2many('currency.exchange', 'folio_no',
                                    readonly=True)
    hotel_invoice_id = fields.Many2one('account.invoice', 'Invoice',
                                       copy=False)
    duration_dummy = fields.Float('Duration Dummy')
    count_currency = fields.Integer(compute="_compute_count_currency")
    room_moves_ids = fields.Many2many('hotel.room.move',
                                      'hotel_folio_room_move_rel',
                                      'folio_id', 'room_move_id',
                                      string='Room Moves',
                                      readonly=True, copy=False)
    status = fields.Selection([('draft', 'Draft'),
                              ('sent', 'Sent'),
                              ('sale', 'Confirm'),
                              ('done', 'Locked'),
                              ('cancel', 'Cancelled'),
                                ], string='Status', readonly=True,
                             copy=False, index=True, track_visibility='onchange',
                             default='draft',
                             compute="_mapping_state")


    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment term
        - Invoice address
        - Delivery address
        """
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
            })
            return

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False,
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }
        if self.env.user.company_id.sale_note:
            values['note'] = self.with_context(
                lang=self.partner_id.lang).env.user.company_id.sale_note

        if self.partner_id.user_id:
            values['user_id'] = self.partner_id.user_id.id
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        self.update(values)

    @api.multi
    def go_to_currency_exchange(self):
        '''
         When Money Exchange button is clicked then this method is called.
        -------------------------------------------------------------------
        @param self: object pointer
        '''
        action = self.env.ref('hotel.open_currency_exchange_tree').read()[0]
        ctx = dict(self._context)
        for rec in self:
            curr_exchanges = rec.mapped('currrency_ids')
            if rec.partner_id.id and len(rec.folio_lines) != 0:
                ctx.update({
                    'default_folio_no': rec.id,
                    'default_guest_name': rec.partner_id.id,
                    'default_room_no': rec.folio_lines[0].product_id.name,
                    'default_hotel': rec.warehouse_id.id
                })
            else:
                raise ValidationError(_('Please Reserve Any Room.'))
            action.update({'context': ctx})
            if len(curr_exchanges) > 1:
                action['domain'] = [('id', 'in', curr_exchanges.ids)]
            elif len(curr_exchanges) == 1:
                action['views'] = [
                    (rec.env.ref('hotel.view_currency_exchange_form').id,
                     'form')]
                action['res_id'] = curr_exchanges.id
            else:
                return {'name': _('Currency Exchange'),
                        'context': ctx,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'currency.exchange',
                        'views': [(rec.env.ref(
                            'hotel.view_currency_exchange_form').id,
                            'form')],
                        'type': 'ir.actions.act_window',
                        'target': 'current',
                        }
        return action

    @api.constrains('folio_lines')
    def folio_room_lines(self):
        '''
        This method is used to validate the room_lines.
        ------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        folio_rooms = []
        for rec in self:
            for room_no in rec.folio_lines.mapped('room_number_id'):
                lines = rec.folio_lines.search([('room_number_id', '=', room_no.id),
                                                ('folio_id', '=', rec.id)])
                for line in lines:
                    record = lines.search([('id', '!=', line.id),
                                           ('id', 'in', lines.ids),
                                           ('checkin_date', '>=',
                                            line.checkin_date),
                                           ('checkout_date', '<=',
                                            line.checkout_date),
                                           ('room_number_id', '=', room_no.id)])
                    if record:
                        raise ValidationError(_('''Room Duplicate Exceeded!,
                                                You Cannot Take Same %s Room Twice!''') %
                                              (room_no.name))

    @api.constrains('folio_lines', 'service_lines')
    def check_duration_range(self):
        """
        When checkin date is greater than or
        equal to checkout date in reservation_line.
        """
        for folio_line in self.folio_lines:
            if folio_line.checkin_date >= folio_line.checkout_date:
                raise ValidationError(_('Folio line checkout date should be greater \
                                        than checkin date.'))
            if folio_line.checkin_date < self.checkin_date:
                raise ValidationError(_('Enter valid folio line checkin date.'))

            if folio_line.checkout_date > self.checkout_date:
                raise ValidationError(_('Enter valid folio line checkout date.'))

        for service_line in self.service_lines:
            if service_line.checkin and service_line.checkout:
                if service_line.checkin >= service_line.checkout:
                    raise ValidationError(_('Service line checkout date should be greater \
                                            than checkin date.'))
                if service_line.checkin < self.checkin_date:
                    raise ValidationError(_('Enter valid service line checkin date.'))
    
                if service_line.checkout > self.checkout_date:
                    raise ValidationError(_('Enter valid service line checkout date.'))

    def _set_room_amenities(self, rec):
        service_line_obj = self.env['hotel.service.line']
        extra_room_qty = 0
        extra_room_price = 0.0
        for line in rec.folio_lines:
            if line.room_id and not line.service_line_bool:
                for amenity in line.room_id.room_amenities:
                    qty = 1.0
                    if amenity.product_id and amenity.product_id.per_night_bool and\
                            line.checkin_date and line.checkout_date:
                        checkin_date = datetime.strptime(line.checkin_date,
                                                         DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(line.checkout_date,
                                                          DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        qty = dur.days
                    vals = {
                        'checkin': line.checkin_date,
                        'checkout': line.checkout_date,
                        'folio_id': rec.id,
                        'product_id': amenity.product_id.id,
                        'name': amenity.product_id.name,
                        'product_uom_qty': qty,
                        'price_unit': amenity.lst_price,
                        'product_uom': amenity.product_id.uom_id.id,
                        'tax_id': [(6, 0, amenity.product_id.taxes_id.ids)]
                        }
                    service_line_obj.create(vals)
                    line.service_line_bool = True
                # it's for extra room service added
                if line.room_number_id and line.room_number_id.extra_charge > 0:
                    extra_room_qty += 1
                    extra_room_price += line.room_number_id.extra_charge
            extra_room_product = rec.company_id.extra_room_charge_id
            if extra_room_qty > 0 and extra_room_product and rec.folio_lines and not line.service_line_bool:
                extra_room_line = rec.service_lines.search([('product_id', '=', extra_room_product.id or False),
                                                        ('folio_id', '=', self.id),
                                                        ('extra_bed_service_line_bool', '=', False)],
                                                       limit=1)
                if extra_room_line:
                    room_qty = extra_room_line.product_uom_qty + extra_room_qty
                    price_unit = 0.0
                    if room_qty > 0:
                        price_unit = (extra_room_line.price_unit +
                                      extra_room_price) / room_qty
                    if amenity.product_id and amenity.product_id.per_night_bool and\
                            line.checkin_date and line.checkout_date:
                        checkin_date = datetime.strptime(line.checkin_date,
                                                         DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(line.checkout_date,
                                                          DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        room_qty = room_qty * dur.days
                    extra_room_line.update({
                        'product_uom_qty': room_qty,
                        'price_unit': price_unit or 0.0,
                        'extra_bed_service_line_bool':True  
                    })
                else:
                    price_unit = 0.0
                    if extra_room_qty > 0:
                        price_unit = extra_room_price / extra_room_qty
                    if extra_room_product and extra_room_product.per_night_bool and\
                            line.checkin_date and line.checkout_date:
                        checkin_date = datetime.strptime(line.checkin_date,
                                                         DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(line.checkout_date,
                                                          DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        extra_room_qty = extra_room_qty * dur.days
                    service_vals = {
                                'checkin': line.checkin_date,
                                'checkout': line.checkout_date,
                                'product_id': extra_room_product.id,
                                'name': extra_room_product.name,
                                'folio_id': rec.id,
                                'product_uom_qty': extra_room_qty,
                                'price_unit': price_unit,
                                'product_uom': extra_room_product.uom_id.id,
                                'extra_bed_service_line_bool': True,
                                'tax_id': [(6, 0, extra_room_product.taxes_id.ids)]
                                }
                    line.service_line_bool = True
                    service_line_obj.create(service_vals)

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('hotel.folio')
        res = super(HotelFolio, self).create(vals)
        if res and vals.get('folio_lines') and not self._context.get('set_room_aminities'):
            self._set_room_amenities(res)
        return res

    @api.multi
    def write(self, vals):
        res = super(HotelFolio, self).write(vals)
        if res and vals.get('folio_lines') and not self._context.get('set_room_aminities'):
            for rec in self:
                self._set_room_amenities(rec)
        return res
    
    @api.multi
    def button_dummy(self):
        return True

    @api.multi
    def action_done(self):
        '''
            This method is used for to set folio into done state and
            also process the flow of stock picking for service line product
        '''

        for folio in self:
            for picking in folio.picking_ids:
                if picking.state not in ['done', 'cancel']:
                    wiz_data = picking.button_validate()
                    if wiz_data and wiz_data.get('res_model', False) and \
                            wiz_data.get('res_id', False):
                        self.env[wiz_data['res_model']].browse(
                            wiz_data['res_id']).process()
            folio.room_moves_ids.sudo().write({'state': 'done'})
            folio.state = 'done'

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        '''
        @param self: object pointer
        '''
        invoice_id = (self.order_id.action_invoice_create(grouped=False,
                                                          final=False))
        return invoice_id

    @api.multi
    def action_cancel(self):
        """
        @param self: object pointer
        """
        if not self.order_id:
            raise ValidationError(_('Order id is not available'))
        return self.order_id.action_cancel()

    @api.multi
    def action_confirm(self):
        room_move_obj = self.env['hotel.room.move']
        folio_line_obj = self.env['hotel.folio.line']
        for folio in self:
            for room in folio.folio_lines.mapped('room_id'):
                vals = {}
                lines = folio_line_obj.search([('room_id', '=', room.id),
                                               ('folio_id', '=', folio.id)])
                move_lines = []
                for line in lines:
                    folio._cr.execute("""SELECT room_number_id FROM
                                hotel_room_move_line WHERE (%s,%s) OVERLAPS
                                (check_in, check_out) AND state != 'cancel' AND
                                (folio_line_id != %s OR folio_line_id is Null) AND
                                room_number_id=%s AND company_id=%s
                                """, (line.checkin_date, line.checkout_date, line.id,
                                      line.room_number_id.id,
                                      line.company_id.id))
                    datas = folio._cr.fetchone()
                    if datas is not None:
                        raise ValidationError(_('''Room Reserved!,
                                                %s room have already reserved for another customer,
                                                Kindly select another room''') % (line.room_id.name))
                    move_lines.append(
                        (0, 0, {
                            'room_number_id': line.room_number_id.id,
                            'folio_line_id': line.id,
                        }))
                vals.update({
                    'check_in': folio.checkin_date,
                    'check_out': folio.checkout_date,
                    'room_id': room.id,
                    'room_qty': len(lines),
                    'state': 'assigned',
                    'room_move_line_ids': move_lines,
                    'folios_ids': [(4, folio.id)],
                    'company_id': folio.company_id.id
                })
                room_move_obj.create(vals)
            folio.order_id.action_confirm()

    @api.multi
    def action_cancel_draft(self):
        '''
        @param self: object pointer
        '''
        if not len(self._ids):
            return False
        query = "select id from sale_order_line \
        where order_id IN %s and state=%s"
        self._cr.execute(query, (tuple(self._ids), 'cancel'))
        cr1 = self._cr
        line_ids = map(lambda x: x[0], cr1.fetchall())
        self.write({'state': 'draft', 'invoice_ids': []})
        sale_line_obj = self.env['sale.order.line'].browse(line_ids)
        sale_line_obj.write({'invoiced': False, 'state': 'draft',
                             'invoice_lines': [(6, 0, [])]})
        return True

    @api.multi
    def action_view_invoice(self):
        invoices = self.order_id.mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [
                (self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def recalculate_prices(self):
        self.order_id.recalculate_prices()


class HotelFolioLine(models.Model):
    _name = 'hotel.folio.line'
    _description = 'Hotel folio line'

    order_line_id = fields.Many2one('sale.order.line', 'Sale Order Line',
                                    required=True, delegate=True,
                                    ondelete='cascade')
    folio_id = fields.Many2one('hotel.folio', 'Folio',
                               ondelete='cascade', required=True)
    checkin_date = fields.Date('Check In')
    checkout_date = fields.Date('Check Out')
    room_id = fields.Many2one('hotel.room', 'Room Type', copy=False,
                              ondelete="restrict", change_default=True,
                              required=True)
    room_number_id = fields.Many2one('hotel.room.number', string='Room', copy=False,
                                     domain="[('room_id', '=', room_id),('state', '=', 'available')]",
                                     ondelete="restrict", required=True)
    service_line_bool = fields.Boolean('Service Bool')

    @api.onchange('checkin_date', 'checkout_date')
    def onchange_folio_date(self):
        if self.checkin_date and self.checkout_date:
            room_obj = self.env['hotel.room']
            self.room_id = False
            checkin_date = datetime.strptime(str(self.checkin_date),
                                             DEFAULT_SERVER_DATE_FORMAT)
            checkout_date = datetime.strptime(str(self.checkout_date),
                                              DEFAULT_SERVER_DATE_FORMAT)
            dur = checkout_date - checkin_date
            self.product_uom_qty = dur.days
            room_list = room_obj.search([('status', '=', 'available')]).ids
            for room_id in room_list:
                room = room_obj.browse(room_id)
                self._cr.execute("""SELECT room_id, sum(room_qty) as qty FROM
                                hotel_room_move WHERE (%s,%s) OVERLAPS
                                (check_in, check_out) AND state != 'cancel'
                                AND room_id = %s and company_id=%s
                                GROUP BY room_id""",
                                 (self.checkin_date, self.checkout_date, room_id,
                                  self.company_id.id))
                data = self._cr.dictfetchone()
                room_qty = room.rooms_qty
                if data is not None and room_qty <= data.get('qty'):
                    room_list.remove(data.get('room_id'))
            domain = {'room_id': [('id', 'in', room_list)]}
            return {'domain': domain}

    @api.onchange('room_id')
    def onchange_room(self):
        result = {'domain': {}}
        if self.room_id:
            self.update({
                         'product_id': self.room_id.product_id.id,
                         'room_number_id':False
                         })
            result = self.product_id_change()
        if self.checkin_date and self.checkout_date and self.room_id:
            self._cr.execute("""SELECT DISTINCT(room_number_id) FROM
                                hotel_room_move_line WHERE (%s,%s) OVERLAPS
                                (check_in, check_out) AND company_id=%s""",
                             (self.checkin_date, self.checkout_date,
                              self.env.user.company_id.id))
            datas = self._cr.fetchall()
            record_ids = [data[0] for data in datas]
            domain = {'room_number_id': [('room_id', '=', self.room_id.id),
                                         ('state', '!=', 'cancel'),
                                         ('id', 'not in', record_ids), ]}
            result['domain'].update(domain)
        return result

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :parem float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sale order"""
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(
                        uom=uom.id).get_product_price_rule(product, qty, self.folio_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or(
            product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(
                    product_currency, currency_id)

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0
        return product[field_name] * uom_factor * cur_factor, currency_id.id

    @api.multi
    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        if self.folio_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=self.folio_id.pricelist_id.id).price
        product_context = dict(self.env.context, partner_id=self.folio_id.partner_id.id,
                               date=self.folio_id.date_order, uom=self.product_uom.id)
        final_price, rule_id = self.folio_id.pricelist_id.with_context(product_context).get_product_price_rule(
            self.product_id, self.product_uom_qty or 1.0, self.folio_id.partner_id)
        base_price, currency_id = self.with_context(product_context)._get_real_price_currency(
            product, rule_id, self.product_uom_qty, self.product_uom, self.folio_id.pricelist_id.id)
        if currency_id != self.folio_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(
                product_context).compute(base_price, self.folio_id.pricelist_id.currency_id)
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.folio_id.fiscal_position_id or line.folio_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            taxes = line.product_id.taxes_id.filtered(
                lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(
                taxes, line.product_id, line.folio_id.partner_shipping_id) if fpos else taxes

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [
            ('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
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
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)
        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.folio_id.partner_id.lang,
                partner=self.folio_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.folio_id.date_order,
                pricelist=self.folio_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)

    @api.model
    def create(self, vals):
        if 'folio_id' in vals:
            folio = self.env["hotel.folio"].browse(vals['folio_id'])
            vals.update({'order_id': folio.order_id.id})
        return super(HotelFolioLine, self).create(vals)

    @api.multi
    def unlink(self):
        if self.order_line_id:
            self.order_line_id.unlink()
        return super(HotelFolioLine, self).unlink()

    @api.multi
    def copy(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        return super(HotelFolioLine, self).copy(default=default)

    @api.multi
    def button_confirm(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            line = folio.order_line_id
            line.button_confirm()
        return True

    @api.multi
    def button_done(self):
        '''
        @param self: object pointer
        '''
        lines = [folio_line.order_line_id for folio_line in self]
        lines.button_done()
        self.state = 'done'
        return True

    @api.multi
    def copy_data(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        line_id = self.order_line_id.id
        sale_line_obj = self.env['sale.order.line'].browse(line_id)
        return sale_line_obj.copy_data(default=default)


class HotelServiceLine(models.Model):
    _name = 'hotel.service.line'
    _description = 'hotel Service line'

    service_line_id = fields.Many2one('sale.order.line', 'Service Line',
                                      required=True, delegate=True,
                                      ondelete='cascade')
    folio_id = fields.Many2one('hotel.folio', 'Folio', ondelete='cascade')
    per_night_bool = fields.Boolean("Rate per Nights")
    checkin = fields.Date('Checkin')
    checkout = fields.Date('Checkout')
    extra_bed_service_line_bool = fields.Boolean('Extra Bed Service Bool')

    @api.constrains('checkin', 'checkout')
    def check_in_out_date(self):
        """
        Checkout date should be greater than the check-in date.
        """
        for rec in self:
            if rec.checkout and rec.checkin:
                current_date = datetime.today().strftime(DEFAULT_SERVER_DATE_FORMAT)
                if str(rec.checkin) < current_date:
                    raise ValidationError(_('Check-in date should be greater than \
                                             the current date.'))
                if rec.checkout < rec.checkin:
                    raise ValidationError(_('Check-out date should be greater \
                                             than Check-in date.'))

    @api.model
    def create(self, vals):
        """
        Overrides orm create method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        @return: new record set for hotel service line.
        """
        if 'folio_id' in vals:
            folio = self.env['hotel.folio'].browse(vals['folio_id'])
            vals.update({'order_id': folio.order_id.id})
        return super(HotelServiceLine, self).create(vals)

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.service_line_id:
            self.service_line_id.unlink()
        return super(HotelServiceLine, self).unlink()

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.folio_id.fiscal_position_id or line.folio_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            taxes = line.product_id.taxes_id.filtered(
                lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(
                taxes, line.product_id, line.folio_id.partner_shipping_id) if fpos else taxes

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :parem float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sale order"""
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(
                        uom=uom.id).get_product_price_rule(product, qty, self.folio_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or(
            product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(
                    product_currency, currency_id)

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0
        return product[field_name] * uom_factor * cur_factor, currency_id.id

    @api.multi
    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        if self.folio_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=self.folio_id.pricelist_id.id).price
        product_context = dict(self.env.context, partner_id=self.folio_id.partner_id.id,
                               date=self.folio_id.date_order, uom=self.product_uom.id)
        final_price, rule_id = self.folio_id.pricelist_id.with_context(product_context).get_product_price_rule(
            self.product_id, self.product_uom_qty or 1.0, self.folio_id.partner_id)
        base_price, currency_id = self.with_context(product_context)._get_real_price_currency(
            product, rule_id, self.product_uom_qty, self.product_uom, self.folio_id.pricelist_id.id)
        if currency_id != self.folio_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(
                product_context).compute(base_price, self.folio_id.pricelist_id.currency_id)
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [
            ('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
        if not self.product_id.per_night_bool:
            vals['product_uom_qty'] = 1.0

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
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)
        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        '''
        @param self: object pointer
        '''
        tax_obj = self.env['account.tax']
        if not self.product_uom:
            self.price_unit = 0.0
            return
        self.price_unit = self.product_id.list_price
        if self.folio_id.partner_id:
            prod = self.product_id.with_context(
                lang=self.folio_id.partner_id.lang,
                partner=self.folio_id.partner_id.id,
                quantity=self.product_uom_qty,
                date_order=self.folio_id.checkin_date,
                pricelist=self.folio_id.pricelist_id.id,
                uom=self.product_uom.id
            )
            prod_price = self._get_display_price(prod)
            self.price_unit = tax_obj._fix_tax_included_price(prod_price,
                                                              prod.taxes_id,
                                                              self.tax_id)

    @api.multi
    def button_confirm(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            service_line = folio.service_line_id
            line = service_line.button_confirm()
        return line

    @api.multi
    def button_done(self):
        '''
        @param self: object pointer
        '''
        for folio in self:
            service_line = folio.service_line_id
            line = service_line.button_done()
        return line

    @api.multi
    def copy_data(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        sale_line_obj = self.env['sale.order.line']. \
            browse(self.service_line_id.id)
        return sale_line_obj.copy_data(default=default)

    @api.onchange('checkin', 'checkout', 'product_id')
    def onchange_checkin_checkout_date(self):
        for rec in self:
            if rec.checkin and rec.checkout and\
                    rec.product_id and rec.product_id.per_night_bool:
                checkin_date = datetime.strptime(rec.checkin,
                                                 DEFAULT_SERVER_DATE_FORMAT)
                checkout_date = datetime.strptime(rec.checkout,
                                                  DEFAULT_SERVER_DATE_FORMAT)
                dur = checkout_date - checkin_date
                rec.update({'product_uom_qty': dur.days})


class HotelServiceType(models.Model):
    _name = "hotel.service.type"
    _description = "Service Type"

    product_category_id = fields.Many2one('product.category', 'Product Category',
                                 required=True, delegate=True,
                                 ondelete='cascade',
                                 domain=[('type', '=', 'service')])
    parent_id = fields.Many2one('hotel.service.type', 'Parent Category', index=True,
                                ondelete='cascade', oldname="service_id")
    child_id = fields.One2many('hotel.service.type', 'parent_id', 'Child Categories')


class HotelServices(models.Model):
    _name = 'hotel.services'
    _description = 'Hotel Services and its charges'

    product_id = fields.Many2one('product.product', 'Service_id',
                                 required=True, ondelete='cascade',
                                 delegate=True)
    categ_id = fields.Many2one('hotel.service.type', string='Service Category',
                               required=True)
    product_manager = fields.Many2one('res.users', string='Product Manager')

    @api.multi
    def unlink(self):
        for rec in self:
            rec.product_id.unlink()
        return super(HotelServices, self).unlink()


class CurrencyExchangeRate(models.Model):
    _name = "currency.exchange"
    _description = "currency"

    @api.depends('input_curr', 'out_curr', 'in_amount')
    def _compute_get_currency(self):
        '''
        When you change input_curr, out_curr or in_amount
        it will update the out_amount of the currency exchange
        ------------------------------------------------------
        @param self: object pointer
        '''
        for rec in self:
            rec.out_amount = 0.0
            if rec.input_curr:
                result = rec.get_rate(rec.input_curr.name,
                                      rec.out_curr.name)
                if rec.out_curr:
                    rec.rate = result
                    if rec.rate == Decimal('-1.00'):
                        raise ValidationError(_('Please Check Your Network \
                                                Connectivity.'))
                    rec.out_amount = (float(result) * float(rec.in_amount))

    @api.depends('out_amount', 'tax')
    def _compute_tax_change(self):
        '''
        When you change out_amount or tax
        it will update the total of the currency exchange
        -------------------------------------------------
        @param self: object pointer
        '''
        for rec in self:
            if rec.out_amount:
                ser_tax = ((rec.out_amount) * (float(rec.tax))) / 100
                rec.total = rec.out_amount + ser_tax

    @api.model
    def get_rate(self, source_cur, dest_cur):
        '''
        Calculate rate between two currency
        -----------------------------------
        @param self: object pointer
        '''
        curr_rate = CurrencyRates()
        try:
            rate = curr_rate.get_rate(source_cur, dest_cur)
            return Decimal(rate)
        except:
            return Decimal('-1.00')

    name = fields.Char('Reg Number', readonly=True, default='New')
    today_date = fields.Datetime('Date Ordered',
                                 required=True,
                                 default=(lambda *a:
                                          time.strftime
                                          (DEFAULT_SERVER_DATETIME_FORMAT)))
    input_curr = fields.Many2one('res.currency', string='Input Currency',
                                 track_visibility='always')
    in_amount = fields.Float('Amount Taken', size=64, default=1.0, index=True)
    out_curr = fields.Many2one('res.currency', string='Output Currency',
                               track_visibility='always')
    out_amount = fields.Float(compute="_compute_get_currency",
                              string='Subtotal', size=64)
    folio_no = fields.Many2one('hotel.folio', 'Folio Number')
    guest_name = fields.Many2one('res.partner', string='Guest Name')
    room_number = fields.Char(string='Room Number')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'),
                              ('cancel', 'Cancel')], 'State', default='draft')
    rate = fields.Float(compute="_compute_get_currency",
                        string='Rate (Per Unit)', size=64, readonly=True)
    hotel_id = fields.Many2one('stock.warehouse', 'Hotel Name')
    type = fields.Selection([('cash', 'Cash')], 'Type', default='cash')
    tax = fields.Float('Service Tax', default=2.0)
    total = fields.Float(compute="_compute_tax_change", string='Total Amount')

    @api.constrains('out_curr')
    def check_out_curr(self):
        for cur in self:
            if cur.out_curr == cur.input_curr:
                raise ValidationError(_('Input currency and output currency '
                                        'must not be same'))

    @api.model
    def create(self, vals):
        """
        Overrides orm create method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        """
        if not vals:
            vals = {}
        seq_obj = self.env['ir.sequence']
        vals['name'] = seq_obj.next_by_code('currency.exchange') or 'New'
        return super(CurrencyExchangeRate, self).create(vals)

    @api.onchange('folio_no')
    def get_folio_no(self):
        '''
        When you change folio_no, based on that it will update
        the guest_name,hotel_id and room_number as well
        ---------------------------------------------------------
        @param self: object pointer
        '''
        for rec in self:
            self.guest_name = False
            self.hotel_id = False
            self.room_number = False
            if rec.folio_no and len(rec.folio_no.folio_lines) != 0:
                self.guest_name = rec.folio_no.partner_id.id
                self.hotel_id = rec.folio_no.warehouse_id.id
                self.room_number = rec.folio_no.folio_lines[0].product_id.name

    @api.multi
    def act_cur_done(self):
        """
        This method is used to change the state
        to done of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.state = 'done'
        return True

    @api.multi
    def act_cur_cancel(self):
        """
        This method is used to change the state
        to cancel of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.state = 'cancel'
        return True

    @api.multi
    def act_cur_cancel_draft(self):
        """
        This method is used to change the state
        to draft of the currency exchange
        ---------------------------------------
        @param self: object pointer
        """
        self.state = 'draft'
        return True
