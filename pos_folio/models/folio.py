# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    folio_id = fields.Many2one('hotel.folio', 'Folio Number')
    room_no = fields.Char('Room Number')

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['folio_id'] = ui_order.get('folio_id', False)
        table_data = ui_order.get("table_data")
        if table_data:
            if ui_order.get('folio_id', False):
                restaurant_table_obj = self.env['restaurant.table']
                restaurant_table_obj.sudo().remove_table_order(table_data)
        return order_fields


class HotelFolio(models.Model):
    _inherit = "hotel.folio"

    def get_folio_data(self, input_value=None):
        input_folio_val = input_value.get('input_value')
        folio = self.search_read([('name','ilike',input_folio_val),
                                  ('state','in',['draft','sale'])],
                                 ['id','name','partner_id'])
        folio_lines = self.env['hotel.folio.line'].search(
                [('room_number_id','ilike',input_folio_val)],
               )
        for folio_line in folio_lines:
            folio_id = folio_line.folio_id
            if folio_id and folio_id.state in ['draft','sale']:
                folio.append({'id': folio_id.id ,
                           'name':folio_id.name,
                           'partner_id': [folio_id.partner_id.id,
                                     folio_id.partner_id.name]})
        return folio

