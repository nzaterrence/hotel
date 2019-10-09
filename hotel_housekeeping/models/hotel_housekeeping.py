# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError


class HotelHousekeeper(models.Model):
    _name = 'hotel.housekeeper'

    employee_id = fields.Many2one('hr.employee', 'Housekepeer',
                                  required=True, delegate=True,
                                  ondelete='cascade')


class HouseKeepingSchedule(models.Model):
    _name = 'house.keeping.schedule'

    room_id = fields.Many2one('hotel.room')
    room_number_id = fields.Many2one('hotel.room.number', 'Room Number',
                                     required=True)


class HotelHousekeepingActivity(models.Model):

    _name = 'hotel.housekeeping.activity'
    _description = 'Housekeeping Activity'

    product_id = fields.Many2one('product.product', 'Service',
                                 required=True, delegate=True,
                                 ondelete='cascade', index=True)


class HotelHousekeepingStatusLog(models.Model):

    _name = 'hotel.housekeeping.status.log'

    log_date = fields.Datetime('Log Datetime')
    room_number_id = fields.Many2one('hotel.room.number', 'Room Number',
                                     required=True)
    state = fields.Selection([('clean', 'Clean'),
                              ('dirty', 'Dirty'),
                              ('maintenance', 'Maintenance')],
                             string="Status",
                             default='clean',
                             required=True)
    housekeeper_id = fields.Many2one('hotel.housekeeper', 'Housekeeper',
                                     required=False)
    remarks = fields.Text('Remarks')


class HotelHousekeepingStatus(models.Model):

    _name = "hotel.housekeeping.status"

    room_number_id = fields.Many2one('hotel.room.number', 'Room Number',
                                     required=True)
    room_id = fields.Many2one('hotel.room', 'Hotel Room')
    state = fields.Selection([('clean', 'Clean'),
                              ('dirty', 'Dirty'),
                              ('maintenance', 'Maintenance')],
                             string="Status",
                             default='clean',
                             required=True)
    room_status = fields.Selection([('arrived', 'Arrived'),
                                    ('available', 'Available'),
                                    ('stay_over', 'Stay Over'),
                                    ('closed', 'Closed'),
                                    ('maintenance', 'Maintenance')],
                                   string="Availability",
                                   default='available')
    housekeeper_id = fields.Many2one('hotel.housekeeper', 'Housekeeper',
                                     required=False)
    remarks = fields.Text('Remarks')

    @api.onchange('room_number_id')
    def onchange_room_number(self):
        if self.room_number_id:
            self.room_id = self.room_number_id.room_id.id or False

    @api.multi
    def write(self, vals):
        status_log_obj = self.env['hotel.housekeeping.status.log']
        if vals.get('housekeeper_id') or vals.get('state') or vals.get('remarks'):
            logs_vals = ({
                'log_date': datetime.now(),
                'room_number_id': self.room_number_id.id,
                'state': self.state,
                'housekeeper_id': vals.get('housekeeper_id'),
                'remarks': vals.get('remarks')
            })
            status_log_obj.sudo().create(logs_vals)
        return super(HotelHousekeepingStatus, self).write(vals)

    @api.model
    def open_housekeeping_status(self):
        view_type = 'tree'
        rooms = self.env['hotel.room.number'].search(
            [('state', '!=', 'closed')])
        room_status_ids = []
        for room in rooms:
            rooms_status = self.search([('room_number_id', '=', room.id)])
            if not rooms_status:
                room_status = self.create({
                    'room_number_id': room.id,
                    'room_id': room.room_id.id,
                })
                room_status_ids.append(room_status.id)
            else:
                room_status_ids.extend(rooms_status.ids)
        domain = "[('id', 'in', " + str(room_status_ids) + ")]"
        context = {'search_default_room_type': 1}
        value = {
            'domain': domain,
            'context': context,
            'name': _('Housekeeping Status'),
            'view_type': 'form',
            'view_mode': view_type,
            'res_model': 'hotel.housekeeping.status',
            'type': 'ir.actions.act_window'
        }
        return value


