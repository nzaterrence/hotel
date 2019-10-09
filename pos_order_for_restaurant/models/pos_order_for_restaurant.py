# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosConfig(models.Model):
    """
    Summary.

    Attributes:
        display_delivery (Boolean)
        display_parcel (Boolean)
    """

    _inherit = 'pos.config'

    display_delivery = fields.Boolean(
        "Display Delivery Button",
        help="""If Display Delivery Button is true
            than pos shows a delivery button.""",
        default=True)
    display_parcel = fields.Boolean(
        "Display Parcel Button",
        help="""If Display Parcel Button is true than
            pos shows a parcel button.""",
        default=True)


class PosOrder(models.Model):
    """
    Summary.

    Attributes:
        confirm_order (Boolean)
        driver_name (Many2one)
        is_synch_order (Boolean)
        order_status (Char)
        parcel (Char)
        pflag (Boolean)
        phone (Char)
        reserved_table_ids (One2many)
        split_order (Boolean)
        table_name (Char)
    """

    _inherit = "pos.order"

    @api.model
    def get_draft_state_order(self):
        """
        Summary.

        Returns:
            TYPE: Boolean
        """
        table_obj = self.env["restaurant.table"]
        draft_order_ids = self.search([
            ('state', '=', 'draft'),
            ('confirm_order', '=', True),
            ('is_synch_order', '!=', True)])
        if draft_order_ids:
            orders = []
            for b_order in draft_order_ids:
                driver_name = False
                if b_order.driver_name:
                    driver_name = b_order.driver_name.id
                order = {
                    'id': b_order.id,
                    'name': b_order.name,
                    'pos_reference': b_order.pos_reference,
                    'pricelist_id': b_order.pricelist_id.id,
                    'pricelist_name': b_order.pricelist_id.name,
                    'pricelist_currency_id':
                    b_order.pricelist_id.currency_id.id,
                    'user_id': b_order.user_id.id,
                    'partner_id': b_order.partner_id.name or False,
                    'partner_ids': b_order.partner_id.id or False,
                    'pflag': b_order.pflag,
                    'parcel': b_order.parcel,
                    'phone': b_order.phone,
                    'sequence_number': b_order.sequence_number,
                    'driver_name': driver_name,
                }
                table_ids = []
                table_name = ''
                table_data = []
                reserved_seat = ''
                table_ids = []
                for reserve in b_order.reserved_table_ids:
                    table = table_obj.browse(reserve.table_id.id)
                    table_ids.append(table.id)
                    reserved_seat += str(table.id) + "/" + \
                        str(reserve.reserver_seat) + "_"
                    table_name += table.name + "/" + \
                        str(reserve.reserver_seat) + ' '
                    table_data.append(
                        {
                            "reserver_seat": reserve.reserver_seat,
                            'table_id': table.id
                        })
                if b_order.reserved_table_ids:
                    order.update({'creation_date_id': table_ids})
                    order.update({'table_ids': table_ids})
                    order.update({'order_name': table_name})
                    order.update({'reserved_seat': reserved_seat,
                                  'table_data': table_data})
                if b_order.pflag:
                    order.update({'creation_date_id': b_order.parcel})
                    order.update({'table_ids': False})
                    order.update({'order_name': b_order.parcel})
                    order.update({'reserved_seat': False, 'table_data': False})
                if not b_order.pflag and not b_order.reserved_table_ids:
                    order.update(
                        {'creation_date_id': b_order.partner_id.name or False})
                    order.update({'table_ids': False})
                    order.update(
                        {'order_name': b_order.partner_id.name or False})
                    order.update({'reserved_seat': False, 'table_data': False})
                lines = []
                for line in b_order.lines:
                    lines.append({'id': line.id,
                                  'product_id': line.product_id.id,
                                  'qty': line.qty,
                                  'discount': line.discount,
                                  'price_unit': line.price_unit,
                                  'flag': True,
                                  'name': line.name,
                                  #                                  'sequence_number':line.sequence_number,
                                  })
                order.update({'lines': lines})
                orders.append(order)
            return orders
        return False

    @api.depends('reserved_table_ids')
    def get_table_name(self):
        """
        Summary.

        Returns:
            TYPE: Dictionary
        """
        res = {}
        for order in self:
            table_name = ''
            try:
                for table in order.reserved_table_ids:
                    if table.table_id:
                        table_name += table.table_id.name + " "
            except AttributeError:
                table_name = False
            res[order.id] = table_name
            self.table_name = table_name
        return res

    pflag = fields.Boolean('Flag')
    parcel = fields.Char("Parcel Order", size=32)
    driver_name = fields.Many2one('res.users', "Delivery Boy")
    phone = fields.Char("Customer Phone Number", size=128)
    reserved_table_ids = fields.One2many(
        "table.reserverd", "order_id", "Reserved Table")
    split_order = fields.Boolean('split')
    table_name = fields.Char(compute='get_table_name',
                             string='Table Name', store=True)
    order_status = fields.Char('Order Status', default='not confirm')
    confirm_order = fields.Boolean('Confirm Order')
    is_synch_order = fields.Boolean('Is Synch Order?')

    @api.multi
    def action_pos_order_paid(self):
        """
        Summary.

        Returns:
            TYPE: Object
        """
        res = super(PosOrder, self).action_pos_order_paid()
        table_obj = self.env["restaurant.table"]
        for order in self:
            if not order.split_order and order.order_status != 'confirm' and not order.folio_id:
                for res_table in order.reserved_table_ids:
                    reserver_seat = res_table.reserver_seat
                    available_capacities =\
                        res_table.table_id.available_capacities
                    if (available_capacities -
                            reserver_seat) == 0:
                        table_obj.browse(res_table.table_id.id).write(
                            {
                                'state': 'available',
                                'available_capacities':
                                reserver_seat - available_capacities})
                    else:
                        if (available_capacities - reserver_seat) > 0:
                            table_obj.browse(res_table.table_id.id).write(
                                {
                                    'state': 'available',
                                    'available_capacities':
                                    available_capacities - reserver_seat
                                })
        return res

    @api.model
    def _order_fields(self, ui_order):
        """
        Summary.

        Args:
            ui_order (TYPE): Dictionary

        Returns:
            TYPE: Dictionary
        """
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['driver_name'] = ui_order.get('driver_name', False)
        order_fields['phone'] = ui_order.get('phone', False)
        order_fields['pflag'] = ui_order.get('pflag', False)
        order_fields['parcel'] = ui_order.get('parcel', False)
        order_fields['split_order'] = ui_order.get('split_order', False)
        order_fields['confirm_order'] = ui_order.get('confirm_order', False)
        if ui_order.get('offline_order', False) and \
                ui_order.get('offline_confirm_order', False):
            order_fields['order_status'] = 'confirm'
        table_data = ui_order.get("table_data")
        reserve_table_ids = []
        if ui_order.get('id', False) and table_data:
            self.browse(ui_order.get('id')).write(
                {'reserved_table_ids': [(5, 0)]})
            for reserve in table_data:
                reserve.update({"order_id": ui_order.get('id')})
                reserv_id = self.env["table.reserverd"].create(reserve).id
                reserve_table_ids.append((4, reserv_id))
                if ui_order.get('offline_delete_order', False):
                    table_id = reserve.get('table_id')
                    if table_id:
                        if ui_order.get('id', False):
                            self.close_order([ui_order.get('id', False)])
            order_fields['reserved_table_ids'] = reserve_table_ids
        if not ui_order.get('id', False) and table_data:
            for reserve in table_data:
                table_id = reserve.get('table_id')
                reserv_id = self.env["table.reserverd"].create(reserve).id
                reserve_table_ids.append((4, reserv_id))
            order_fields['reserved_table_ids'] = reserve_table_ids
            if ui_order.get('offline_delete_order', False):
                self.env['restaurant.table'].remove_table_order(table_data)
        return order_fields

    @api.model
    def check_group_pos_delivery_boy(self, puser):
        """
        Summary.

        Args:
            puser (TYPE): Integer

        Returns:
            TYPE: Boolean
        """
        mod_obj = self.env['ir.model.data']
        grp_result = mod_obj.get_object(
            'pos_order_for_restaurant', 'group_pos_delivery_boy')
        user_add = [user.id for user in grp_result.users]
        for user in mod_obj.get_object(
                'point_of_sale', 'group_pos_manager').users:
            if puser in user_add:
                return True
        return False

    @api.model
    def close_order(self, order_id):
        """
        Summary.

        Args:
            order_id (Integer)

        Returns:
            TYPE: Boolean
        """
        ir_module_module_object = self.env['ir.module.module']
        is_kitchen_screen = ir_module_module_object.search(
            [('state', '=', 'installed'), ('name', '=', 'pos_kot_receipt')])
        line_ids = []
        if is_kitchen_screen:
            for order in self.browse(order_id):
                for line in order.lines:
                    if line.order_line_state_id.id == 3 or\
                            line.order_line_state_id.id != 1:
                        line_ids.append(line.id)
            if line_ids:
                return False
        if order_id:
            if is_kitchen_screen:
                for order in self.browse(order_id):
                    for res_table in order.reserved_table_ids:
                        reserver_seat = res_table.reserver_seat
                        available_capacities = \
                            res_table.table_id.available_capacities
                        if (available_capacities - reserver_seat) == 0:
                            self.env["restaurant.table"].browse(
                                res_table.table_id.id).write(
                                {
                                    'state': 'available',
                                    'available_capacities':
                                    available_capacities - reserver_seat})
                        else:
                            if (available_capacities - reserver_seat) > 0:
                                self.env["restaurant.table"].browse(
                                    res_table.table_id.id).write(
                                    {
                                        'state': 'available',
                                        'available_capacities':
                                        available_capacities - reserver_seat
                                    })
            order_id = order_id[0]
            line_ids = [line.id for line in self.browse(order_id).lines]
            self.env["pos.order.line"].browse(
                line_ids).write({"order_id": order_id})
            self.browse(order_id).action_pos_order_cancel()
        return True

    @api.model
    def reassign_table(self, booked_table):
        """
        Summary.

        Args:
            booked_table : String

        Returns:
            TYPE: Boolean
        """
        table_obj = self.env['restaurant.table']
        if booked_table and booked_table.split('_'):
            for booked in booked_table.split('_'):
                if booked:
                    table_id = int(booked.split('/')[0])
                    qty = int(booked.split('/')[1])
                    table_data = table_obj.browse(table_id)
                    table_data.write(
                        {
                            'available_capacities':
                            table_data.available_capacities - int(qty),
                            'state': 'available'
                        })
        return True

    @api.model
    def remove_order(self, second_order_id=False):
        """
        Summary.

        Args:
            second_order_id (bool, optional)

        Returns:
            TYPE: Boolean
        """
        if self.sudo().ids and second_order_id:
            line_ids = [line.id for line in self.browse(second_order_id).lines]
            self.env["pos.order.line"].browse(
                line_ids).write({"order_id": ids[0]})
            self.browse(second_order_id).action_pos_order_cancel()
        if not ids and second_order_id:
            self.browse(second_order_id).action_pos_order_cancel()
        return True


