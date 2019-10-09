# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    
    env = api.Environment(cr, SUPERUSER_ID, {})

    ir_model_data_obj = env['ir.model.data']
    extra_bed_id = ir_model_data_obj.xmlid_to_res_id('hotel_extra_bed_charge.hotel_extra_bed_charge')
    cr.execute("""
                UPDATE res_company SET extra_bed_charge_id = %s""",
                (extra_bed_id,))
    cr.commit()
