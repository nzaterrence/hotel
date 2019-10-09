# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError


class RoomChangeQuantity(models.TransientModel):
    _name = "hotel.change.room.qty"
    _description = "Change Room Quantity"

    room_id = fields.Many2one('hotel.room', 'Room', required=True)
    new_quantity = fields.Integer('New Room Quantity',
                                  default=1,required=True)

    @api.model
    def default_get(self, fields):
        res = super(RoomChangeQuantity, self).default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'hotel.room' and self.env.context.get('active_id'):
            res['room_id'] = self.env['hotel.room'].browse(self.env.context['active_id']).id
        return res

    @api.onchange('room_id')
    def onchange_room_id(self):
        if self.room_id:
            self.new_quantity = self.room_id.rooms_qty

    @api.constrains('new_quantity')
    def check_new_quantity(self):
        if any(wizard.new_quantity < 0 for wizard in self):
            raise UserError(_('Quantity cannot be negative.'))

    @api.multi
    def change_room_qty(self):
        room_number_obj = self.env['hotel.room.number']
        for rec in self:
            room_cnt = room_number_obj.search_count([('room_id', '=', rec.room_id.id),
                                                     ('state', '!=', 'closed')])
            th_qty = rec.new_quantity - room_cnt
            if th_qty > 0:
                for i in range(th_qty):
                    room_number_obj.with_context({'auto_seq':True}).create({'name': rec.room_id.name,
                                                   'room_id': rec.room_id.id,
                                                   'floor_id': rec.room_id.floor_id.id or False
                                                   })
            elif th_qty < 0:
                rooms = room_number_obj.search([('room_id', '=', rec.room_id.id),
                                                ('state', '!=', 'closed')],
                                               limit=abs(th_qty))
                rooms.write({'state': 'closed'})
        return {'type': 'ir.actions.act_window_close'}
