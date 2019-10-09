# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HotelFrontdesk(models.Model):
    _name = 'hotel.frontdesk'
    _description = "Hotel Management Frontdesk"

    name = fields.Char("Name")
    date = fields.Date("Date")

    @api.model
    def room_detail(self):
        rooms = self.env['hotel.room'].search([])

        datas = []
        for room in rooms:
            datas.append({
                'room_name': room.name,
                'room_id': room.id,
                'title_row': True})
            self._cr.execute("""
                    SELECT line.id AS id, room.id as room_id,
                            line.check_in AS start,line.check_out AS end,
                            prod_tmp.name as room_name,rno.name AS title,
                            part.name AS name,
                            line.folio_line_id,
                            line.state,line.reservation_line_id,
                            rno.id as resid, resline.reservation_id,
                            folioline.folio_id,
                    CASE WHEN folioline.folio_id is not null THEN folio.name
                         WHEN resline.reservation_id is not null
                         THEN res.reservation_no
                    END AS seq_no,
                    CASE WHEN folioline.folio_id is not null
                         THEN sale_line.product_uom_qty
                         WHEN resline.reservation_id is not null THEN
                    date_part('day',age(resline.checkout, resline.checkin))
                    END AS qty,
                    CASE WHEN folioline.folio_id is not null
                         THEN sale_line.price_unit
                         WHEN resline.reservation_id is not null
                         THEN resline.price_unit
                    END AS price_unit,
                    CASE WHEN folioline.folio_id is not null
                         THEN sale_line.price_subtotal
                         WHEN resline.reservation_id is not null
                         THEN resline.price_subtotal
                    END AS price_subtotal
                            from hotel_room_number AS rno
                            JOIN hotel_room AS room ON room.id = rno.room_id
                            JOIN product_product as prod
                            ON room.product_id = prod.id
                            JOIN product_template as prod_tmp
                            ON prod.product_tmpl_id = prod_tmp.id
                            LEFT JOIN hotel_room_move_line AS line
                            ON (rno.id = line.room_number_id)
                            AND (line.state != 'cancel')
                    AND (line.check_in >= current_date - interval '10 days')
                            LEFT JOIN hotel_reservation_line AS resline ON
                            line.reservation_line_id = resline.id
                            LEFT JOIN hotel_folio_line AS folioline ON
                            line.folio_line_id = folioline.id
                            LEFT JOIN hotel_folio AS folio
                            ON folioline.folio_id = folio.id
                            LEFT JOIN sale_order AS sale
                            ON sale.id = folio.order_id
                    LEFT JOIN sale_order_line AS sale_line
                            ON sale_line.id = folioline.order_line_id
                            LEFT JOIN hotel_reservation AS res ON
                            resline.reservation_id = res.id
                            LEFT JOIN res_partner as part ON
                            (res.partner_id = part.id)
                            OR (sale.partner_id = part.id )
                    WHERE room.id = %s
                    ORDER BY title""", (room.id,))
            room_datas = self._cr.dictfetchall()
            datas.extend(room_datas)

        return datas

    @api.model
    def get_date_change_rate(self, new_room_id, start_date, end_date):
        start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)

        date_delta = end_date - start_date
        qty = date_delta.days

        if new_room_id:
            self._cr.execute("""SELECT MAX(room_price) FROM room_pricelist_line
                                WHERE room_id=%s AND date BETWEEN %s AND %s
                                AND company_id=%s""",
                             (new_room_id, start_date, end_date,
                              self.env.user.company_id.id))
            rate_plan = self._cr.fetchone()[0]
            if rate_plan is not None:
                unit_price = rate_plan
            else:
                unit_price = self.env['hotel.room'].browse(
                    new_room_id).list_price
        return {
            'qty': qty,
            'new_unit_price': unit_price,
            'new_total_price': qty * unit_price
        }
