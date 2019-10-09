import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_compare, \
    DEFAULT_SERVER_DATETIME_FORMAT as dt, DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import ValidationError, UserError
import odoo.addons.decimal_precision as dp
from ast import literal_eval


class HotelFolio(models.Model):

    _inherit = 'hotel.folio'
    _order = 'reservation_id desc'

    reservation_id = fields.Many2one('hotel.reservation', 'Reservation',
                                     copy=False, ondelete="restrict")

    @api.multi
    def action_confirm(self):
        room_move_obj = self.env['hotel.room.move']
        room_move_line_obj = self.env['hotel.room.move.line']
        folio_line_obj = self.env['hotel.folio.line']
        for folio in self:
            for room in folio.folio_lines.mapped('room_id'):
                
                room_move = room_move_obj.search([('reservation_id', '=', folio.reservation_id.id),
                                                  ('room_id', '=', room.id)], limit=1)
                lines = folio_line_obj.search([('room_id', '=', room.id),
                                               ('folio_id', '=', folio.id)])
                if folio.reservation_id and room_move:
                    if not room_move and not lines:
                        return True
                    reserved_room_number_list = [
                        line.room_number_id.id for line in
                        room_move.room_move_line_ids]
                    new_room_list = []
                    move_lines = []
                    for line in lines:
                        folio._cr.execute(
                            """SELECT room_number_id FROM
                            hotel_room_move_line WHERE (%s,%s) OVERLAPS
                            (check_in, check_out) AND state != 'cancel' AND
                            (folio_line_id != %s OR folio_line_id is Null)
                            AND (room_move_id != %s OR  room_move_id is Null)
                            AND room_number_id = %s AND company_id=%s""",
                            (line.checkin_date, line.checkout_date, line.id,
                             room_move.id, line.room_number_id.id,
                             folio.company_id.id))
                        datas = folio._cr.fetchone()
                        if datas is not None:
                            raise ValidationError(_(
                                '''Room Reserved!,
                                %s room have already reserved for another customer,
                                Kindly select another room''') %
                                (line.room_id.name))
                        new_room_list.append(line.room_number_id.id)
                        if line.room_number_id.id not in \
                                reserved_room_number_list:
                            move_lines.append((0, 0, {
                                'room_number_id': line.room_number_id.id,
                                'folio_line_id': line.id}))
                        if line.order_line_id:
                            invoice_ids = [
                                res_line.invoice_lines_ids.id for res_line in
                                line.reservation_lines_ids]
                            invoice_ids = [
                                x for x in invoice_ids if x]
                            if invoice_ids:
                                line.order_line_id.write(
                                    {'invoice_lines': [(6, 0, invoice_ids)]})
                    room_move.write({
                        'state': 'assigned',
                        'room_move_line_ids': move_lines,
                        'folios_ids': [(4, folio.id)]
                    })
                    unused_list = list(set(reserved_room_number_list).difference(set(new_room_list)))
                    if unused_list:
                        room_move_line_obj.search([('room_number_id', 'in', unused_list),
                                                   ('room_move_id', '=', room_move.id)]).write({'state': 'cancel'})
                else:
                    vals = {}
                    move_lines = []
                    for line in lines:
                        folio._cr.execute("""SELECT room_number_id FROM
                                hotel_room_move_line WHERE (%s,%s) OVERLAPS
                                (check_in, check_out) AND state != 'cancel' AND
                                (folio_line_id != %s OR folio_line_id is Null)
                                AND room_number_id = %s AND company_id=%s
                                """, (line.checkin_date, line.checkout_date,
                                      line.id,
                                      line.room_number_id.id,
                                      line.company_id.id))
                        datas = folio._cr.fetchone()
                        if datas is not None:
                            raise ValidationError(_('''
                                Room Reserved!,
                                %s room have already reserved for another customer,
                                Kindly select another room''') %
                                                  (line.room_id.name))
                        move_lines.append((0, 0, {
                            'room_number_id': line.room_number_id.id,
                            'folio_line_id': line.id}))
                    vals.update({
                        'check_in': folio.checkin_date,
                        'check_out': folio.checkout_date,
                        'room_id': room.id,
                        'room_qty': len(lines),
                        'state': 'assigned',
                        'room_move_line_ids': move_lines,
                        'folios_ids': [(4, folio.id)]
                    })
                    room_move_obj.create(vals)
            folio.order_id.action_confirm()


class HotelFolioLine(models.Model):
    _inherit = 'hotel.folio.line'

    @api.depends('reservation_lines_ids')
    def _compute_reserved_line(self):
        for rec in self:
            rec.update({'is_reserved_line': len(rec.reservation_lines_ids)})

    reservation_lines_ids = fields.Many2many(
        'hotel_reservation.line',
        'hotel_folio_line_reservation_line_rel',
        'folio_line_id', 'reservation_line_id',
        string='Reservation Lines',
        readonly=True, copy=False)
    is_paid = fields.Boolean(
        related='order_line_id.is_paid', string="Payment Status")
    is_reserved_line = fields.Boolean(compute='_compute_reserved_line')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_paid = fields.Boolean('Payment Status')


class ResPartner(models.Model):
    _inherit = "res.partner"

    age = fields.Integer('Age')


