
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Adults(models.Model):
    _name = "hotel.reservation.adults"
    _description = "Adult Details"

    name = fields.Char('Name', required=True)
    image = fields.Binary('Image', attachment=True)
    color = fields.Integer(string='Color Index', default=0)
    age = fields.Integer('Age', required=True)
    mobile = fields.Char('Mobile')
    reservation_id = fields.Many2one('hotel.reservation',
                                     'Reservation')
