
from odoo import api, models, fields
from datetime import datetime


class HotelFolioRoomAllocation(models.TransientModel):
    _inherit = 'hotel.folio.room.allocation'

    def folio_process(self):
        active_id = self.env.context.get('active_id')
        for roomtype in self.folio_allocation_ids:
            for room in roomtype.room_numbers_ids:
                if active_id:
                    activity_plan = self.env['hotel.housekeeping.activity.plan'].search(
                        [('activity_plan', '=', 'oncheckin')],
                        limit=1)
                    hotel_housekeeping_obj = self.env['hotel.housekeeping']
                    service_ids = []
                    for service in activity_plan.activity_line_ids:
                        if service:
                            service_ids.append([0, 0, {'activity_name': service.activity_id.id,
                                                       'today_date': fields.Date.context_today(self),
                                                       'state': ''}])
                    vals = {'name':activity_plan.name,
                            'current_date': fields.Date.context_today(self),
                            'clean_type': 'checkin',
                            'inspector_id': activity_plan.user_id.id,
                            'inspect_date_time': datetime.today(),
                            'state': 'inspect',
                            'room_no': roomtype.room_id.id,
                            'room_number_id': room.id,
                            'activity_line_ids': service_ids}
                    hotel_housekeeping_obj.create(vals)

        return super(HotelFolioRoomAllocation, self).folio_process()


class HotelFolio(models.Model):
    _inherit = 'hotel.folio'

    @api.multi
    def action_done(self):
        activity_plan = self.env['hotel.housekeeping.activity.plan'].search(
                                                [('activity_plan', '=', 'oncheckout')],
                                                limit=1)
        hotel_housekeeping_obj = self.env['hotel.housekeeping']
        for folio in self.folio_lines:
            service_ids = []
            for service in activity_plan.activity_line_ids:
                service_ids.append([0, 0, {'activity_name': service.activity_id.id,
                                           'today_date': fields.Date.context_today(self),
                                           'state': 'dirty'}])
            vals = {'name':activity_plan.name,
                    'current_date': fields.Date.context_today(self),
                    'clean_type': 'checkout',
                    'inspector_id': activity_plan.user_id.id,
                    'inspect_date_time': datetime.today(),
                    'state': 'inspect',
                    'room_no': folio.room_id.id,
                    'room_number_id': folio.room_number_id.id,
                    'activity_line_ids': service_ids}
            hotel_housekeeping_obj.create(vals)

        return super(HotelFolio, self).action_done()
