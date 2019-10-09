# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Housekeeping Management',
    'version': '12.0.1.0.0',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'http://www.serpentcs.com',
    'license': 'AGPL-3',
    'category': 'Generic Modules/Hotel Housekeeping',
    'depends': ['hotel', 'hr', 'hotel_reservation'],
    'demo': ['data/hotel_housekeeping_data.xml', ],
    'data': [
        'data/housekeeping_cron_job.xml',
        'security/ir.model.access.csv',
        # 'report/hotel_housekeeping_report.xml',
        # 'report/activity_detail.xml',
        # 'wizard/hotel_housekeeping_wizard.xml',
        'views/hotel_housekeeping_view.xml',
        'views/hotel_housekeeper_view.xml'
    ],
    'installable': True,
}
