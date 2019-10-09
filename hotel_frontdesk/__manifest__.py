# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Management Frontdesk',
    'version': '12.0.1.0.0',
    'description': '''This module is for the HMS Front Desk. ''',
    'author': '''Serpent Consulting Services Pvt. Ltd.''',
    'website': 'http://www.serpentcs.com',
    'category': 'Hotel Management',
    'license': "AGPL-3",
    'complexity': 'easy',
    'Summary': 'A Module For Hotel Management Front Desk',
    'depends': [
        'hotel', 'web',
        'hotel_reservation',
        'hotel_room_availability',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/template_view.xml',
        'views/frontdesk_view.xml',
    ],
    'qweb': [
        "static/src/xml/hotel_frontdesk.xml",
    ],
    'installable': True,
    'application': True
}
