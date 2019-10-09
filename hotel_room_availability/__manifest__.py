# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Room Availability and Rate Plan',
    'summary': 'Manage Hotel available room',
    'version': '12.0.1.0.0',
    'description': '''This module helps Hotel to manage  available rooms''',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'category': 'Generic Modules/Hotel Management',
    'license': 'AGPL-3',
    'depends': ['hotel', 'hotel_reservation'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'wizard/update_available_room_view.xml',
        'wizard/update_room_pricelist_view.xml',
        'views/hotel_room_availability_view.xml',
        'views/hotel_room_pricelist_view.xml',
    ],
    'demo': [],
    'css': [],
    'qweb': [
        'static/src/xml/room_availability.xml',
        'static/src/xml/room_pricelist.xml',
    ],
    'installable': True,
}