class HotelReservation(models.Model):
    _name = "hotel.reservation"
    _rec_name = "reservation_no"
    _description = "Reservation"
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    @api.depends('state', 'reservation_line')
    def _get_folio(self):
        for rec in self:
            hotel_folios = rec.reservation_line.mapped(
                'folio_lines_ids').mapped('folio_id')
            rec.update({
                'folios_ids': hotel_folios.ids,
                'folio_count': len(hotel_folios.ids)
            })

    @api.depends('reservation_line.price_total', 'service_lines.price_total')
    def _amount_all(self):
        for rec in self:
            amount_untaxed = amount_tax = 0.0
            for line in rec.reservation_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            for line in rec.service_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            rec.update({
                'amount_untaxed':
                    rec.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': rec.pricelist_id.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.depends('checkin', 'checkout')
    def _compute_no_days(self):
        for rec in self:
            if rec.checkin and rec.checkout:
                dur = rec.checkout - rec.checkin
                rec.stay_days = dur.days

    @api.depends('state', 'reservation_line.invoice_lines_ids',
                 'reservation_line.invoice_status')
    def _compute_invoice(self):
        invoice_obj = self.env['account.invoice']
        for rec in self:
            invoice_ids = \
                rec.reservation_line.mapped('invoice_lines_ids').mapped(
                    'invoice_id').filtered(
                        lambda r: r.type in ['out_invoice', 'out_refund'])
            refunds = invoice_ids.search([
                ('origin', 'like', rec.name),
                ('company_id', '=', rec.company_id.id)]
            ).filtered(lambda r: r.type in ['out_invoice', 'out_refund'])
            invoice_ids |= refunds.filtered(
                lambda r: rec.name in [origin.strip()
                                       for origin in r.origin.split(',')])
            # Search for refunds as well
            refund_ids = invoice_obj.browse()
#            line_invoice_status = []
            if invoice_ids:
                for inv in invoice_ids:
                    refund_ids += invoice_obj.search([
                        ('type', '=', 'out_refund'),
                        ('origin', '=', inv.number),
                        ('origin', '!=', False),
                        ('journal_id', '=', inv.journal_id.id)])
            line_invoice_status = [
                line.invoice_status for line in rec.reservation_line]

            if not line_invoice_status:
                invoice_status = 'no'
            elif any(invoice_status == 'to_invoice' for
                     invoice_status in line_invoice_status):
                invoice_status = 'to_invoice'
            elif all(invoice_status == 'invoiced' for
                     invoice_status in line_invoice_status):
                invoice_status = 'invoiced'
            else:
                invoice_status = 'no'

            rec.update({
                'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
                'invoice_ids': invoice_ids.ids + refund_ids.ids,
                'invoice_status': invoice_status
            })

    @api.model
    def default_get(self, fields):
        res = super(HotelReservation, self).default_get(fields)
        if res.get('checkin') and res.get('checkout') and\
                res.get('checkin') == res.get('checkout'):
            checkin = res.get('checkin')
            checkout = checkin + timedelta(days=1)
            res['checkout'] = checkout.strftime(DEFAULT_SERVER_DATE_FORMAT)
        return res

    @api.depends('reservation_line.checkin', 'reservation_line.checkout')
    def _compute_check_in_out(self):
        for rec in self:
            checkin_list = []
            checkout_list = []
            for line in rec.reservation_line:
                if line.checkin:
                    checkin_list.append(line.checkin)
                if line.checkout:
                    checkout_list.append(line.checkout)

            rec.update({
                'checkin': checkin_list and min(checkin_list) or
                str(datetime.today()),
                'checkout': checkout_list and max(checkout_list) or
                str((datetime.today() + timedelta(days=1)))
            })

    name = fields.Char('Name')
    reservation_no = fields.Char(
        'Reservation No', size=64, readonly=True, default='New')
    date_order = fields.Datetime(
        'Date Ordered', readonly=True, required=True,
        index=True, default=(lambda *a: time.strftime(dt)))
    company_id = fields.Many2one(
        'res.company', 'Hotel',
        readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env['res.company']._company_default_get(
            'hotel.reservation'))
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Hotels', readonly=True,
        index=True,
        required=True, default=1,
        states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one(
        "res.currency", related='pricelist_id.currency_id',
        string="Currency", readonly=True, required=True)
    partner_id = fields.Many2one(
        'res.partner', 'Guest Name', readonly=True,
        index=True,
        states={'draft': [('readonly', False)]}, required=True)
    user_id = fields.Many2one(
        'res.users', string='Salesperson', index=True,
        track_visibility='onchange',
        default=lambda self: self.env.user)
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Scheme',
        required=True, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Pricelist for current reservation.")
    partner_invoice_id = fields.Many2one(
        'res.partner', 'Invoice Address',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Invoice address for current reservation.")
    partner_order_id = fields.Many2one(
        'res.partner', 'Ordering Contact',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="The name and address of the contact that requested \
            the order or quotation.")
    partner_shipping_id = fields.Many2one(
        'res.partner', 'Delivery Address',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Delivery address for current reservation. ")
    checkin = fields.Date(
        'Checkin-Date', readonly=True,
        compute="_compute_check_in_out",
        store=True, track_visibility='always')
    checkout = fields.Date(
        'Checkout-Date', readonly=True,
        compute="_compute_check_in_out",
        store=True, track_visibility='always')
    adults = fields.Integer(
        'Adults', size=64, readonly=True, default=1,
        states={'draft': [('readonly', False)]},
        help='List of adults there in guest list. ')
    children = fields.Integer(
        'Children', size=64, readonly=True,
        states={'draft': [('readonly', False)]},
        help='Number of children there in guest list.')
    reservation_line = fields.One2many(
        'hotel_reservation.line', 'reservation_id',
        'Reservation Line',
        help='Hotel room reservation details.',
        readonly=True,
        copy=False,
        states={'draft': [('readonly', False)]})
    state = fields.Selection(
        [('draft', 'Draft'), ('confirm', 'Confirm'),
         ('cancel', 'Cancel'), ('done', 'Done')],
        'State', readonly=True,
        default='draft')
    folios_ids = fields.Many2many(
        'hotel.folio', string='Folio', compute="_get_folio")
    folio_count = fields.Integer('Folio Count', compute="_get_folio")
    dummy = fields.Datetime('Dummy')
    service_lines = fields.One2many(
        'hotel.reservation.service.line',
        'reservation_id',
        readonly=True, copy=False,
        states={'draft': [('readonly', False)]},
        help="""Hotel services detail provide to
        customer and it will include in main
        Invoice.""")
    stay_days = fields.Integer(
        compute="_compute_no_days",
        string="Days", copy=False,
        readonly=True, store=True,
        track_visibility='always')
    amount_untaxed = fields.Monetary(
        'Untaxed Amount', store=True,
        readonly=True, compute='_amount_all',
        track_visibility='onchange')
    amount_tax = fields.Monetary(
        string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(
        string='Total', store=True,
        readonly=True, compute='_amount_all',
        track_visibility='always')
    room_move_ids = fields.One2many(
        'hotel.room.move', 'reservation_id',
        'Room Reservation Summary',
        help='Hotel room reservation details.',
        readonly=True, copy=False,
        states={'draft': [('readonly', False)]})
    hotel_policy = fields.Selection(
        [('prepaid', 'On Booking'),
         ('manual', 'On Check In'),
         ('picking', 'On Checkout')],
        'Payment Policy',
        default=lambda self: self.env.user.company_id.default_hotel_policy,
        help="Hotel policy for payment that "
        "either the guest has to payment at "
        "booking time or check-in "
        "check-out time.",
        readonly=True, states={'draft': [('readonly', False)]}, required=True)
    invoice_ids = fields.Many2many(
        'account.invoice', string='Invoices', copy=False)
    invoice_count = fields.Integer(compute="_compute_invoice",
                                   string="Invoice")
    invoice_status = fields.Selection([('no', 'Nothing to Invoice'),
                                       ('to_invoice', 'To Invoice'),
                                       ('invoiced', 'Invoiced')],
                                      string="Invoice Status",
                                      compute='_compute_invoice',
                                      readonly=True)
    reservation_adults_ids = fields.One2many('hotel.reservation.adults',
                                             'reservation_id',
                                             string="Adults", copy=False,
                                             states={
                                                 'draft': [('readonly', False)]},
                                             required=True)
    remarks = fields.Text('Remarks', copy=False)
    cancel_reason_id = fields.Many2one('reservation.cancel.reason',
                                       string="Reason for cancellation",
                                       readonly=True,
                                       copy=False,
                                       ondelete="restrict")
    

    @api.model
    def _send_reminder(self):
        """Scheduler method to send reminder before 2 days of checkin."""
        curr_date = datetime.now()
        new_check_in_date = curr_date + relativedelta(days=2)
        reservations = self.search(
            [('checkin', '=', new_check_in_date.date())])
        for reservation in reservations:
            template = self.env.ref(
                "hotel_reservation.mail_template_reservation_reminder")
            template.send_mail(reservation.id, force_send=True)

    @api.multi
    def action_view_invoice(self):
        """Method of the smart button for invoice."""
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('reservation_id', '=', self.id))
        return action

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        for reserv_rec in self:
            if reserv_rec.state != 'draft':
                raise ValidationError(_('You cannot delete Reservation in %s\
                                         state.') % (reserv_rec.state))
        return super(HotelReservation, self).unlink()

    @api.multi
    def copy(self):
        ctx = dict(self._context) or {}
        ctx.update({'duplicate': True})
        return super(HotelReservation, self.with_context(ctx)).copy()

    @api.constrains('reservation_line', 'adults', 'children')
    def check_reservation_rooms(self):
        '''
        This method is used to validate the reservation_line.
        -----------------------------------------------------
        @param self: object pointer
        @return: raise a warning depending on the validation
        '''
        reservation_line_obj = self.env['hotel_reservation.line']
        for reservation in self:
            if self._context.get('install_mode'):
                return True
            capacity = 0
            if reservation.adults <= 0:
                raise ValidationError(_('Adults must be more than 0'))
            if reservation.children < 0:
                raise ValidationError(_('Children must be 0 or more than 0'))
            for room_no in reservation.reservation_line.mapped(
                    'room_number_id'):
                # get the same room number lines
                lines = reservation_line_obj.search([
                    ('room_number_id', '=', room_no.id),
                    ('reservation_id', '=', reservation.id)])
                for line in lines:
                    record = lines.search([
                        ('id', 'in', lines.ids),
                        ('id', '!=', line.id),
                        ('checkin', '>=', line.checkin),
                        ('checkout', '<=', line.checkout),
                        ('room_number_id', '=', room_no.id)])
                    if record:
                        raise ValidationError(_(
                            '''Room Duplicate Exceeded!,
                            %s Rooms Already Have Selected
                            in Reservation!''') %
                            (room_no.name))

            for room in reservation.reservation_line.mapped('room_id'):
                lines = reservation_line_obj.search([
                    ('room_id', '=', room.id),
                    ('reservation_id', '=', reservation.id)])
                capacity += sum(line.qty * line.room_id.capacity
                                for line in lines)
            if reservation.reservation_line and (reservation.adults + reservation.children) > capacity:
                raise ValidationError(_('''Room Capacity Exceeded!,
                    Please Select Rooms According to Members Accomodation!'''))

    @api.constrains('reservation_line', 'service_lines')
    def check_duration_range(self):
        """
        When checkin date is greater than or
        equal to checkout date in reservation_line.
        """
        for reservation_line in self.reservation_line:
            if reservation_line.checkin >= reservation_line.checkout:
                raise ValidationError(_('Reservation line checkout date should be greater \
                                        than checkin date.'))
            if reservation_line.checkin < self.checkin:
                raise ValidationError(_('Enter valid reservation line checkin date.'))

            if reservation_line.checkout > self.checkout:
                raise ValidationError(_('Enter valid reservation line checkout date.'))

        for service_line in self.service_lines:
            if service_line.checkin >= service_line.checkout:
                raise ValidationError(_('Service line checkout date should be greater \
                                        than checkin date.'))
            if service_line.checkin < self.checkin:
                raise ValidationError(_('Enter valid service line checkin date.'))

            if service_line.checkout > self.checkout:
                raise ValidationError(_('Enter valid service line checkout date.'))

    @api.constrains('adults', 'reservation_adults_ids')
    def check_adults_details(self):
        for rec in self:
            if rec.company_id.adults_details_validation and \
                    rec.adults != len(rec.reservation_adults_ids):
                raise ValidationError(
                    _('Kindly add adutls details as per no of adutls!'))

    @api.model
    def _needaction_count(self, domain=None):
        """
         Show a count of draft state reservations on the menu badge.
         """
        return self.search_count([('state', '=', 'draft')])

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
            })
            return

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'pricelist_id': self.partner_id.property_product_pricelist
            and self.partner_id.property_product_pricelist.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }

        if self.partner_id.user_id:
            values['user_id'] = self.partner_id.user_id.id
        self.update(values)

    @api.multi
    def confirmed_reservation(self):
        """
        This method create a new record set for hotel room reservation line
        -------------------------------------------------------------------
        @param self: The object pointer
        @return: new record set for hotel room reservation line.
        """
        room_move_obj = self.env['hotel.room.move']
        reservation_line_obj = self.env['hotel_reservation.line']
        ir_sequence_obj = self.env['ir.sequence']
        vals = {}
        for rec in self:
            if not rec.reservation_line:
                raise ValidationError(
                    _('Please create some reservation lines!'))
            if self.company_id:
                resevation_seq = ir_sequence_obj.with_context(force_company=self.company_id.id).next_by_code('hotel.reservation') or _('New')
            else:
                resevation_seq = ir_sequence_obj.next_by_code('hotel.reservation') or _('New')
            for room in rec.reservation_line.mapped('room_id'):
                lines = reservation_line_obj.search([('room_id', '=', room.id),
                                                     ('reservation_id', '=', rec.id)])
                dates_list = []
                move_lines = []
                room_qty = 0.0
                for line in lines:
                    if line.room_number_id:
                        rec._cr.execute("""
                            SELECT room_number_id FROM
                            hotel_room_move_line WHERE (%s,%s) OVERLAPS
                            (check_in, check_out) AND state != 'cancel' AND
                            (reservation_line_id != %s OR
                            reservation_line_id is Null)
                            AND room_number_id = %s
                            AND company_id = %s
                        """, (line.checkin, line.checkout, line.id,
                              line.room_number_id.id,
                              rec.company_id.id))
                        datas = rec._cr.fetchone()
                        if datas is not None:
                            raise ValidationError(_(
                                '''Room Reserved!,
                                %s room have already reserved for another customer,
                                Kindly select another room''') %
                                (line.room_id.name))
                        move_lines.append((0, 0,{'room_number_id': line.room_number_id.id,
                                             'reservation_line_id': line.id
                                             }))
                    dates_list.append(rec.checkin)
                    dates_list.append(rec.checkout)
                    room_qty += line.qty or 0.0
                    available_room_qty = line.get_available_room_qty(
                        line.room_id, line.checkin, line.checkout)
                    if line.qty > available_room_qty:
                        raise ValidationError(_(
                            'You tried to Confirm '
                            'Reservation with "%s" room'
                            ' but this type room only %s left.'
                        ) % (line.room_id.name, available_room_qty))
                vals = {
                    'room_id': room.id,
                    'check_in': min(dates_list),
                    'check_out': max(dates_list),
                    'state': 'reserved',
                    'room_qty': room_qty,
                    'reservation_id': rec.id,
                    'room_move_line_ids': move_lines
                }
                room_move_obj.create(vals)
            rec.sudo().write({'reservation_no': resevation_seq,
                              'state': 'confirm'})
            # send email of reservation confirmation with attachment of
            # reservation receipts
            if rec.company_id.send_confirmation_email:
                template = self.env.ref(
                    'hotel_reservation.mail_template_hotel_reservation')
                template.send_mail(rec.id, force_send=True)


    @api.multi
    def cancel_reservation(self):
        """
        This method cancel record set for hotel room reservation line
        ------------------------------------------------------------------
        @param self: The object pointer
        @return: cancel record set for hotel room reservation line.
        """
        for rec in self:
            rec.mapped('room_move_ids').write({'state': 'cancel'})
        self.write({'state': 'cancel'})
        return True

    @api.multi
    def set_to_draft_reservation(self):
        self.write({
            'state': 'draft',
            'reservation_no': 'New'
        })

    @api.multi
    def set_done(self):
        self.write({'state': 'done'})

    @api.multi
    def send_reservation_maill(self):
        '''
        This function opens a window to compose an email,
        template message loaded by default.
        @param self: object pointer
        '''
        assert len(self._ids) == 1, 'This is for a single id at a time.'
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = (ir_model_data.get_object_reference
                           ('hotel_reservation',
                            'mail_template_hotel_reservation')[1])
        except ValueError:
            template_id = False
        try:
            compose_form_id = (ir_model_data.get_object_reference
                               ('mail',
                                'email_compose_message_wizard_form')[1])
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'hotel.reservation',
            'default_res_id': self._ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_send': True,
            'mark_so_as_sent': True
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
            'force_send': True
        }

    @api.multi
    def create_folio(self):
        """
        This method is for create new hotel folio.
        -----------------------------------------
        @param self: The object pointer
        @return: new record set for hotel folio.
        """
        reservation_line_obj = self.env['hotel_reservation.line']
        view = self.env.ref(
            'hotel_reservation.hotel_folio_room_allocation_form_view')
        for reservation in self:
            allocation_list = []
            for room in reservation.reservation_line.mapped('room_id'):
                lines = reservation_line_obj.search([
                    ('room_id', '=', room.id),
                    ('reservation_id', '=', reservation.id)])
                room_no_ids = [
                    line.room_number_id.id for line in lines if
                    line.room_number_id]
                vals = {'room_id': room.id,
                        'room_qty': len(lines.ids),
                        'reservation_lines_ids': [(6, 0, lines.ids)],
                        'room_numbers_ids': [(6, 0, room_no_ids)]}
                allocation_list.append((0, 0, vals))
            wiz = self.env['hotel.folio.room.allocation'].create(
                {'reservation_id': reservation.id,
                 'folio_allocation_ids': allocation_list})
            return {
                'name': _('Rooms Allocation'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hotel.folio.room.allocation',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }

    def open_folio_view(self):
        folios = self.mapped('folios_ids')
        action = self.env.ref(
            'hotel.open_hotel_folio1_form_tree_all').read()[0]
        if len(folios) > 1:
            action['domain'] = [('id', 'in', folios.ids)]
        elif len(folios) == 1:
            action['views'] = \
                [(self.env.ref('hotel.view_hotel_folio1_form').id, 'form')]
            action['res_id'] = folios.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def _prepare_invoice(self):
        self.ensure_one()
        journal_id = self.env['account.invoice'].default_get(['journal_id'])[
            'journal_id']
        if not journal_id:
            raise UserError(
                _('Please define an accounting \
                sale journal for this company.'))
        invoice_vals = {
            'origin': self.reservation_no,
            'type': 'out_invoice',
            'account_id':
            self.partner_invoice_id.property_account_receivable_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'fiscal_position_id':
                self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'reservation_id': self.id
        }
        return invoice_vals

    @api.multi
    def action_invoice_create(self):
        inv_obj = self.env['account.invoice']
        for rec in self:
            inv_data = rec._prepare_invoice()
            invoices = inv_obj.create(inv_data)
            for line in rec.reservation_line.sorted(
                    key=lambda l: l.qty_to_invoice < 0):
                i = 1
                while i <= line.qty:
                    line.invoice_line_create(invoices, line.stay_days)
                    i += 1
        if not invoices:
            raise UserError(_('There is no invoicable line.'))

        for invoice in invoices:
            if not invoice.invoice_line_ids:
                raise UserError(_('There is no invoicable line.'))
            # If invoice is negative, do a refund invoice instead
            if invoice.amount_untaxed < 0:
                invoice.type = 'out_refund'
                for line in invoice.invoice_line_ids:
                    line.quantity = -line.quantity
            # Use additional field helper function (for account extensions)
            for line in invoice.invoice_line_ids:
                line._set_additional_fields(invoice)
            # Necessary to force computation of taxes.
            # In account_invoice, they are triggered
            # by onchanges, which are not triggered when doing a create.
            invoice.compute_taxes()
            invoice.message_post_with_view(
                'mail.message_origin_link',
                values={'self': invoice,
                        'origin': invoice.name},
                subtype_id=self.env.ref('mail.mt_note').id)
        return [invoice.id]

    def _set_room_amenities(self, res):
        extra_room_qty = 0
        extra_room_price = 0.0
        amenitiy_list = []
        for line in res.reservation_line:
            if not line.service_line_bool and line.room_id:
                for amenity in line.room_id.room_amenities:
                    qty = 1.0
                    per_night_bool = False
                    if amenity.product_id and amenity.product_id.per_night_bool and\
                            line.checkin and line.checkout:
                        checkin_date = datetime.strptime(line.checkin,
                                                         DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(line.checkout,
                                                          DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        qty = dur.days
                        per_night_bool = True
                    val = {
                        'checkin': line.checkin,
                        'checkout': line.checkout,
                        'product_id': amenity.product_id.id,
                        'name': amenity.product_id.name,
                        'reservation_id': res.id,
                        'qty': qty,
                        'price_unit': amenity.lst_price,
                        'per_night_bool': per_night_bool,
                        'product_uom': amenity.product_id.uom_id.id,
                        'extra_bed_service_line_bool': True,
                        'reservation_lines_ids': [(6, 0, line.ids)],
                        'tax_id': [(6, 0, amenity.product_id.taxes_id.ids)]
                    }
                    self.env['hotel.reservation.service.line'].create(val)
                    line.service_line_bool = True
                # it's for extra room service added
                if line.room_number_id and line.room_number_id.extra_charge > 0:
                    extra_room_qty += 1
                extra_room_price += line.room_number_id.extra_charge
#        rec.update({'service_lines': [(6, 0, amenitiy_list)]})
            extra_room_product = res.company_id.extra_room_charge_id
            if extra_room_qty > 0 and extra_room_product and res.reservation_line and not line.service_line_bool:
                extra_room_line = res.service_lines.search([('product_id', '=', extra_room_product.id or False),
                                                        ('reservation_id', '=', res.id),
                                                        ('extra_bed_service_line_bool', '=', False)],
                                                       limit=1)
                if extra_room_line:
                    room_qty = extra_room_line.qty + extra_room_qty
                    price_unit = 0.0
                    if room_qty > 0:
                        price_unit = (extra_room_line.price_unit +
                                      extra_room_price) / room_qty
                    if extra_room_product and \
                            extra_room_product.per_night_bool and\
                            line.checkin and line.checkout:
                        checkin_date = datetime.strptime(
                            rec.checkin,
                            DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(
                            rec.checkout,
                            DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        room_qty = room_qty * dur.days
                    extra_room_line.update({
                        'qty': room_qty,
                        'price_unit': price_unit or 0.0,
                        'extra_bed_service_line_bool':True
                    })
                else:
                    if extra_room_product and \
                            extra_room_product.per_night_bool and\
                            line.checkin and line.checkout:
                        checkin_date = datetime.strptime(
                            rec.checkin,
                            DEFAULT_SERVER_DATE_FORMAT)
                        checkout_date = datetime.strptime(
                            rec.checkout,
                            DEFAULT_SERVER_DATE_FORMAT)
                        dur = checkout_date - checkin_date
                        extra_room_qty = extra_room_qty * dur.days
                    price_unit = 0.0
                    if extra_room_qty > 0:
                        price_unit = extra_room_price / extra_room_qty
                    
                    service_vals = {
                            'checkin': line.checkin,
                            'checkout': line.checkout,
                            'product_id': extra_room_product.id,
                            'name': extra_room_product.name,
                            'qty': extra_room_qty,
                            'reservation_id': res.id,
                            'per_night_bool': per_night_bool,
                            'extra_bed_service_line_bool':True,
                            'price_unit': price_unit,
                            'product_uom': extra_room_product.uom_id.id,
                            'tax_id': [(6, 0, extra_room_product.taxes_id.ids)]
                        }
                    line.service_line_bool = True
                    self.env['hotel.reservation.service.line'].create(service_vals)
        
    @api.model
    def create(self, vals):
        res = super(HotelReservation, self).create(vals)
        if res:
            self._set_room_amenities(res)
        return res
    
    @api.multi
    def write(self, vals):
        res = super(HotelReservation, self).write(vals)
        if res and vals.get('reservation_line'):
            for rec in self:
                self._set_room_amenities(rec)
        return res


class HotelReservationLine(models.Model):
    _name = "hotel_reservation.line"
    _description = "Reservation Line"

    @api.depends('qty', 'discount', 'price_unit', 'tax_id', 'stay_days')
    def _compute_amount(self):
        """
        Compute the amounts of the Reservation line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line_qty = line.qty * line.stay_days
            taxes = line.tax_id.compute_all(
                price, line.reservation_id.currency_id, line_qty,
                product=line.room_id.product_id,
                partner=line.reservation_id.partner_shipping_id)
            line.update({
                'price_tax':
                    sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('checkin', 'checkout')
    def _compute_stays_duration(self):
        for rec in self:
            if rec.checkin and rec.checkout:
                checkin_date = datetime.strptime(
                    str(rec.checkin),
                    DEFAULT_SERVER_DATE_FORMAT)
                checkout_date = datetime.strptime(
                    str(rec.checkout),
                    DEFAULT_SERVER_DATE_FORMAT)
                dur = checkout_date - checkin_date
                rec.stay_days = dur.days

    @api.depends('invoice_lines_ids.invoice_id.state',
                 'invoice_lines_ids.quantity')
    def _get_invoice_qty(self):
        for line in self:
            qty_invoiced = 0.0
            for invoice_line in line.invoice_lines_ids:
                if invoice_line.invoice_id.state != 'cancel':
                    if invoice_line.invoice_id.type == 'out_invoice':
                        qty_invoiced += \
                            invoice_line.uom_id._compute_quantity(
                                invoice_line.quantity,
                                line.room_id.product_id.uom_id)
                    elif invoice_line.invoice_id.type == 'out_refund':
                        qty_invoiced -= \
                            invoice_line.uom_id._compute_quantity(
                                invoice_line.quantity,
                                line.room_id.product_id.uom_id)
            line.qty_invoiced = qty_invoiced

    @api.depends('qty_invoiced', 'qty', 'reservation_id.state')
    def _get_to_invoice_qty(self):
        for line in self:
            if line.reservation_id.state in ['confirm', 'done']:
                line.qty_to_invoice = (
                    line.qty * line.stay_days) - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    @api.depends('qty', 'qty_to_invoice', 'qty_invoiced')
    def _compute_invoice_status(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for line in self:
            if not line.invoice_lines_ids:
                line.invoice_status = 'no'
            elif not float_is_zero(
                    line.qty_to_invoice, precision_digits=precision):
                line.invoice_status = 'to_invoice'
            elif float_compare(line.qty_invoiced, (line.qty * line.stay_days),
                               precision_digits=precision) == 0:
                line.invoice_status = 'invoiced'
            else:
                line.invoice_status = 'no'

    name = fields.Char('Name', size=64, required=True)
    reservation_id = fields.Many2one(
        'hotel.reservation', 'Reservation',
        copy=False, ondelete="cascade")
    room_id = fields.Many2one(
        'hotel.room', 'Room', copy=False,
        ondelete="restrict", required=True)
    room_number_id = fields.Many2one(
        'hotel.room.number', 'Room Numbers', copy=False,
        domain="[('room_id', '=', room_id), ('state', '=', 'available')]")
    price_unit = fields.Float(
        'Room Rate', required=True,
        digits=dp.get_precision('Product Price'),
        default=0.0)
    discount = fields.Float(
        'Discount (%)', digits=dp.get_precision('Discount'), default=0.0)
    room_status = fields.Selection(
        related='room_id.status', string='Status', readonly=True)
    qty = fields.Float(
        string='Quantity',
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=False, required=True, default=1.0)
    stay_days = fields.Integer(
        "Nights", copy=False, readonly=True,
        compute="_compute_stays_duration")
    tax_id = fields.Many2many(
        'account.tax', string='Tax',
        domain=['|', ('active', '=', False), ('active', '=', True)])
    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(
        compute='_compute_amount', string='Taxes',
        readonly=True, store=True)
    price_total = fields.Monetary(
        compute='_compute_amount', string='Total',
        readonly=True, store=True)
    currency_id = fields.Many2one(
        related='reservation_id.currency_id',
        store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(
        related='reservation_id.company_id',
        string='Company', store=True, readonly=True)
    checkin = fields.Date("Checkin")
    checkout = fields.Date("Checkout")
    folio_lines_ids = fields.Many2many(
        'hotel.folio.line',
        'hotel_folio_line_reservation_line_rel',
        'reservation_line_id', 'folio_line_id',
        string='Reservation Lines',
        readonly=True, copy=False)
    invoice_lines_ids = fields.Many2many(
        'account.invoice.line',
        string='Invoice Lines', readonly=True, copy=False)
    invoice_status = fields.Selection(
        [('no', 'Nothing to Invoice'),
         ('to_invoice', 'To Invoice'),
         ('invoiced', 'Invoiced')],
        string="Invoice Status",
        compute='_compute_invoice_status',
        store=True, readonly=True, default='no')
    price_unit = fields.Float(
        'Unit Price', required=True, digits=dp.get_precision('Product Price'),
        default=0.0)
    state = fields.Selection([('draft', 'Draft'),
                              ('confirm', 'Confirm'),
                              ('cancel', 'Cancel'),
                              ('done', 'Done')],
                             related='reservation_id.state',
                             string='Reservation Status', readonly=True,
                             copy=False, store=True, default='draft')
    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice',
        store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    qty_invoiced = fields.Float(
        compute='_get_invoice_qty', string='Invoiced',
        store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    service_line_bool = fields.Boolean('Service Bool')

    @api.onchange('checkin', 'checkout')
    def onchange_reservation_date(self):
        if not (self.reservation_id.checkin and self.reservation_id.checkout):
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select checkin checkout date!'),
            }
            return {'warning': warning}
        room_obj = self.env['hotel.room']
        if self.checkin and self.checkout:
            self.room_id = False
            room_list = room_obj.search([('status', '=', 'available')]).ids
            for room_id in room_list:
                room = room_obj.browse(room_id)
                self._cr.execute("""SELECT room_id, sum(room_qty) as qty FROM
                                hotel_room_move WHERE state != 'cancel'
                                AND room_id=%s
                                AND (%s,%s) OVERLAPS (check_in, check_out)
                                AND company_id=%s
                                GROUP BY room_id""",
                                 (room_id, self.checkin, self.checkout,
                                  self.company_id.id))
                data = self._cr.dictfetchone()
                room_qty = room.rooms_qty
                if data is not None and room_qty <= data.get('qty'):
                    room_list.remove(data.get('room_id'))
            domain = {'room_id': [('id', 'in', room_list)]}
            return {'domain': domain}

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.reservation_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            taxes = line.room_id.taxes_id.filtered(
                lambda r: not line.company_id or
                r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(
                taxes, line.room_id,
                line.reservation_id.partner_shipping_id) if fpos else taxes

    def _get_real_price_currency(self, room, rule_id, qty, uom, pricelist_id):
        product = room.product_id
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy ==\
                    'without_discount':
                while pricelist_item.base == 'pricelist' and\
                    pricelist_item.base_pricelist_id and\
                    pricelist_item.base_pricelist_id.discount_policy ==\
                        'without_discount':
                    price, rule_id = \
                        pricelist_item.base_pricelist_id.with_context(
                            uom=uom.id).get_product_price_rule(
                                product, qty,
                                self.reservation_id_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and\
                    pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or(
            product.company_id and product.company_id.currency_id) or\
            self.env.user.company_id.currency_id
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
    def _get_display_price(self, room):
        if self.reservation_id.pricelist_id.discount_policy == 'with_discount':
            return room.with_context(
                pricelist=self.reservation_id.pricelist_id.id).price
        room_context = dict(
            self.env.context, partner_id=self.reservation_id.partner_id.id,
            date=self.reservation_id.date_order,
            uom=self.room_id.product_id.uom_id.id)
        final_price, rule_id = self.reservation_id.pricelist_id.with_context(
            room_context).get_product_price_rule(
            self.room_id.product_id, self.qty or 1.0,
            self.reservation_id.partner_id)
        base_price, currency_id = self.with_context(
            room_context)._get_real_price_currency(
            room, rule_id, self.qty, self.room_id.product_id.uom_id,
            self.reservation_id.pricelist_id.id)
        if currency_id != self.reservation_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(
                currency_id).with_context(
                room_context).compute(
                base_price, self.reservation_id.pricelist_id.currency_id)
        return max(base_price, final_price)

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
        vals['room_number_id'] = False
        self._compute_tax_id()

        if self.reservation_id.pricelist_id and self.reservation_id.partner_id:
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
            domain = {'room_number_id': [('room_id', '=', self.room_id.id),
                                         ('state', '=', 'available'),
                                         ('id', 'not in', record_ids)]}
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
            self.price_unit = self.env[
                'account.tax']._fix_tax_included_price_company(
                    self._get_display_price(room),
                    room.taxes_id, self.tax_id,
                    self.company_id)

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        hotel_room_reserv_line_obj = self.env['hotel.room.move']
        for rec in self:
            hres_arg = [('room_id', '=', rec.id),
                        ('reservation_id', '=', rec.reservation_id.id)]
            line_ids = hotel_room_reserv_line_obj.search(hres_arg)
            if line_ids:
                line_ids.unlink()
        return super(HotelReservationLine, self).unlink()

    def _prepare_invoice_line(self, qty):
        self.ensure_one()
        res = {}
        account = self.room_id.product_id.property_account_income_id or\
            self.room_id.product_id.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_(
                'Please define income account \
                for this product: "%s" (id:%d) - or for its category: "%s".') %
                (self.product_id.name, self.product_id.id,
                 self.product_id.categ_id.name))

        fpos = self.reservation_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)

        res = {
            'name': self.name,
            'origin': self.reservation_id.reservation_no,
            'account_id': account.id,
            'price_unit': self.price_unit,
            'quantity': qty,
            'discount': self.discount,
            'uom_id': self.room_id.product_id.uom_id.id,
            'product_id': self.room_id.product_id.id or False,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)]
        }
        return res

    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty)
                vals.update({'invoice_id': invoice_id.id})
                inv_line_id = self.env['account.invoice.line'].create(vals)
                line.write({'invoice_lines_ids': [(4, inv_line_id.id)]})

    @api.multi
    def get_available_room_qty(self, room, checkin, checkout):
        self._cr.execute("""SELECT sum(room_qty) as qty FROM
                            hotel_room_move WHERE state != 'cancel'
                            AND room_id=%s AND
                            (%s,%s) OVERLAPS (check_in, check_out)
                            AND company_id=%s""",
                         (room.id, checkin, checkout, self.company_id.id))
        room_qty = self._cr.fetchone()[0]
        available_room_qty = room and room.rooms_qty
        if room_qty:
            available_room_qty -= room_qty
        return available_room_qty

    @api.multi
    def get_booked_room_qty(self, room_id, checkin, checkout):
        self._cr.execute("""SELECT sum(room_qty) as qty FROM
                            hotel_room_move WHERE state != 'cancel'
                            AND room_id=%s AND
                            (%s,%s) OVERLAPS (check_in, check_out)
                            AND company_id=%s """,
                         (room_id, checkin, checkout, self.env.user.company_id.id))
        room_qty = self._cr.fetchone()[0]
        if room_qty is None:
            room_qty = 0
        return room_qty

    @api.constrains('qty', 'checkin', 'checkout')
    def check_reservation_rooms(self):
        '''
        This method is used to validate the reservation_line.
        -----------------------------------------------------
        @param self: object pointer
        @return: raise a warning depending on the validation
        '''
        for line in self:
            available_room_qty = line.get_available_room_qty(
                line.room_id, line.checkin, line.checkout)
            if line.qty > available_room_qty:
                raise ValidationError(_(
                    'You tried to Reservation with "%s" room'
                    ' but this type room only %s left.'
                ) % (line.room_id.name, available_room_qty))


class HotelServiceLine(models.Model):
    _name = 'hotel.reservation.service.line'
    _description = 'hotel Service line'

    @api.depends('qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price, line.reservation_id.currency_id,
                line.qty, product=line.product_id,
                partner=line.reservation_id.partner_shipping_id)
            line.update({
                'price_tax':
                sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    checkin = fields.Date("Checkin")
    checkout = fields.Date("Checkout")
    reservation_id = fields.Many2one(
        'hotel.reservation', 'Reservation',
        ondelete="cascade", copy=False)
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', '!=', 'product'), ('service_ok', '=', True)],
        change_default=True, ondelete='restrict',
        required=True)

    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    per_night_bool =  fields.Boolean("Rate per Nights")
    price_unit = fields.Float('Unit Price', required=True,
                              digits=dp.get_precision('Product Price'),
                              default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal',
                                     readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Taxes',
                             readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total',
                                  readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes',
                              domain=['|', ('active', '=', False), ('active', '=', True)])
    discount = fields.Float(string='Discount (%)',
                            digits=dp.get_precision('Discount'), default=0.0)
    qty = fields.Float(string='Quantity',
                       digits=dp.get_precision('Product Unit of Measure'),
                       required=True, default=1.0)
    product_uom = fields.Many2one('uom.uom', 'Unit of Measure',
                                  required=True)
    currency_id = fields.Many2one(related='reservation_id.currency_id', store=True,
                                  string='Currency', readonly=True)
    company_id = fields.Many2one(related='reservation_id.company_id', string='Company',
                                 store=True, readonly=True)
    order_partner_id = fields.Many2one(related='reservation_id.partner_id',
                                       store=True, string='Customer')
    extra_bed_service_line_bool = fields.Boolean('Extra Bed Service Bool')

    @api.constrains('checkin', 'checkout')
    def check_in_out_date(self):
        """
        Checkout date should be greater than the check-in date.
        """
        for rec in self:
            if rec.checkout and rec.checkin:
                current_date = datetime.today().strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
                if str(rec.checkin) < current_date:
                    raise ValidationError(_('Check-in date should be greater than \
                                             the current date.'))
                if rec.checkout < rec.checkin:
                    raise ValidationError(_('Check-out date should be greater \
                                             than Check-in date.'))

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.reservation_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            taxes = line.product_id.taxes_id.filtered(
                lambda r: not line.company_id
                or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(
                taxes, line.product_id,
                line.reservation_id.partner_shipping_id) if fpos else taxes

    def _get_real_price_currency(
            self, product, rule_id, qty, uom, pricelist_id):
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy ==\
                    'without_discount':
                while pricelist_item.base == 'pricelist' and \
                    pricelist_item.base_pricelist_id and\
                    pricelist_item.base_pricelist_id.discount_policy ==\
                        'without_discount':
                    price, rule_id = \
                        pricelist_item.base_pricelist_id.with_context(
                            uom=uom.id).get_product_price_rule(
                            product, qty, self.reservation_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and \
                    pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or(
            product.company_id and product.company_id.currency_id)\
            or self.env.user.company_id.currency_id
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
        if self.reservation_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(
                pricelist=self.reservation_id.pricelist_id.id).price
        product_context = dict(
            self.env.context, partner_id=self.order_id.partner_id.id,
            date=self.reservation_id.date_order, uom=self.product_uom.id)
        final_price, rule_id = self.reservation_id.pricelist_id.with_context(
            product_context).get_product_price_rule(
                self.product_id, self.qty or 1.0,
                self.reservation_id.partner_id)
        base_price, currency_id = self.with_context(
            product_context)._get_real_price_currency(
            product, rule_id, self.qty, self.product_uom,
            self.reservation_id.pricelist_id.id)
        if currency_id != self.reservation_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(
                currency_id).with_context(
                product_context).compute(
                base_price, self.reservation_id.pricelist_id.currency_id)
        return max(base_price, final_price)

    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [
            ('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (
                self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id.id
        if not self.product_id.per_night_bool:
            vals['qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.reservation_id.partner_id.lang,
            partner=self.reservation_id.partner_id.id,
            quantity=vals.get('qty') or self.qty,
            date=self.reservation_id.date_order,
            pricelist=self.reservation_id.pricelist_id.id,
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
        vals['per_night_bool'] = product.per_night_bool

        if self.reservation_id.pricelist_id and self.reservation_id.partner_id:
            vals['price_unit'] = self.env[
                'account.tax']._fix_tax_included_price_company(
                self._get_display_price(product),
                product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)
        return result

    @api.onchange('product_uom', 'qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.reservation_id.pricelist_id and self.reservation_id.partner_id:
            product = self.product_id.with_context(
                lang=self.reservation_id.partner_id.lang,
                partner=self.reservation_id.partner_id.id,
                quantity=self.qty,
                date=self.reservation_id.date_order,
                pricelist=self.reservation_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.env[
                'account.tax']._fix_tax_included_price_company(
                self._get_display_price(product),
                product.taxes_id, self.tax_id, self.company_id)

    @api.onchange('checkin', 'checkout', 'product_id')
    def onchange_checkin_checkout_date(self):
        for rec in self:
            if rec.checkin and rec.checkout and\
                    rec.product_id and rec.product_id.per_night_bool:
                dur = rec.checkout - rec.checkin
                rec.update({'qty': dur.days})


class HotelRoomMove(models.Model):

    _inherit = 'hotel.room.move'
    _description = 'Hotel Room Move Line'

    reservation_id = fields.Many2one(
        'hotel.reservation', string='Reservation')
    status = fields.Selection(string='state', related='reservation_id.state')


class HotelRoomMoveLine(models.Model):

    _inherit = 'hotel.room.move.line'
    _description = 'Hotel Room Move Line'

    reservation_line_id = fields.Many2one('hotel_reservation.line',
                                          string='Reservation Line')


class HotelRoom(models.Model):

    _inherit = 'hotel.room'
    _description = 'Hotel Room'

    room_move_ids = fields.One2many(
        'hotel.room.move', 'room_id', 'Room Movement')

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        for room in self:
            for reserv_line in room.room_move_ids:
                if reserv_line.status == 'confirm':
                    raise ValidationError(_('User is not able to delete the \
                                            room after the room in %s state \
                                            in reservation')
                                          % (reserv_line.status))
        return super(HotelRoom, self).unlink()


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    reservation_id = fields.Many2one('hotel.reservation', 'Reservation')


class ReservationCancelReason(models.Model):
    _name = 'reservation.cancel.reason'
    _description = 'Reservation Cancellation Reason'
    
    name = fields.Char('Reason', required=True, translate=True)
