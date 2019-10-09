# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
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


class HotelFloor(models.Model):
    _name = "hotel.floor"
    _description = "Floor"

    name = fields.Char('Floor Name', size=64, required=True, index=True)
    sequence = fields.Integer('Sequence', size=64, index=True)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    isroom = fields.Boolean('Is Room')
    service_ok = fields.Boolean('Can be Service')
    per_night_bool = fields.Boolean('Rate Per Night',
                                    help="If you select true then in service line to charge per night")


class HotelRoomAmenitiesType(models.Model):
    _name = 'hotel.room.amenities.type'
    _description = 'amenities Type'

    product_category_id = fields.Many2one('product.category', 'Product Category',
                                 required=True, delegate=True,
                                 ondelete='cascade',
                                 domain=[('type', '=', 'service')])
    parent_id = fields.Many2one('hotel.room.amenities.type', 'Parent Category', index=True,
                                ondelete='cascade', oldname="amenity_id")
    child_id = fields.One2many('hotel.room.amenities.type', 'parent_id', 'Child Categories')


class HotelRoomAmenities(models.Model):
    _name = 'hotel.room.amenities'
    _description = 'Room amenities'

    product_id = fields.Many2one('product.product', 'Product Category',
                                 required=True, delegate=True,
                                 ondelete='cascade',
                                 domain=[('type', '=', 'service')])
    categ_id = fields.Many2one('hotel.room.amenities.type',
                               string='Amenities Category', required=True)
    product_manager = fields.Many2one('res.users', string='Product Manager')
#    taxes_id = fields.Many2many('account.tax', 'product_taxes_rel', 'prod_id', 'tax_id',
#                                string='Customer Taxes',
#                                domain=[('type_tax_use', '=', 'sale')])
    
#    @api.model
#    def create(self, vals):
#        res = super(HotelRoomAmenities, self).create(vals)
#        if vals.get('taxes_id'):
#            res.product_id.write({'taxes_id':vals.get('taxes_id')})
#        return res
#    
#    @api.multi
#    def write(self, vals):
#        res = super(HotelRoomAmenities, self).write(vals)
#        for rec in self:
#            if vals.get('taxes_id'):
#                rec.product_id.write({'taxes_id':vals.get('taxes_id')})
#        return res
#    
    @api.multi
    def unlink(self):
        for rec in self:
            rec.product_id.unlink()
        return super(HotelRoomAmenities, self).unlink()


class HotelRoomNumber(models.Model):
    _name = 'hotel.room.number'
    _description = 'Hotel Room Number'

    name = fields.Char('Room Number', required=True)
    floor_id = fields.Many2one('hotel.floor', 'Floor No',
                               ondelete='cascade',
                               help='At which floor the room is located.')
    room_location = fields.Char('Location')
    extra_charge = fields.Float('Extra Charge')
    active = fields.Boolean(default=True)
    room_id = fields.Many2one('hotel.room', 'Room No',
                              ondelete='cascade', required=True)
    state = fields.Selection([('available', 'Available'),
                              ('closed', 'Closed'),
                              ('maintenance', 'Maintenance')],
                             default='available')
    company_id = fields.Many2one(related='room_id.company_id',
                                 string="Hotel")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Room number must be unique!'),
    ]
    
    @api.model
    def create(self, vals):
        seq_obj = self.env['ir.sequence']
        if self._context.get('auto_seq') and vals.get('name'):
            seq_no = seq_obj.next_by_code('hotel.room.number') or 'New'
            vals.update({'name':  vals.get('name', '') + '-' + seq_no})
        return super(HotelRoomNumber, self).create(vals)

    @api.multi
    def action_maintenance(self):
        """Method for the button used when in maintenance and moves to that state."""
        self.write({'state': 'maintenance'})
    
    @api.multi
    def action_close_room(self):
        self.write({'state': 'closed'})

    @api.multi
    def action_open_room(self):
        self.write({'state': 'available'})

    @api.multi
    def hotel_room_move_line(self):
        """Method of the smart button for traceability."""
        return {
            'name': 'Hotel Move Line',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'hotel.room.move.line',
            'domain': [('room_number_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }


class HotelRoom(models.Model):
    _name = 'hotel.room'
    _description = 'Hotel Room'

    @api.depends('room_number_ids', 'room_number_ids.state')
    def _compute_room_qty(self):
        for rec in self:
            rooms = self.mapped('room_number_ids').filtered(
                lambda r: r.state != 'closed')
            rec.update({'rooms_qty': len(rooms.ids)})

    @api.depends('room_move_ids')
    def _compute_count_room(self):
        """Compute field for smart button traceability."""
        for rooms in self:
            rooms.count_room = len(rooms.room_move_ids.ids)

    product_id = fields.Many2one('product.product', 'Product_id',
                                 required=True, delegate=True,
                                 ondelete='cascade')
    floor_id = fields.Many2one('hotel.floor', 'Floor No', ondelete='cascade',
                               help='At which floor the room is located.')
    max_adult = fields.Integer("Maximum Adult", default="1")
    max_child = fields.Integer("Maximum Children")
    room_amenities = fields.Many2many('hotel.room.amenities',
                                      string='Room Amenities',
                                      help='List of room amenities.')
    status = fields.Selection([('available', 'Available'),
                               ('occupied', 'Occupied')],
                              'Status', default='available')
    capacity = fields.Integer('Total Capacity', required=True, default=1)
    rooms_qty = fields.Integer('No of Rooms', compute="_compute_room_qty",
                               store=True)
    room_number_ids = fields.One2many('hotel.room.number', 'room_id',
                                      'Rooms Numbers')
    room_move_ids = fields.One2many('hotel.room.move', 'room_id',
                                    'Room Movement')
    count_room = fields.Integer(compute="_compute_count_room")

    @api.multi
    def unlink(self):
        for rec in self:
            rec.product_id.unlink()
        return super(HotelRoom, self).unlink()

    def action_open_room_number(self):
        rooms = self.mapped('room_number_ids').filtered(
            lambda r: r.state != 'closed')
        action = self.env.ref('hotel.action_hotel_room_number').read()[0]
        action['domain'] = [('id', 'in', rooms.ids)]
        return action

    @api.constrains('capacity')
    def check_capacity(self):
        for room in self:
            if room.capacity <= 0:
                raise ValidationError(_('Room capacity must be more than 0!'))
        total = room.max_adult + room.max_child
        if room.capacity < total:
            raise ValidationError(
                _('Persons should be according to capacity!'))

    @api.multi
    def trace_hotel_move(self):
        """Method of the smart button for traceability."""
        return {
            'name': 'Trace Hotel',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'hotel.room.move',
            'domain': [('id', 'in', self.room_move_ids.ids)],
            'type': 'ir.actions.act_window',
        }

#    def cron_update_category(self):
#        product_category_obj = self.env['product.category']
#
#        self._cr.execute("""SELECT id,name from hotel_room_amenities_type where product_category_id is null""")
#        datas = self._cr.fetchall()
#        for amenities_type in datas:
#            product_category = product_category_obj.sudo().create({'name': amenities_type[1]})
#            self._cr.execute("""UPDATE hotel_room_amenities_type SET product_category_id=%s WHERE id=%s""",
#                             (product_category.id, amenities_type[0]))
#
#        self._cr.execute("""SELECT id,name from hotel_service_type where product_category_id is null""")
#        datas = self._cr.fetchall()
#        for service_type in datas:
#            product_category = product_category_obj.sudo().create({'name': service_type[1]})
#            self._cr.execute("""UPDATE hotel_service_type SET product_category_id=%s WHERE id=%s""",
#                             (product_category.id, service_type[0]))