class ResPartner(models.Model):

    """
    Summary.

    """

    _inherit = 'res.partner'

    @api.model
    def create_customer_from_pos(self, c_name, c_street, c_street2, c_city, c_zip, c_phone):
        """
        Summary.

        Args:
            c_name (TYPE): String
            c_street (TYPE): String
            c_street2 (TYPE): String
            c_city (TYPE): String
            c_zip (TYPE): String
            c_phone (TYPE): Integer

        Returns:
            TYPE: Integer
        """

        idclient = self.create({
            'name': c_name,
            'street': c_street or False,
            'street2': c_street2 or False,
            'city': c_city or False,
            'zip': c_zip or False,
            'phone': c_phone or False,
            'customer': True,
        })
        return idclient.id


class TableReserved(models.Model):
    """
    Summary.

    Attributes:
        order_id (TYPE): Many2one
        reserver_seat (TYPE): Integer
        table_id (TYPE): Many2one
    """

    _name = "table.reserverd"

    table_id = fields.Many2one("restaurant.table", "Table")
    reserver_seat = fields.Integer("Reserved Seat")
    order_id = fields.Many2one("pos.order", "POS Order")


class RestaurantTable(models.Model):
    """
    Summary.

    Attributes:
        available_capacities (TYPE): Integer
        capacities (TYPE): Integer
        state (TYPE): Selection
        users_ids (TYPE): Many2many
    """

    _inherit = 'restaurant.table'

    capacities = fields.Integer('Capacities')
    state = fields.Selection([
        ('reserved', 'Reserved'),
        ('available', 'Available')],
        'State',
        required=True,
        default='available')
    users_ids = fields.Many2many(
        'res.users', 'rel_table_master_users', 'table_id', 'user_id', 'User')
    available_capacities = fields.Integer(
        'Reserved Seat', readonly=True, default=0)

    @api.model
    def remove_table_order(self, table_ids):
        """
        summary.

        Args:
            table_ids (TYPE): Description
        Returns:
            TYPE: Description
        """
        for table_rec in table_ids:
            table = self.browse(table_rec['table_id'])
            if (int(table.available_capacities) - int(
                    table_rec['reserver_seat'])) == 0:
                table.write({
                    'state': 'available',
                    'available_capacities':
                    int(table.available_capacities) - int(
                        table_rec['reserver_seat'])})
            else:
                table.write({
                    'state': 'available',
                    'available_capacities':
                    int(table.available_capacities) - int(
                        table_rec['reserver_seat'])})
        return True

    @api.model
    def remove_delete_table_order(self, orders):
        """
        summary.

        Args:
            orders (TYPE): Dictionaery
        Returns:
            TYPE: Boolean
        """
        for order in orders:
            table_data = order.get('table_data')
            if table_data:
                self.remove_table_order(table_data)
        return True

    @api.model
    def update_offline_table_order(self, table_datas):
        """
        summary.

        Args:
            table_datas (TYPE): list
        Returns:
            TYPE: boolean
        """
        for table_data in table_datas:
            table = self.browse(int(table_data))
            if table and table.state == 'available':
                table_state = "available"
                final_available_capacities = table.available_capacities + \
                    int(table_datas[table_data])
                if table.capacities - final_available_capacities == 0:
                    table_state = "reserved"
                table.write({'state': table_state,
                             'available_capacities':
                             final_available_capacities})
        return True

    @api.model
    def create_from_ui(self, table):
        """
        summary.

        Args:
            table (TYPE): dictionary
        Returns:
            TYPE: integer
        """
        if table.get('floor_id'):
            table['floor_id'] = table['floor_id'][0]

        table_id = table.pop('id', False)
        if table_id:
            self.browse(table_id).write(table)
        else:
            table_id = self.create(table).id
        return table_id

    @api.model
    def get_waiter_list(self):
        """
        summary.

        Returns:
            TYPE: list
        """
        table_ids = self.search([])
        waiter_list = []
        final_list = []
        if table_ids:
            for table in self:
                for table_user in table.users_ids:
                    if table_user.id not in waiter_list:
                        waiter_list.append(table_user.id)
                        waiter_list_temp = {
                            'id': table_user.id, 'name': table_user.name}
                        final_list.append(waiter_list_temp)
            return final_list

    @api.multi
    def action_available(self):
        """
        summary.

        Returns:
            TYPE: Boolean
        Raises:
            UserError: Whene table are full
        """
        if self.id:
            reserve_table_obj = self.env["table.reserverd"]
            for table in self:
                reserve_ids = reserve_table_obj.search([
                    ('table_id', '=', table.id),
                    ("order_id.state", "=", "draft")
                ])
                if reserve_ids:
                    raise UserError(_("Table is not empty!"))
                else:
                    self.write(
                        {'state': 'available', 'available_capacities': 0})
        return True
