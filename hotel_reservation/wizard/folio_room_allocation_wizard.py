# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt, DEFAULT_SERVER_DATE_FORMAT


class HotelFolioRoomAllocation(models.TransientModel):
    _name = 'hotel.folio.room.allocation'
    _description = 'Hotel Folio Room Allocation'

    @api.constrains('room_qty', 'folio_allocation_ids')
    def check_folio_room_allocations(self):
        """To check that the selected room allocations can not be more than quantity."""
        for rec in self.folio_allocation_ids:
            if rec.room_numbers_ids and rec.room_numbers_ids.ids and len(rec.room_numbers_ids.ids) != rec.room_qty:
                raise ValidationError(
                    _("Room Allocations should be selected as per quantity!"))

    reservation_id = fields.Many2one(
        'hotel.reservation', 'Reservation', required=False)
    folio_allocation_ids = fields.One2many('hotel.folio.room.allocation.line',
                                           'folio_allocation_id',
                                           string='Allocation Lines')

    def folio_process(self):
        hotel_folio_obj = self.env['hotel.folio']
        for rec in self:
            folio_lines = []
            services_lines = []
            folio_vals = {
                'partner_id': rec.reservation_id.partner_id.id,
                'date_order': rec.reservation_id.date_order
                }
            # Initiating a new folio record object
            folio_new = self.env['hotel.folio'].new(folio_vals)

            # Calling the default_get method of folio
            folio_vals.update(folio_new.default_get(folio_new._fields))
            
            folio_vals.update({
                'company_id': rec.reservation_id.company_id.id,
                'partner_invoice_id': rec.reservation_id.partner_invoice_id.id,
                'partner_shipping_id': rec.reservation_id.partner_shipping_id.id, 
                'pricelist_id': rec.reservation_id.pricelist_id.id,
                'checkin_date': rec.reservation_id.checkin,
                'checkout_date': rec.reservation_id.checkout,
                'reservation_id': rec.reservation_id.id,
            })
            for service in rec.reservation_id.service_lines:
                services_lines.append((0, 0,
                                       {
                                        'checkin': service.checkin,
                                        'checkout': service.checkout,
                                        'product_id': service.product_id.id,
                                        'name': service.product_id.name or '',
                                        'product_uom_qty': service.qty,
                                        'price_unit': service.price_unit,
                                        'tax_id': [(6, 0, service.tax_id.ids)],
                                        'discount': service.discount,
                                        'per_night_bool': service.per_night_bool,
                                        'extra_bed_service_line_bool': service.extra_bed_service_line_bool,
                                        }))
#           for line in rec.reservation_id.reservation_line:
            for allocation_line in rec.folio_allocation_ids:
                if not allocation_line.room_numbers_ids:
                    raise ValidationError(
                        _("Kindly to add room number in allocation!"))
                room_no = 0
                for line in allocation_line.reservation_lines_ids:
                    folio_lines.append((0, 0, {
                        'checkin_date': line.checkin,
                        'checkout_date': line.checkout,
                        'room_id': line.room_id.id,
                        'product_id': line.room_id and line.room_id.product_id.id,
                        'room_number_id': allocation_line.room_numbers_ids.ids[room_no],
                        'name': line.name,
                        'price_unit': line.price_unit,
                        'tax_id': [(6, 0, line.tax_id.ids)],
                        'discount': line.discount,
                        'product_uom_qty': line.stay_days,
                        'product_uom': line.room_id.product_id.uom_id.id,
                        'qty_to_invoice': line.qty_to_invoice,
                        'qty_invoiced': line.qty_invoiced,
                        'reservation_lines_ids': [(6, 0, [line.id])],
                        'service_line_bool': line.service_line_bool,
                    }))
                    room_no += 1

            folio_vals.update({'service_lines': services_lines,
                               'folio_lines': folio_lines
                               })
            folio = hotel_folio_obj.sudo().with_context({'set_room_aminities': True}).create(folio_vals)
            self.reservation_id.state = 'done'
        return True


class HotelFolioRoomAllocationLines(models.TransientModel):
    _name = 'hotel.folio.room.allocation.line'
    _description = 'Hotel Folio Room Allocation Line'

    @api.depends('room_numbers_ids')
    def _compute_selected_room(self):
        for rec in self:
            rec.room_selected_count = len(rec.room_numbers_ids.ids)

    folio_allocation_id = fields.Many2one('hotel.folio.room.allocation', 'Reservation',
                                          required=True)
    reservation_lines_ids = fields.Many2many('hotel_reservation.line',
                                             string='Reservation Line',
                                             required=True)
    room_id = fields.Many2one('hotel.room', string="Room")
    room_selected_count = fields.Integer(compute="_compute_selected_room")
    room_qty = fields.Integer()
    room_numbers_ids = fields.Many2many('hotel.room.number', string="Room Allocation",
                                        domain="[('state', '=', 'available'),('room_id', '=', room_id)]")
