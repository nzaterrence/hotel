# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HotelRoomMove(models.Model):

    _name = 'hotel.room.move'
    _description = 'Hotel Room Move Line'
    _rec_name = 'room_id'

    room_id = fields.Many2one('hotel.room', 'Room',
                              required=True)
    room_qty = fields.Float('Qty', default=1.0)
    check_in = fields.Date('Check In Date', required=True)
    check_out = fields.Date('Check Out Date', required=True)
    state = fields.Selection([('reserved', 'Reserved'), 
                              ('assigned', 'Assigned'),
                              ('done', 'Done'),
                              ('cancel', 'Cancel')],
                             string='Room Status',
                             default='assigned',
                             store=True)
    room_move_line_ids = fields.One2many('hotel.room.move.line', 'room_move_id',
                                         'Room Move Line')
    folios_ids = fields.Many2many('hotel.folio',
                                  'hotel_folio_room_move_rel',
                                  'room_move_id', 'folio_id',
                                  string='Folio',
                                  readonly=True,copy=False)
    company_id = fields.Many2one('res.company', 'Hotel',
        default=lambda self: self.env['res.company']._company_default_get('hotel.room.move'), index=1)


class HotelRoomMoveLine(models.Model):

    _name = 'hotel.room.move.line'
    _description = 'Hotel Room Move Line'

    room_move_id = fields.Many2one('hotel.room.move', string="Room Move",
                                   ondelete="cascade", copy=False, readonly=False)
    room_number_id = fields.Many2one('hotel.room.number','Room id',
                                     required=True)
    state = fields.Selection(related='room_move_id.state',
                             string='Room Status',
                             readonly=True,
                             store=True)
    check_in = fields.Date(related='room_move_id.check_in',
                           string='Check In Date', readonly=True,
                           store=True)
    check_out = fields.Date(related='room_move_id.check_out',
                            string='Check Out Date', readonly=True,
                            store=True)
    folio_line_id = fields.Many2one('hotel.folio.line', 'Folio')
    company_id = fields.Many2one(related="room_move_id.company_id", string="Hotel",
                                 store=True)