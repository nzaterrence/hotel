# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Room Quick Booking',
    'summary': 'Quick Hotel room Booking',
    'version': '12.0.1.0.0',
    'description': '''This module allows you to book hotel rooms faster.''',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'category': 'Generic Modules/Hotel Management',
    'license': 'AGPL-3',
    'depends': ['hotel_room_availability'],
    'data': [
        'security/ir.model.access.csv',
        'views/views_quick_reservation.xml',
        'views/template_view.xml',
    ],
    'demo': [],
    # 'css': [],
    # 'qweb': ['static/src/xml/room_availability.xml',
    #          'static/src/xml/room_pricelist.xml', ],
    'installable': True,
    'auto_install': False,
}
