# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Pos Options Bar',
    'version': '12.0.1.0.1',
    'category': 'Point Of Sale',
    'sequence': 6,
    'summary': 'Add Option Bar in footer',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'maintainer': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'https://www.serpentcs.com',
    'data': [
            'security/ir.model.access.csv',
            'view/templates.xml'],
    'depends': ['point_of_sale'],
    'qweb': ['static/src/xml/pos_options.xml'],
    'images': ['static/description/pos_option_bar.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'price': 29,
    'currency': 'EUR',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
