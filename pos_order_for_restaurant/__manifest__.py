# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Takeaway/Delivery Order For Restaurant',
    'version': '12.0.1.0.3',
    'category': 'Point Of Sale',
    'sequence': 6,
    'summary': 'Add Take Away and Delivery option for POS Orders.',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'maintainer': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'https://www.serpentcs.com',
    'description': """This module allow us to take parcel
        and delivery order and Also provide
        Table management functionality.
    """,
    'data': ['security/pos_order_for_restaurant_security.xml',
             'security/ir.model.access.csv',
             'view/templates.xml',
             'view/pos_order_for_restaurant_view.xml',
             ],
    'demo': [
        'view/pos_order_restaurant_demo.xml',
    ],
    'depends': ['pos_restaurant', 'pos_kot_receipt'],
    'qweb': ['static/src/xml/pos_order_for_restaurant.xml'],
    'images': ['static/description/pos_order_for_restaurant.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'price': 49,
    'currency': 'EUR',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
