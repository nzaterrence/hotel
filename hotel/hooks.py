# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    
    env = api.Environment(cr, SUPERUSER_ID, {})

    ir_model_data_obj = env['ir.model.data']
    extra_room_id = ir_model_data_obj.xmlid_to_res_id(
                    'hotel.hotel_extra_room_charge_site_seen')
    cr.execute("""
                UPDATE res_company SET extra_room_charge_id = %s""",
                (extra_room_id,))
    cr.commit()
