# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HotelQuickReservation(models.Model):
    _name = 'hotel.quick.reservation'
    _description = 'Hotel Quick Reservation'
    _auto = False

    room_id = fields.Many2one("hotel.room", string="Room")
    price = fields.Float(
        string="Price")
    room_qty = fields.Integer(
        string="Availability")
    room_date = fields.Date(string="Date")

    @api.model
    def init(self):
        self._cr.execute("""
            CREATE or REPLACE view hotel_quick_reservation as (
                SELECT
                row_number() OVER () AS id,
                current_date + s.a AS room_date,
                room.id as room_id,
                CASE
                    WHEN (select room_qty from room_availability_line
                        WHERE date=(current_date + s.a)
                        AND room_category_id=room.id) >= 0 THEN
                    (select room_qty from room_availability_line
                        WHERE date=(current_date + s.a)
                        AND room_category_id=room.id)
                    ELSE room.rooms_qty END AS room_qty,
                CASE
                   WHEN (select room_price from room_pricelist_line
                    WHERE date=(current_date + s.a)
                    AND room_id=room.id
                    AND company_id=prod_tmp.company_id) >= 0 THEN
                    (select room_price from room_pricelist_line
                    WHERE date=(current_date + s.a)
                    AND room_id=room.id
                    AND company_id=prod_tmp.company_id)
                    ELSE prod_tmp.list_price END AS price
                        FROM generate_series(0,30) AS s(a),
                hotel_room as room LEFT JOIN product_product as prod
                on room.product_id = prod.id
                LEFT JOIN product_template as prod_tmp
                ON prod.product_tmpl_id = prod_tmp.id)
        """)
