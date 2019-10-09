# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Extra Bed Charges',
    'summary': 'Manage Extra bad charges',
    'description': '''This module is for the charge of extra bed. ''',
    'version': '12.0.1.0.0',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'category': 'Generic Modules/Hotel Management',
    'license': 'AGPL-3',
    'depends': ['hotel_reservation'],
    'data': [
        'data/hotel_data.xml',
        'views/res_company.xml'
    ],
    'demo': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
