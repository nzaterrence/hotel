# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser
from odoo import api, fields, models


class FolioReport(models.AbstractModel):
    _name = 'report.hotel.report_hotel_folio'
    _description = 'Report Hotel Folio'

    def _get_folio_data(self, date_start, date_end):
        total_amount = 0.0
        data_folio = []
        folio_obj = self.env['hotel.folio']
        act_domain = [('checkin_date', '>=', date_start),
                      ('checkout_date', '<=', date_end)]
        folios = folio_obj.search(act_domain)
        for data in folios:
            data_folio.append({'name': data.name,
                               'partner': data.partner_id.name,
                               'checkin': (data.checkin_date).strftime('%d-%m-%Y'),
                               'checkout': (data.checkout_date).strftime('%d-%m-%Y'),
                               'amount': '%.2f' % float(data.amount_total)})
            total_amount += float(data.amount_total)
        data_folio.append({'total_amount': '%.2f' % float(total_amount)})
        return data_folio

    @api.model
    def _get_report_values(self, docids, data):
        self.model = self.env.context.get('active_model')
        if data is None:
            data = {}
        if not docids:
            docids = data['form'].get('docids')
        folio_profile = self.env['hotel.folio'].browse(docids)
        date_start = data['form'].get('date_start')
        date_end = data['form'].get('date_end')
        rec = {
            'doc_ids': docids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': folio_profile,
            'folio_data': self._get_folio_data(date_start, date_end)
        }
        rec['data'].update({'date_end':
                            parser.parse(rec.get('data').
                                         get('date_end')).
                            strftime('%d/%m/%Y')})
        rec['data'].update({'date_start':
                            parser.parse(rec.get('data').
                                         get('date_start')).
                            strftime('%d/%m/%Y')})
        return rec
