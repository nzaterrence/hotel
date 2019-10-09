# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Management',
    'summary': 'Manage Hotel room and booking management system',
    'version': '12.0.1.0.0',
    'description': '''This module helps customer to book their room into the
    the Hotel''',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'category': 'Generic Modules/Hotel Management',
    'license': 'AGPL-3',
    'depends': ['sale_stock'],
    'data': [
        'security/hotel_security.xml',
        'security/ir.model.access.csv',
        'data/hotel_sequence.xml',
        'data/hotel_data.xml',
#        'data/cron_job.xml',
        'wizard/change_room_qty_views.xml',
        'report/hotel_folio_report_template.xml',
        'report/currency_exchange_report_template.xml',
        'report/report_view.xml',
        'views/res_company.xml',
        'views/hotel_view.xml',
        'wizard/hotel_folio_report_wizard_view.xml',
        'views/room_move.xml',
        'views/res_partner_view.xml'
    ],
    'demo': ['data/hotel_demo_data.xml'],
    'css': ['static/src/css/room_kanban.css'],
    'installable': True,
    'application': True,
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {
        'python': ['forex_python'],
    },
}
