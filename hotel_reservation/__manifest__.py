# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Hotel Reservation Management',
    'version': '12.0.1.0.0',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'category': 'Generic Modules/Hotel Reservation',
    'summary' : 'Manages Guest Reservation',
    'license': 'AGPL-3',
    'depends': ['hotel', 'stock', 'mail'],
    'demo': ['data/hotel_reservation_data.xml'],
    'data': [
        'security/hotel_reservation_security.xml',
        'security/ir.model.access.csv',
        'report/report_view.xml',
        'data/booking_reminder_scheduler.xml',
        'data/hotel_reservation_sequence.xml',
        'wizard/reservation_cancel_wizard_view.xml',
        'wizard/folio_room_allocation_wizard.xml',
        'wizard/hotel_reservation_report_wizard_view.xml',
        'report/reservation_receipt_template.xml',
        'report/reservation_checkin_template.xml',
        'report/reservation_checkout_template.xml',
        'report/reservation_room_template.xml',
        'report/reservation_max_room_template.xml',
        'views/reservation_cancellation_view.xml',
        'views/email_temp_view.xml',
        'views/res_company_view.xml',
        'views/hotel_reservation_view.xml',
    ],
    'installable': True,
}
