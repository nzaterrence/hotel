# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo import api, fields, models


class HMSDashboard(models.Model):
    _name = 'hms.dashboard'
    _description = "Hotel Management Dashboard"

    name = fields.Char("Name")
    date = fields.Date('Date')

    @api.model
    def get_hms_dashboard_details(self):
        """
        Dashboard count the New booking, Total Revenue, Arrivals and
        Departures for records.
        """
        user_rec = self.env.user
        company_id = user_rec.company_id
        symbol = company_id.currency_id.symbol
        position = company_id.currency_id.position
        today_total = 0.0
        total_total = 0.0
        is_hotel_manager = self.user_has_groups('hotel.group_hotel_manager')
        is_hote_user = self.user_has_groups('hotel.group_hotel_user')
        hotel_reservation_count_id = \
            self.env['hotel.reservation'].search_count(
                [('state', 'in', ('confirm', 'done'))])
        taday_start = datetime.now().replace(hour=0, minute=0, second=0)
        taday_end = taday_start.replace(hour=23, minute=59, second=59)
        today_reservation_count_id = \
            self.env['hotel.reservation'].search_count(
                [('date_order', '<=', str(taday_end)),
                 ('state', 'in', ('confirm', 'done')),
                 ('date_order', '>=', str(taday_start))])

        total_reservation_count = \
            self.env['hotel.reservation'].search_count(
                [])

        today_invoice_id = self.env['account.invoice'].search(
            [('date_invoice', '=', fields.Date.today()),
             ('type', 'in', ['out_invoice', 'out_refund']),
             ('state', 'not in', ['cancel', 'draft']),
             ])
        total_invoice_id = self.env['account.invoice'].search(
            [('state', 'not in', ['cancel', 'draft']),
             ('type', 'in', ['out_invoice', 'out_refund']),
             ])
        today_revenue_inv_ids = self.env['account.invoice'].search(
            [('date_invoice', '=', fields.Date.today()),
             ('type', 'in', ['out_invoice', 'out_refund']),
             ('state', 'not in', ['cancel', 'draft']),
             ]).ids

        today_total = sum(inv.amount_total
                          for inv in today_invoice_id)

        total_total = sum(inv.amount_total
                          for inv in total_invoice_id)

        today_arrival_count_id = self.env['hotel.reservation'].search_count(
            [('checkin', '=', fields.Date.today()),
             ('state', 'not in', ['cancel', 'draft'])])
        total_arrival_count = self.env['hotel.reservation'].search_count(
            [('state', 'not in', ['cancel', 'draft'])])
        today_arrival_ids = self.env['hotel.reservation'].search(
            [('state', 'not in', ['cancel', 'draft'])]).ids
        today_departure_count_id = self.env['hotel.folio'].search_count(
            [('checkout_date', '=', fields.Date.today()),
             ('state', 'not in', ['cancel', 'draft'])])
        total_departure_count = self.env['hotel.folio'].search_count(
            [('state', 'not in', ['cancel', 'draft'])])
        today_departure_ids = self.env['hotel.folio'].search(
            [('checkout_date', '=', fields.Date.today()),
             ('state', 'not in', ['cancel', 'draft'])]).ids
        total_departure_ids = self.env['hotel.folio'].search(
            [('state', 'not in', ['cancel', 'draft'])]).ids

        data = {
            'symbol': symbol,
            'position': position,
            'is_hotel_manager': is_hotel_manager,
            'is_hote_user': is_hote_user,
            'hotel_reservation_count_id': hotel_reservation_count_id,
            'today_reservation_count_id': today_reservation_count_id,
            'today_revenue': today_total,
            'total_revenue': total_total,
            'today_arrival_count_id': today_arrival_count_id,
            'today_arrival_ids': today_arrival_ids,
            'today_departure_count_id': today_departure_count_id,
            'today_departure_ids': today_departure_ids,
            'invoice_ids': today_revenue_inv_ids,
            'total_reservation_count': total_reservation_count,
            'total_arrival_count': total_arrival_count,
            'total_departure_count': total_departure_count,
            'total_departure_ids': total_departure_ids
        }
        return data

    @api.model
    def get_last_6_months_sales(self):
        max_val = 3000
        company_id = self.env.user.company_id.id
        self._cr.execute("""
            SELECT to_char(so.confirmation_date , 'Month') as month,
            SUM(so.amount_total) as total
            FROM sale_order AS so JOIN hotel_folio AS hf ON so.id = hf.order_id
            WHERE so.confirmation_date >  CURRENT_DATE - INTERVAL '6 months'
            and so.state != 'cancel' and so.company_id = %s
            GROUP BY month;
            """, (company_id,))
        datas = self._cr.dictfetchall()
        if datas:
            max_val = max(data.get('total') for data in datas)
            max_val = self.max_round_value(max_val)
        result = {
            'datas': datas,
            'max_val': max_val,
        }
        return result

    @api.model
    def get_last_5_reservations(self):
        datas = [{
            'partner_id': rec.partner_id.id,
            'checkin': rec.checkin,
            'checkout': rec.checkout,
            'state': rec.state,
            'guest_name': rec.partner_id.name,
        } for rec in self.env['hotel.reservation'].search([], limit=5)]
        return datas

    @api.model
    def get_last_10_reservations(self):
        datas = [{
            'id': rec.id,
            'reservation_no': rec.reservation_no,
            'partner_id': rec.partner_id.id,
            'checkin': rec.checkin,
            'checkout': rec.checkout,
            'state': rec.state,
            'phone': rec.partner_id.phone,
            'guest_name': rec.partner_id.name,
        } for rec in self.env['hotel.reservation'].search([], limit=10)]
        return datas

    @api.model
    def confirm_reservation(self, room_id):
        room_rec = self.env['hotel.reservation'].browse(room_id)
        room_rec.confirmed_reservation()

    @api.model
    def cancel_reservation(self, room_id):
        room_rec = self.env['hotel.reservation'].browse(room_id)
        room_rec.cancel_reservation()

    @api.model
    def get_pie_chart_data(self):
        company_id = self.env.user.company_id.id
        self._cr.execute("""
            SELECT COUNT(line.id) as total, prod_tmp.name
            FROM hotel_reservation_line as line JOIN hotel_room as room ON
            line.room_id = room.id JOIN product_product as prod ON
            room.product_id = prod.id
            JOIN product_template as prod_tmp ON
            prod.product_tmpl_id = prod_tmp.id
            AND prod_tmp.active = True AND
            line.company_id = %s AND
            prod_tmp.company_id = %s
            GROUP BY prod_tmp.name""", (company_id, company_id))
        datas = self._cr.dictfetchall()
        return datas

    def max_round_value(self, amount):
        return amount if amount % 100 == 0 else amount + 100 - amount % 100

    @api.model
    def get_room_current_rate(self, room_ids=[], current_date=False):
        datas = []
        room_pricelist_line_obj = self.env['room.pricelist.line']
        hotel_reservation_line_obj = self.env['hotel_reservation.line']
        if not room_ids:
            rooms = self.env['hotel.room'].search([])
        else:
            rooms = self.env['hotel.room'].browse(room_ids)
        if not current_date:
            current_date = fields.Date.context_today(self)
        for room in rooms:
            pricelist_line = room_pricelist_line_obj.search(
                [('room_id', '=', room.id),
                 ('date', '=', current_date),
                 ('company_id', '=', self.env.user.company_id.id)],
                limit=1)
            if pricelist_line:
                price = pricelist_line.room_price
            else:
                price = room.list_price
            room_qty = hotel_reservation_line_obj.get_available_room_qty(
                room, current_date, current_date)
            datas.append({
                'room': room.name,
                'description': room.description or room.name,
                'rate_price': price,
                'room_qty': room_qty
            })
        return datas
