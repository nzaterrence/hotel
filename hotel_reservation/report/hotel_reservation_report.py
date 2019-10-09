# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser
from odoo import models, fields, api


class ReportTestCheckin(models.AbstractModel):
    _name = "report.hotel_reservation.reservation_checkin_report_template"
    _description = "Reservation Checkin Report"

    def _get_room_type(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        room_dom = [('checkin', '>=', date_start),
                    ('checkout', '<=', date_end)]
        res = reservation_line_obj.search(room_dom)
        return res

    def _get_room_nos(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_checkin(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    @api.multi
    def _get_report_values(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        act_ids = self.env.context.get('active_ids', [])
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        date_start = data['form'].get('date_start')
        date_end = data['form'].get('date_end')
        rm_act = self.with_context(data['form'].get('used_context', {}))
        _get_room_type = rm_act._get_room_type(date_start, date_end)
        _get_room_nos = rm_act._get_room_nos(date_start, date_end)
        _get_checkin = rm_act._get_checkin(date_start, date_end)
        res = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_room_type': _get_room_type,
            'get_room_nos': _get_room_nos,
            'get_checkin': _get_checkin,
        }
        return res


class ReportTestCheckout(models.AbstractModel):
    _name = "report.hotel_reservation.reservation_checkout_report_template"
    _description = "Reservation Checkout Report"

    def _get_room_type(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkout', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_room_nos(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkout', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_checkout(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkout', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    @api.model
    def _get_report_values(self, docids, data):
        self.model = self.env.context.get('active_model')
        act_ids = self.env.context.get('active_ids', [])
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        date_start = data.get('date_start', fields.Date.today())
        date_end = data['form'].get('date_end',
                                    str(datetime.now() +
                                        relativedelta(months=+1,
                                                      day=1, days=-1))[:10])
        rm_act = self.with_context(data['form'].get('used_context', {}))
        _get_room_type = rm_act._get_room_type(date_start, date_end)
        _get_room_nos = rm_act._get_room_nos(date_start, date_end)
        _get_checkout = rm_act._get_checkout(date_start, date_end)
        res = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_room_type': _get_room_type,
            'get_room_nos': _get_room_nos,
            'get_checkout': _get_checkout,
        }
        return res


class ReportTestMaxroom(models.AbstractModel):
    _name = "report.hotel_reservation.reservation_maxroom_report_template"
    _description = "Maximum Used Rooms"

    def _get_room_type(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_room_nos(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_data(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_room_used_detail(self, date_start, date_end):
        room_used_details = []
        hotel_room_obj = self.env['hotel.room']
        room_ids = hotel_room_obj.search([])
        for room in hotel_room_obj.browse(room_ids.ids):
            counter = 0
            details = {}
            if room.room_number_ids:
                for room_resv_line in room.room_move_ids:
                    if(str(room_resv_line.check_in) >= date_start and
                       str(room_resv_line.check_in) <= date_end):
                        counter += 1
            if counter >= 1:
                details.update({'name': room.name or '',
                                'no_of_times_used': counter})
                room_used_details.append(details)
        return room_used_details

    @api.model
    def _get_report_values(self, docids, data):
        self.model = self.env.context.get('active_model')
        act_ids = self.env.context.get('active_ids', [])
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        date_start = data['form'].get('date_start', fields.Date.today())
        date_end = data['form'].get('date_end',
                                    str(datetime.now() +
                                        relativedelta(months=+1,
                                                      day=1, days=-1))[:10])
        rm_act = self.with_context(data['form'].get('used_context', {}))
        _get_room_type = rm_act._get_room_type(date_start, date_end)
        _get_room_nos = rm_act._get_room_nos(date_start, date_end)
        _get_data = rm_act._get_data(date_start, date_end)
        _get_room_used_detail = rm_act._get_room_used_detail(
            date_start, date_end)
        res = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_room_type': _get_room_type,
            'get_room_nos': _get_room_nos,
            'get_data': _get_data,
            'get_room_used_detail': _get_room_used_detail,
        }
        return res


class ReportTestRoomres(models.AbstractModel):
    _name = "report.hotel_reservation.reservation_room_report_template"
    _description = "Reservation List Report"

    def _get_room_type(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_room_nos(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    def _get_data(self, date_start, date_end):
        reservation_line_obj = self.env['hotel.reservation']
        res = reservation_line_obj.search([('checkin', '>=', date_start),
                                           ('checkout', '<=', date_end)])
        return res

    @api.model
    def _get_report_values(self, docids, data):
        self.model = self.env.context.get('active_model')
        act_ids = self.env.context.get('active_ids', [])
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        date_start = data.get('date_start', fields.Date.today())
        date_end = data['form'].get('date_end',
                                    str(datetime.now() +
                                        relativedelta(months=+1,
                                                      day=1, days=-1))[:10])
        rm_act = self.with_context(data['form'].get('used_context', {}))
        _get_room_type = rm_act._get_room_type(date_start, date_end)
        _get_room_nos = rm_act._get_room_nos(date_start, date_end)
        _get_data = rm_act._get_data(date_start, date_end)
        return {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_room_type': _get_room_type,
            'get_room_nos': _get_room_nos,
            'get_data': _get_data,
        }