class HotelHousekeepingActivities(models.Model):

    _name = "hotel.housekeeping.activities"
    _description = "Housekeeping Activities "

    def _cleaning_duration(self):
        for duration in self:
            duration.cleaning_time = duration.clean_end_time - duration.clean_start_time

    # housekeeping_id = fields.Many2one('hotel.housekeeping', string='Reservation')
    a_list = fields.Many2one('hotel.housekeeping', string='Reservation')
    today_date = fields.Date('Today Date', required=True)
    activity_name = fields.Many2one('hotel.housekeeping.activity',
                                    string='Housekeeping Activity', required=True)
    housekeeper = fields.Many2one('res.users', string='Housekeeper')
    clean_start_time = fields.Datetime('Clean Start Time')
    clean_end_time = fields.Datetime('Clean End Time')
    cleaning_time = fields.Char(
        'Cleaning Duration', compute="_cleaning_duration")
    dirty = fields.Boolean('Dirty',
                           help='Checked if the housekeeping activity'
                           'results as Dirty.')
    clean = fields.Boolean('Clean', help='Checked if the housekeeping'
                           'activity results as Clean.')
    state = fields.Selection([('clean', 'Clean'),
                              ('dirty', 'Dirty'),
                              ('maintenance', 'Maintenance')],
                             string="Status",
                             default='clean')

    @api.constrains('clean_start_time', 'clean_end_time')
    def check_clean_start_time(self):
        '''
        This method is used to validate the clean_start_time and
        clean_end_time.
        ---------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        if self.clean_start_time >= self.clean_end_time:
            raise ValidationError(_('Start Date Should be \
            less than the End Date!'))

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(HotelHousekeepingActivities, self).default_get(fields)
#        if self._context.get('room_id', False):
#            res.update({'room_id': self._context['room_id']})
        if self._context.get('today_date', False):
            res.update({'today_date': self._context['today_date']})
        return res


class HotelHousekeepingActivityPlan(models.Model):

    _name = "hotel.housekeeping.activity.plan"
    _description = "Housekeeping Activity Plan"

    name = fields.Char("Name", required=True)
    activity_plan = fields.Selection([('oncheckin', 'On Checkin'),
                                      ('oncheckout', 'On Checkout'),
                                      ('ondayuse', 'On Day Use')],
                                     string="Activity Type", required=True)
    activity_line_ids = fields.One2many('hotel.housekeeping.activity.plan.line',
                                        'activity_plan_id', 'Services')
    user_id = fields.Many2one('res.users', string='Responsible',
                              default=lambda self: self.env.user)
    active = fields.Boolean(default=True)

    # _sql_constraints = [
    #     ("name_uniq", "unique(activity_plan)",
    #      "Can't create same activity plan again!"),
    # ]

    # @api.constrains('activity_plan')
    # def housekeeping_activity_plan(self):
    #     self._cr.execute("""SELECT activity_plan FROM hotel_housekeeping_activity_plan
    #       WHERE activity_plan IN ('oncheckin','oncheckout');
    #         """)
    #     datas = self._cr.dictfetchall()
    #     if datas:
    #         if self.activity_plan in ["oncheckin", "oncheckout"]:
    #             raise ValidationError(
    #                 _("Can't create same activity plan again!"))


class HotelHousekeepingActivityPlanLine(models.Model):

    _name = "hotel.housekeeping.activity.plan.line"
    _description = "Housekeeping Activity Plan Line"

    activity_id = fields.Many2one(
        'hotel.housekeeping.activity', 'Activity', required=True)
    name = fields.Char("Name", required=True)
    activity_plan_id = fields.Many2one(
        'hotel.housekeeping.activity.plan', 'Activity Plan')

    @api.multi
    @api.onchange('activity_id')
    def onchange_activity_id(self):
        if self.activity_id:
            self.name = self.activity_id.name


class HotelHousekeeping(models.Model):

    _name = "hotel.housekeeping"
    _description = "Hotel Housekeeping"
    _rec_name = 'room_no'

    name = fields.Char("Name", required=True)
    current_date = fields.Date("Today's Date", required=True,
                               index=True,
                               states={'done': [('readonly', True)]},
                               default=fields.Date.today)
    clean_type = fields.Selection([('daily', 'Daily'),
                                   ('checkin', 'Check-In'),
                                   ('checkout', 'Check-Out')],
                                  'Clean Type', required=True,
                                  states={'done': [('readonly', True)]},)
    room_no = fields.Many2one('hotel.room', 'Room Type',
                              states={'done': [('readonly', True)]})
    room_number_id = fields.Many2one('hotel.room.number', 'Room Number',
                                     domain="[('room_id', '=', room_no)]")
    activity_line_ids = fields.One2many('hotel.housekeeping.activities',
                                        'a_list', 'Activities',
                                        states={'done': [('readonly', True)]},
                                        help='Detail of housekeeping'
                                        'activities')
    inspector_id = fields.Many2one('res.users', 'Inspector', required=True,
                                   index=True,
                                   states={'done': [('readonly', True)]})
    inspect_date_time = fields.Datetime('Inspect Date Time', required=True,
                                        states={'done': [('readonly', True)]})
    quality = fields.Selection([('excellent', 'Excellent'), ('good', 'Good'),
                                ('average', 'Average'), ('bad', 'Bad'),
                                ('ok', 'Ok')], 'Quality',
                               states={'done': [('readonly', True)]},
                               help="Inspector inspect the room and mark \
                                as Excellent, Average, Bad, Good or Ok. ")
    state = fields.Selection([('inspect', 'Inspect'),
                              ('inprogress', 'In Progress'),
                              ('done', 'Done'),
                              ('cancel', 'Cancelled')], 'State',
                             states={'confirm': [('readonly', True)]},
                             index=True, required=True, readonly=True,
                             default='inspect')

    @api.multi
    def room_inspect(self):
        self.write({'state': 'inspect'})

    @api.multi
    def room_inprogress(self):
        self.write({'state': 'inprogress'})

    @api.multi
    def room_done(self):
        self.write({'state': 'done'})

    @api.multi
    def room_cancel(self):
        self.write({'state': 'cancel'})

    @api.model
    def housekeeping_cron_on_daily_use(self):
        activity_plan_obj = self.env['hotel.housekeeping.activity.plan'].search(
            [('activity_plan', '=', 'ondayuse')])
        for activity in activity_plan_obj:
            service_ids = []
            for service in activity.activity_line_ids:
                if service:
                    service_ids.append([0, 0, {'activity_name': service.activity_id.id,
                                               'today_date': fields.Date.context_today(self),
                                               'state': ''}])
            vals = {'name': activity.name,
                    'current_date': fields.Date.context_today(self),
                    'clean_type': 'daily',
                    'inspector_id': activity.user_id.id,
                    'inspect_date_time': datetime.today(),
                    'state': 'inspect',
                    'activity_line_ids': service_ids}
            self.create(vals)
