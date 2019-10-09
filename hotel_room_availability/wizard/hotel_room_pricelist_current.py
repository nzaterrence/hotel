# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HotelRoomPricelistSheetOpen(models.TransientModel):
    _name = 'hotel.room.pricelist.sheet.open'
    _description = 'hotel.room.pricelist.sheet.open'

    @api.model
    def open_room_pricelist_sheet(self):
        view_type = 'form,tree'

        sheets = self.env['room.pricelist'].search([
            ('company_id', '=', self.env.user.company_id.id),
            ('state', '=', 'draft'),
            ('date_from', '<=',
             fields.Date.today()),
            ('date_to', '>=', fields.Date.today())])
        rooms = self.env['hotel.room'].search([
            ('company_id', '=', self.env.user.company_id.id),
            ('status', '=', 'available')])
        ctx = self._context.copy()
        ctx.update({'default_rooms_ids': [(6, 0, rooms.ids)]})
        domain = []
        if len(sheets) > 1:
            view_type = 'tree,form'
            domain = "[('id', 'in', " + str(sheets.ids) + \
                "),('company_id', '='," + \
                str(self.env.user.company_id.id) + ")]"
            sheets.write({'rooms_ids': [(6, 0, rooms.ids)]})
        else:
            domain = "[('company_id', '=', " + \
                str(self.env.user.company_id.id) + ")]"
        value = {
            'domain': domain,
            'name': _('Open Room Pricelist Sheet'),
            'view_type': 'form',
            'view_mode': view_type,
            'res_model': 'room.pricelist',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': ctx
        }
        if len(sheets) == 1:
            sheets.write({'rooms_ids': [(6, 0, rooms.ids)]})
            value['res_id'] = sheets.id
        return value
