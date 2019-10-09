from odoo import api, models, _
from odoo.exceptions import ValidationError

class HotelReservation(models.Model):
    _inherit = 'hotel.reservation'

    @api.multi
    def get_extra_bed_qty(self):
        extra_bed_product_id = self.company_id.extra_bed_charge_id.id or False

        extra_bed_lines = self.service_lines.search([('product_id', '=', extra_bed_product_id),
                                                      ('reservation_id', '=', self.id)])
        extra_bed_qty = sum(product_line.qty for product_line in extra_bed_lines)
        return extra_bed_qty

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
            capacity = 0
            if reservation.adults <= 0:
                raise ValidationError(_('Adults must be more than 0'))
            for room_no in reservation.reservation_line.mapped('room_number_id'):
                #get the same room number lines
                lines = reservation_line_obj.search([('room_number_id', '=', room_no.id),
                                                     ('reservation_id', '=', reservation.id)])
                #checked the each line and find if checkin and checkout date same or not
                for line in lines:
                    record = lines.search([('id', 'in', lines.ids),
                                           ('id', '!=', line.id),
                                           ('checkin', '>=', line.checkin),
                                           ('checkout', '<=', line.checkout),
                                           ('room_number_id', '=', room_no.id)])
                    if record:
                        raise ValidationError(_('''Room Duplicate Exceeded!,
                                                %s Rooms Already Have Selected in Reservation!''')%
                                              (room_no.name))

            for room in reservation.reservation_line.mapped('room_id'):
                lines = reservation_line_obj.search([('room_id', '=', room.id),
                                                     ('reservation_id', '=', reservation.id)])
                capacity += sum(line.qty * line.room_id.capacity for line in lines)
                capacity += self.get_extra_bed_qty()
            if reservation.reservation_line and (reservation.adults + reservation.children) > capacity:
                raise ValidationError(_("Room Capacity Exceeded! ,\
                            Please Select Rooms According to Members Accomodation!"))
