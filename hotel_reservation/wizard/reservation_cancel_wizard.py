# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

RESERVATION_STATES = ['draft', 'confirm']

class HotelReservationCancelWiz(models.TransientModel):
    _name = 'hotel.reservation.cancel.wiz'
    _description = 'Hotel Reservation Cancel Wiz'

    reason_id = fields.Many2one('reservation.cancel.reason',
                                         string='Cancellation Reason')

    @api.multi
    def confirm_cancel(self):
        act_close = {'type': 'ir.actions.act_window_close'}
        reservation_ids = self._context.get('active_ids')
        if reservation_ids is None:
            return act_close
        assert len(reservation_ids) == 1, "Only 1 sale ID expected"
        reservations = self.env['hotel.reservation'].browse(reservation_ids)
        reservations.write({'cancel_reason_id': self.reason_id.id})
        if reservations.state in RESERVATION_STATES:
            reservations.cancel_reservation()
        else:
            raise UserError(_('You cannot cancel the reservation in the '
                              'current state!'))
        return act_close