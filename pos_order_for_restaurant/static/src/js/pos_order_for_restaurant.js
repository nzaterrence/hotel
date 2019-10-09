odoo.define("pos_order_for_restaurant.pos_order_for_restaurant", function(require) {

    var core = require('web.core');
    var data = require('web.data');
    var chrome = require('point_of_sale.chrome');
    var floor = require('pos_restaurant.floors');
    var keyboard = require('point_of_sale.keyboard');
    var gui = require('point_of_sale.gui');
    var models = require('point_of_sale.models');
    var pop_up = require('point_of_sale.popups');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var screens = require('point_of_sale.screens');
    var resturant = require('pos_restaurant.floors');
    var PosDB = require('point_of_sale.DB');
    var session = require('web.session');
    var rpc = require('web.rpc');
    var is_admin = false;

    var QWeb = core.qweb;
    var _t = core._t;
    var is_pos_quick_load_data = _.contains(session.module_list, 'pos_quick_load_data');
    var restaurant_table_dataset = new data.DataSetSearch(self, 'restaurant.table', {}, []);

    var NumberPopupWidget;
    _.each(gui.Gui.prototype.popup_classes, function(popup_class) {
        if (popup_class.name == "number") {
            NumberPopupWidget = popup_class;
        }
    });

    for (var i = 0; i < models.PosModel.prototype.models.length; i++) {
        if (models.PosModel.prototype.models[i].model == 'restaurant.table') {
            models.PosModel.prototype.models.splice(i, 1);
        }
    }

    models.PosModel.prototype.models.push({
        model: 'res.users',
        fields: ['name', 'company_id'],
        ids: function(self) {
            return [session.uid];
        },
        loaded: function(self, users) {
            self.user = users[0];
        },
    }, {
        model: 'restaurant.floor',
        fields: ['name', 'background_color', 'table_ids', 'sequence'],
        domain: null,
        loaded: function(self, floors) {
            self.floors = floors;
            self.floors_by_id = {};
            for (var i = 0; i < floors.length; i++) {
                floors[i].tables = [];
                self.floors_by_id[floors[i].id] = floors[i];
            }
            // Make sure they display in the correct order
            self.floors = self.floors.sort(function(a, b) {
                return a.sequence - b.sequence;
            });
            // Ignore floorplan features if no floor specified.
            self.config.iface_floorplan = !!self.floors.length;
        },
    }, {
        model: 'restaurant.table',
        fields: ['name', 'users_ids', 'capacities', 'state', 'available_capacities', 'floor_id', 'width', 'height', 'position_h', 'position_v', 'shape', 'floor_id', 'color', 'seats'],
        loaded: function(self, tables_data) {
            var tables = [];
            self.table_details = []
            self.tables_by_id = {};
            for (var i = 0; i < tables_data.length; i++) {
                self.tables_by_id[tables_data[i].id] = tables[i];
                var floor = self.floors_by_id[tables_data[i].floor_id[0]];
                if (floor) {
                    floor.tables.push(tables_data[i]);
                    tables_data[i].floor = floor;
                }
            }
            _.each(tables_data, function(item) {
                for (us in item.users_ids) {
                    if (item.users_ids[us] == self.session.uid) {
                        self.table_details.push(item)
                        tables.push([item.id, item.name, item.capacities, item.capacities, item.available_capacities]);
                    }
                }
            });
            self.table_list = tables;
            self.temp_table_list = tables;
            self.all_table = tables_data;
        },
    }, {
        model: 'res.partner',
        //        fields: ['name','street','city','state_id','country_id','vat','phone','zip','mobile','email','barcode','write_date'],
        fields: ['name', 'street', 'city', 'state_id', 'country_id', 'vat', 'phone', 'zip', 'parent_id', 'mobile', 'email', 'barcode', 'write_date', 'property_account_position_id'],
        domain: [
            ['customer', '=', true]
        ],
        loaded: function(self, partners) {
            self.partners = partners;
            self.partner_list = [];
            self.partner_dict = {};
            _.each(self.partners, function(value) {
                self.partner_list.push(value);
                self.partner_dict[parseInt(value.id)] = value;
            });
        },
    }, {
        model: 'res.users',
        fields: ['name', 'pos_security_pin', 'groups_id', 'barcode', 'company_id'],
        domain: null,
        loaded: function(self, user_list) {
            self.delivery_boy = [];
            _.each(user_list, function(user) {
                // pos_order_model.call("check_group_pos_delivery_boy",[user.id])
                rpc.query({
                        model: 'pos.order',
                        method: 'check_group_pos_delivery_boy',
                        args: [user.id],
                    })
                    .then(function(callback) {
                        if (callback) {
                            self.delivery_boy.push(user);
                        }
                    });
            });
            self.user_list = user_list;
        },
    });
    var _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        initialize: function(session, attributes) {
            this.session = session;
            this.pos_session = session;
            return _super_posmodel.initialize.call(this, session, attributes);
        },
        load_new_partners: function() {
            if (is_pos_quick_load_data) {
                return _super_posmodel.load_new_partners.call(this);
                // return this._super()
            }
            var self = this;
            var def = new $.Deferred();
            var fields = _.find(this.models, function(model) {
                return model.model === 'res.partner';
            }).fields;
            var domain = [
                ['customer', '=', true],
                ['write_date', '>', this.db.get_partner_write_date()]
            ];
            rpc.query({
                    model: 'res.partner',
                    method: 'search_read',
                    args: [domain, fields],
                }, {
                    timeout: 3000,
                    shadow: true,
                })
                .then(function(partners) {
                    if (self.db.add_partners(partners)) { // check if the partners we got were real updates
                        _.each(partners, function(partner) {
                            self.partner_list.push(partner);

                            self.partner_dict[parseInt(partner.id)] = partner;
                        });
                        def.resolve();
                    } else {
                        def.reject();
                    }
                }, function(type, err) {
                    def.reject();
                });
            return def;
        },
        delete_current_order: function() {
            var order = this.get_order();
            if (order) {
                var self = this;
                if (order.attributes.id) {

                    // pos_order_model.call("close_order", [])
                    rpc.query({
                        model: 'pos.order',
                        method: 'close_order',
                        args: [
                            [order.attributes.id]
                        ],
                    }).then(function(callback) {
                        if (callback) {
                            order.destroy({
                                'reason': 'abandon'
                            });
                        } else if (!callback) {
                            self.gui.show_popup('alert', {
                                title: _t('Warning !'),
                                warning_icon: true,
                                body: _t('Can not remove order.'),
                            });
                        }
                    }, function(err, event) {
                        event.preventDefault();
                        var table_details = order.attributes.table_data;
                        order.offline_delete_order = true;
                        if (table_details != undefined) {
                            self.push_order(order)
                            self.update_table_details(table_details);
                        }
                        order.destroy({
                            'reason': 'abandon'
                        });
                    });
                } else {
                    var self = this;
                    var table_details = order.attributes.table_data;
                    if (table_details != undefined) {
                        if (!order.attributes.split_order) {
                            // restaurant_table_model.call("remove_table_order", [table_details])
                            rpc.query({
                                model: 'restaurant.table',
                                method: 'remove_table_order',
                                args: [table_details]
                            }).then(function(callback) {
                                order.destroy({
                                    'reason': 'abandon'
                                });
                            }, function(err, event) {
                                event.preventDefault();
                                if (!order.attributes.offline_order) {
                                    self.db.add_table_order(order);
                                }
                                order.destroy({
                                    'reason': 'abandon'
                                });
                            });
                            self.update_table_details(table_details);
                        } else {
                            order.destroy({
                                'reason': 'abandon'
                            });
                        }
                    } else {
                        order.destroy({
                            'reason': 'abandon'
                        });
                    }
                }
            }
        },
        update_table_details: function(data) {
            var self = this;
            if (data != undefined && data[0] != undefined && data[0].table_id) {
                var table_id = data[0].table_id
                var reserver_seat = parseInt(data[0].reserver_seat)
                for (var i = 0; i < self.table_details.length; i++) {
                    if (self.table_details[i].id === table_id) {
                        self.table_details[i].available_capacities = self.table_details[i].available_capacities - reserver_seat
                        self.table_details[i].state = 'available'
                        break;
                    }
                }
            }
        },
        _flush_offline_order: function(orders, options) {
            if (!orders || !orders.length) {
                var result = $.Deferred();
                result.resolve([]);
                return result;
            }

            options = options || {};

            var self = this;
            var timeout = typeof options.timeout === 'number' ? options.timeout : 7500 * orders.length;

            // Keep the order ids that are about to be sent to the
            // backend. In between create_from_ui and the success callback
            // new orders may have been added to it.
            var order_ids_to_sync = _.pluck(orders, 'id');

            // we try to send the order. shadow prevents a spinner if it takes too long. (unless we are sending an invoice,
            // then we want to notify the user that we are waiting on something )
            // var posOrderModel = new Model('pos.order');
            return rpc.query({
                    model: 'pos.order',
                    method: 'create_from_ui',
                    args: [_.map(orders, function(order) {
                        order.to_invoice = options.to_invoice || false;
                        return order;
                    })],
                },
                undefined, {
                    shadow: !options.to_invoice,
                    timeout: undefined
                }).then(function(server_ids) {
                _.each(order_ids_to_sync, function(order_id) {
                    self.db.remove_order(order_id);
                });
                self.set('failed', false);
                $.unblockUI();
                return server_ids;
            }).fail(function(error, event) {
                $.unblockUI();
                if (error.code === 200) { // Business Logic Error, not a connection problem
                    //if warning do not need to display traceback!!
                    if (error.data.exception_type == 'warning') {
                        delete error.data.debug;
                    }

                    // Hide error if already shown before ... 
                    if ((!self.get('failed') || options.show_error) && !options.to_invoice) {
                        self.gui.show_popup('error-traceback', {
                            'title': error.data.message,
                            'body': error.data.debug
                        });
                    }
                    self.set('failed', error)
                }
                // prevent an error popup creation by the rpc failure
                // we want the failure to be silent as we send the orders in the background
                event.preventDefault();
                console.error('Failed to send orders:', orders);
            });
        },
        set_table: function(table) {
            if (!table) { // no table ? go back to the floor plan, see ScreenSelector
                this.set_order(null);
            } else {
                this.table = table;
                var self = this;
                var orders = this.get_order_list();
                var selection_name = '';
                var reserved_seat = '';
                var selection_id = [];
                var select_tables = [];
                if (table.state == 'reserved') {
                    _.each(orders, function(order) {
                        if (order.attributes.table_ids != undefined && order.attributes.table_ids[0] == table.id) {
                            self.set({
                                'selectedOrder': order
                            });
                        }
                    })
                }
                if (table.state == 'available') {
                    var table_id = parseInt(table.id);
                    selection_id.push(table_id);
                    selection_name += ' ' + table.name + "/" + $("#" + table.id + '_sit_reserv').val();
                    reserved_seat += table.id + "/" + $("#" + table.id + '_sit_reserv').val() + '_';
                    actual_reserved_seat = parseInt($("#" + table.id + '_sit_reserv').val());
                    select_tables.push({
                        reserver_seat: $("#" + table.id + '_sit_reserv').val(),
                        table_id: table_id
                    });
                    available_seat = table.seating_capacities;
                    var table_vals = {
                        'available_capacities': actual_reserved_seat + table.available_capacities
                    };
                    if ((actual_reserved_seat > available_seat) || (available_seat == 0)) {
                        self.gui.show_popup('alert', {
                            title: _t('Warning !'),
                            warning_icon: true,
                            body: _t("Table capacity is ") + available_seat + _t(" person you cannot enter more then ") + available_seat + _t(" or less than 1. "),
                        });
                        return false;
                    }
                    if (actual_reserved_seat <= 0 || isNaN(actual_reserved_seat)) {
                        self.gui.show_popup('alert', {
                            title: _t('Warning !'),
                            warning_icon: true,
                            body: _t("You must be add some person in this table"),
                        });
                        return false;
                    }
                    var order = new models.Order({}, {
                        pos: this
                    });
                    if (actual_reserved_seat == available_seat) {
                        table_vals['state'] = 'reserved';
                        order.set('creationDate', selection_name);
                        order.set('table', table);
                        order.set('creationDateId', selection_id);
                        order.set('table_ids', selection_id);
                        order.set('table_data', select_tables);
                        order.set('reserved_seat', reserved_seat);
                        if (table.client_detalis != null) {
                            order.set_client(self.db.get_partner_by_id(table.client_detalis.id));
                        }
                        self.get('orders').add(order);
                        self.set_order(order);
                        // restaurant_table_model.call("write",[[table_id],table_vals]);
                        rpc.query({
                            model: 'restaurant.table',
                            method: 'write',
                            args: [
                                [table_id], table_vals
                            ],
                        })
                        for (var i = 0; i < self.table_details.length; i++) {
                            if (self.table_details[i].id === table_id) {
                                self.table_details[i].available_capacities = table_vals.available_capacities
                                self.table_details[i].state = 'reserved';
                                break;
                            }
                        }
                    } else if (actual_reserved_seat != available_seat) {
                        order.set('creationDate', selection_name);
                        order.set('table', table);
                        order.set('creationDateId', selection_id);
                        order.set('table_ids', selection_id);
                        order.set('table_data', select_tables);
                        order.set('reserved_seat', reserved_seat);
                        if (table.client_detalis != null) {
                            order.set_client(self.db.get_partner_by_id(table.client_detalis.id));
                        }
                        self.get('orders').add(order);
                        self.set_order(order);
                        // restaurant_table_model.call("write",[[table_id],table_vals]);
                        rpc.query({
                            model: 'restaurant.table',
                            method: 'write',
                            args: [
                                [table_id], table_vals
                            ],
                        })
                        for (var i = 0; i < self.table_details.length; i++) {
                            if (self.table_details[i].id === table_id) {
                                self.table_details[i].available_capacities = table_vals.available_capacities
                                break;
                            }
                        }
                        for (var i = 0; i < self.table_details.length; i++) {
                            if (self.table_details[i].id === table_id) {
                                self.table_details[i].available_capacities = table_vals.available_capacities
                                break;
                            }
                        }
                    }
                }
            }
        },
        //creates a new empty order and sets it as the current order
        // add_new_order: function() {
        //     var order = new models.Order({}, {
        //         pos: this
        //     });
        //     this.get('orders').add(order);
        //     this.set('selectedOrder', order);
        //     return order;
        // },
        initialize_table_details: function(floor, re_assign) {
            var self = this;
            self.booked_table = [];
            self.empty_table = [];
            return restaurant_table_dataset.read_slice(['name', 'state', 'users_ids', 'capacities', 'available_capacities', 'floor_id', 'width', 'height', 'position_h', 'position_v', 'shape', 'floor_id', 'color', ], {
                'domain': [
                    ['floor_id', '!=', false]
                ]
            }).then(function(table_records) {
                self.table_details = [];
                _.each(table_records, function(value) {
                    for (us in value.users_ids) {
                        if (value.users_ids[us] == self.session.uid) {
                            self.table_details.push(value)
                            if ((value.capacities - value.available_capacities) < value.capacities) {
                                self.empty_table.push([value.id, value.name, value.capacities, value.capacities - value.available_capacities, value.available_capacities, true, value.floor_id[0], value.state]);
                            } else {
                                self.empty_table.push([value.id, value.name, value.capacities, value.capacities - value.available_capacities, value.available_capacities, false, value.floor_id[0], value.state]);
                            }
                        }
                    }
                });
                if ($('.orders')) {
                    _.each($('.orders')[0].childNodes, function(value) {
                        if ($(value).attr('data')) {
                            self.booked_table.push([$(value).attr("name"),
                                $(value).attr("name").trim(),
                                $(value).attr("data"),
                                $(value).attr('id'),
                                $(value)[0].id
                            ]);
                        }
                    });
                }
                if (re_assign && self.empty_table.length == 0 && self.option_value == "re_assign_order") {
                    var warning_icon = true;
                    var message = _t("Table is not empty. Please wait!")
                    self.open_alert_dialog(message, warning_icon);
                }
                if (self.booked_table.length < 0 && self.option_value == "merge_order") {
                    var warning_icon = true;
                    var message = _t("There is no more table to merge!");
                    self.open_alert_dialog(message, warning_icon);
                    return false;
                }
                if (floor) {
                    self.gui.screen_instances.floors.renderElement();
                    self.gui.show_screen('floors');
                } else if (re_assign) {
                    self.re_assign = re_assign;
                    self.re_assign_table_content();
                }
            }, function(err, event) {
                event.preventDefault();
                if (re_assign) {
                    self.gui.show_popup('confirm', {
                        'title': _t('Offline Orders'),
                        'body': _t(['Check your internet connection and try again.']),
                        'confirm': function() {},
                    });
                }
            });
        },
        re_assign_table_content: function() {
            var self = this;
            $('.reassign_table_screen_content').html($(QWeb.render('select-table', {
                'table': self
            })));
            $('#table_list .input_seat').on('click', function(index) {
                $(this).closest('tr').find("input")[0].checked = !$(this).closest('tr').find("input")[0].checked;
                $(this).closest('tr').removeClass('reassign_order_color');
            });
            $('#table_list .field_boolean').on('click', function(index) {
                $(this).closest('tr').find("input")[0].checked = !$(this).closest('tr').find("input")[0].checked;
                $(this).closest('tr').removeClass('reassign_order_color');
            });
            $('#table_list tr').on('click', function() {
                if ($(this).find("input")[0].checked) {
                    $(this).find("input")[0].checked = false;
                    $(this).removeClass('reassign_order_color');
                } else {
                    $(this).find("input")[0].checked = true;
                    $(this).addClass('reassign_order_color');
                }
            });
            self.set_re_assign_table_screen_property();
        },
        set_re_assign_table_screen_property: function() {
            var self = this;
            $(".marge_table").hide();
            if (self.option_value == "merge_order") {
                $("#booked_table_list").hide();
                $("#booked_table").attr("multiple", "multiple");
                $(".marge_table").attr('checked', true);
                $("#booked_table").css({
                    'margin-bottom': '-12px',
                    'height': '55px',
                    'background': 'white'
                });
                $("#table_list").css({
                    'margin-top': '19px',
                    'display': 'block'
                });
                $("#table_list tr").show();
            } else {
                $("#booked_table_list").hide();
                $("#table_list tr").show();
                $("#table_list").css("display", "block");
                $(".marge_table").attr('checked', false);
            }
        },
        get_order_list: function() {
            return this.get('orders').models;
        },
        set_textbox_attributes: function(input_name, type_of_popup) {
            this.input_name = input_name;
            var self = this;
            if (type_of_popup == 'delivery_order_popup') {
                $('#' + input_name).change(function(e) {
                    $("#person_number_txt").val("");
                    if ($('#' + input_name).val() && $('#' + input_name + ' option:selected') &&
                        $('#' + input_name + ' option:selected').attr('data-id')) {
                        var partner = self.partner_dict[parseInt($('#' + input_name + ' option:selected').attr('data-id'))];
                        if (partner) {
                            if (!partner.phone) {
                                $("#person_number_txt").val("");
                            } else {
                                $("#person_number_txt").val(partner.phone);
                            }
                        }
                    }
                });
            }
        },
        open_alert_dialog: function(message, icon) {
            var warning_icon = icon;
            var message = message;
            var title = _t('Warning !');
            this.alert_dialog = $(QWeb.render('AlertDialog', {
                'widget': self,
                'message': message,
                'title': title,
                'warning_icon': warning_icon
            })).dialog({
                resizable: false,
                height: "auto",
                width: 500,
                position: "center",
                modal: 'true',
                open: function() {
                    $(".ui-dialog-titlebar").hide();
                    $(".ui-dialog").css('overflow', 'hidden');
                    $("body").addClass('hide_over_flow');
                    $(".ui-widget-overlay").height($(document).height() + 15);
                    set_ui_widget_overlay()
                    $(".ui-dialog").addClass('alert_dialog_warning');
                    $('.ui-dialog-buttonpane').find('button:contains("Ok")').addClass('alert_dialog_button');
                    $(".pincode_dialog_warning").hide();
                    $(".add_customer_dialog_warning").hide();
                },
                close: function(event, ui) {
                    $(this).remove();
                    $(".pincode_dialog_warning").show();
                    $(".add_customer_dialog_warning").show();
                    $("body").removeClass('hide_over_flow');
                },
                buttons: {
                    "Ok": function() {
                        $(".ui-dialog-titlebar").show();
                        $(".ui-dialog").removeClass('alert_dialog_warning');
                        $(this).remove();
                        $("body").removeClass('hide_over_flow');
                        $(".pincode_dialog_warning").show();
                        $(".add_customer_dialog_warning").show();
                    },
                },
            });
        },
        // this is called when an order is removed from the order collection. It ensures that there is always an existing
        // order and a valid selected order
        on_removed_order: function(removed_order, index, reason) {
            var order_list = this.get_order_list();
            var self = this;
            if (this.config.iface_floorplan) {
                if ((reason === 'abandon' || removed_order.temporary || this.get('orders').last()) && order_list.length > 0) {
                    self.set_order(order_list[index] || order_list[order_list.length - 1]);
                } else {
                    // back to the floor plan
                    this.table = null;
                    this.gui.show_screen('floors');
                    this.gui.screen_instances.floors.renderElement();
                }
            } else {
                self.add_new_order();
            }
        },
    });
    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function(attributes, options) {
            var self = this;
            this.set({
                'parcel': false,
                'driver_name': false,
                'partner_id': false,
                'phone': false,
                'pflag': false,
                'creationDate': false,
                'table_data': [],
                'reserved_seat': [],
                'table_ids': [],
                'split_order': null,
                'confirm_receipt': false,
                'offline_confirm_order': false,
                'confirm_order': false,
            });
            if (!options.json) {
                $.ajax({
                    type: 'GET',
                    success: function() {
                        self.set('offline_order', false);
                        self.set('offline_order_name', false)
                        self.trigger('change', self);
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                        self.set('offline_order', true);
                        self.set('offline_order_name', self.name)
                        self.trigger('change', self);
                    }
                });
            }
            _super_order.initialize.apply(this, arguments);
        },
        getDriver: function() {
            if (this.get('driver_name')) {
                return this.get('driver_name');
            } else {
                return false;
            }
        },
        set_confirm_receipt: function(confirm_receipt) {
            this.set('confirm_receipt', confirm_receipt);
        },
        get_confirm_receipt: function() {
            return this.get('confirm_receipt');
        },
        getphone: function() {
            if (this.get('phone')) {
                return this.get('phone');
            } else {
                return false;
            }
        },
        getFlag: function() {
            if (this.get('pflag')) {
                return this.get('pflag');
            } else {
                return false;
            }
        },
        getParcel: function() {
            if (this.get('parcel')) {
                return this.get('parcel');
            } else {
                return false;
            }
        },
        get_table_name: function() {
            if (this.get('creationDate')) {
                return this.get('creationDate');
            } else {
                return false
            }
        },
        init_from_JSON: function(json) {
            _super_order.init_from_JSON.apply(this, arguments);
            var self = this;
            self.attributes.parcel = json.parcel;
            self.attributes.pflag = json.pflag;
            self.attributes.creationDate = json.creationDate;
            self.attributes.reserved_seat = json.reserved_seat;
            self.attributes.table_ids = json.table_ids;
            self.attributes.table_data = json.table_data;
            self.attributes.driver_name = json.driver_name;
            self.attributes.split_order = json.split_order;
            self.attributes.offline_order_name = json.offline_order_name;
            self.attributes.offline_confirm_order = json.offline_confirm_order;
            self.attributes.confirm_order = json.confirm_order;
            self.attributes.offline_order = json.offline_order;
            if (json.partner_id) {
                _.each(this.pos.partners, function(partner) {
                    if (partner.id == json.partner_id) {
                        self.partner_id = partner.name;
                    }
                });
            }
        },
        export_as_JSON: function(json) {
            var json = _super_order.export_as_JSON.apply(this, arguments);
            var self = this;
            json.pflag = this.getFlag();
            json.parcel = this.getParcel();
            json.phone = this.getphone();
            json.confirm_receipt = this.get_confirm_receipt();
            json.driver_name = this.getDriver();
            json.table_id = (this.attributes.table && !this.attributes.parcel && !this.getDriver()) ? this.attributes.table.id : false;
            json.floor = (this.attributes.table && !this.attributes.parcel && !this.getDriver()) ? this.attributes.table.floor.name : false;
            json.floor_id = (this.attributes.table && !this.attributes.parcel && !this.getDriver()) ? this.attributes.table.floor.id : false;
            json.customer_count = (!this.attributes.parcel && !this.getDriver()) ? this.customer_count : false;
            json.table_data = (this.attributes.table_data && !this.attributes.parcel && !this.getDriver()) ? this.attributes.table_data : [];
            json.creation_date = self.validation_date || self.creation_date;
            json.creationDate = (this.attributes.creationDate && !this.attributes.parcel && !this.getDriver()) ? this.attributes.creationDate : false;
            json.table_ids = (this.attributes.table_ids && !this.attributes.parcel && !this.getDriver()) ? this.attributes.table_ids : [];
            json.reserved_seat = (this.attributes.reserved_seat && !this.attributes.parcel && !this.getDriver()) ? this.attributes.reserved_seat : [];
            json.split_order = this.attributes.split_order ? this.attributes.split_order : null;
            json.offline_delete_order = this.offline_delete_order ? true : false;
            json.offline_order_name = this.attributes.offline_order_name;
            json.offline_confirm_order = this.attributes.offline_confirm_order;
            json.confirm_order = this.attributes.confirm_order;
            json.offline_order = this.attributes.offline_order;
            return json;
        },
        clean_empty_paymentlines: function() {
            var lines = this.paymentlines.models;
            var empty = [];
            for (var i = 0; i < lines.length; i++) {
                // if (!lines[i].get_amount()) {
                empty.push(lines[i]);
                //}
            }
            for (var i = 0; i < empty.length; i++) {
                this.remove_paymentline(empty[i]);
            }
        },
    });

    // create Parcel Order Popup Widget
    var ParcelOrderPopupWidget = pop_up.extend({
        template: 'ParcelOrderPopupWidget',
        show: function(options) {
            options = options || {};
            var self = this;
            this._super();
            this.title = options.title;
            this.renderElement();
            this.$('.footer .ok').click(function() {
                if ($("#take_away_txt").val().length == 0) {
                    var warning_icon = true;
                    var message = _t("Parcel Order is Empty,Please Enter Parcel Order Name");
                    self.pos.open_alert_dialog(message, warning_icon);
                    return false;
                } else {
                    self.gui.close_popup();
                    self.take_away(self.pos, self.pos.callable);
                }
            });
            if (!self.pos.config.iface_vkeyboard) {
                $('#take_away_txt').focus();
            }
            if (this.pos.config.iface_vkeyboard && this.chrome.widget.keyboard) {
                this.chrome.widget.keyboard.connect($('#take_away_txt'));
            }
            this.$('.footer .close').click(function() {
                self.gui.close_popup();
            });
            self.hotkey_handler = function(event) {
                if (event.which === 13) {
                    self.$('.footer .ok').click();
                } else if (event.which === 27) {
                    self.gui.close_popup();
                }
            };
            $('body').on('keypress', self.hotkey_handler);
        },
        take_away: function(pos, callable) {
            var self = pos;
            var iptxtval = $("#take_away_txt").val();
            var order = new models.Order({}, {
                pos: self
            });
            order.set('pflag', true);
            order.set('parcel', iptxtval);
            order.set('driver_name', false);
            order.set('phone', false);
            self.get('orders').add(order);
            self.set('selectedOrder', order);
        },
        close: function() {
            this._super();
            $('body').off('keypress', this.hotkey_handler);
            if (this.pos.config.iface_vkeyboard && this.chrome.widget.keyboard) {
                this.chrome.widget.keyboard.hide();
                this.chrome.widget.keyboard.connect($('.searchbox input'));
            }
        },
    });
    // Declare Parcel Order Popup Widget
    gui.define_popup({
        name: 'parcel_order',
        widget: ParcelOrderPopupWidget
    });

    // Create Delivery Order Popup Widget
    var DeliveryOrderPopupWidget = pop_up.extend({
        template: 'DeliveryOrderPopupWidget',
        show: function(options) {
            options = options || {};
            var self = this;
            this._super();
            this.title = options.title;
            this.delivery = options.delivery;
            this.renderElement();
            self.pos.set_textbox_attributes('partner_selection', 'delivery_order_popup');
            this.$('.footer .ok').click(function() {
                self.delivery_order(self.pos, self.pos.callable);
            });

            this.$(".footer .new_customer").click(function() {
                self.add_customer();
            });

            this.$('.footer .close').click(function() {
                self.gui.close_popup();
            });
            $('#partner_selection').select2({
                openOnEnter: false
            });
            $('#driver_name').select2({
                openOnEnter: false
            });
            self.hotkey_handler = function(event) {
                if (event.which === 13) {
                    self.$('.footer .ok').click();
                } else if (event.which === 27) {
                    self.gui.close_popup();
                }
            };
            $('body').on('keyup', self.hotkey_handler);
        },
        delivery_order: function(pos, callable) {
            var self = pos;
            var partner_id = null;
            var driver = null;
            if (!$("#partner_selection").val()) {
                var warning_icon = true;
                var message = _t("Please Select Customer.");
                self.open_alert_dialog(message, warning_icon);
                return false;
            } else if ($("#partner_selection").val()) {
                partner_id = $("#partner_selection").val();
            }
            if (!$("#person_number_txt").val()) {
                var warning_icon = true;
                var message = _t("Please Enter Phone Number.");
                self.open_alert_dialog(message, warning_icon);
                return false;
            }
            if (!$('#driver_name').val()) {
                var warning_icon = true;
                var message = _t("Please Select Delivery Boy.");
                self.open_alert_dialog(message, warning_icon);
                return false;
            } else {
                var customer_not_exits = true;
                var current_partner = false;
                if ($('#partner_selection').val() && $('#partner_selection option:selected') &&
                    $('#partner_selection option:selected').attr('data-id')) {
                    var partner = self.partner_dict[parseInt($('#partner_selection option:selected').attr('data-id'))];
                    if (partner) {
                        customer_not_exits = false;
                        current_partner = partner;
                    }
                }
                if (customer_not_exits) {
                    var warning_icon = true;
                    var message = _t("Customer not Exists");
                    self.open_alert_dialog(message, warning_icon);
                    return false;
                }
                var driver_not_exits = true;
                _.each(self.delivery_boy, function(user) {
                    if (user.name.toLowerCase() == $('#driver_name').val().toLowerCase()) {
                        driver = user.id;
                        driver_not_exits = false;
                    }
                });
                if (driver_not_exits) {
                    var warning_icon = true;
                    var message = _t("Invalid Driver");
                    self.open_alert_dialog(message, warning_icon);
                    return false;
                }
                var order = new models.Order({}, {
                    pos: self
                });
                if (partner_id && current_partner) {
                    order.set_client(current_partner);
                }
                var phone = $("#person_number_txt").val();
                var pflag = false;
                var parcel = false;
                order.partner_id = partner_id;
                order.set('pflag', pflag);
                order.set('parcel', parcel);
                order.set('driver_name', driver);
                order.set('phone', phone);
                order.set('partner_id', partner_id);
                if (partner_id.length == 0) {
                    var warning_icon = true;
                    var message = _t("Person name is Empty,Please Enter Person Name");
                    self.open_alert_dialog(message, warning_icon);
                    return false;
                }
                self.get('orders').add(order);
                self.set('selectedOrder', order);
                self.gui.close_popup();
            }
        },
        add_customer: function() {
            var self = this;
            self.add_customer_dialog = $(QWeb.render('add-customer', {
                'widget': self
            })).dialog({
                resizable: false,
                width: 350,
                title: _t("Add Customer"),
                modal: true,
                open: function() {
                    $('body').off('keyup', self.hotkey_handler);
                    $(".ui-dialog").addClass('add_customer_dialog_warning');
                    $(".ui-dialog").css('overflow', 'hidden')
                    $("body").addClass('hide_over_flow');
                    $(".ui-widget-overlay").height($(document).height() + 15);
                    set_ui_widget_overlay()
                    $(".ui-dialog-titlebar-close").hide();
                    $('.ui-dialog-buttonpane').find('button:contains("Ok")').addClass('alert_dialog_button');
                    $('.ui-dialog-buttonpane').find('button:contains("Close")').addClass('alert_dialog_button');
                },
                close: function(event, ui) {
                    $('body').on('keyup', self.hotkey_handler);
                    $(this).remove();
                    $("body").removeClass('hide_over_flow');
                },
                buttons: {
                    "Ok": function() {
                        var c_name = ($("#customer_name").val()).trim();
                        var c_street = ($("#input_street").val()).trim();
                        var c_street2 = ($("#input_street2").val()).trim();
                        var c_city = ($("#input_city").val()).trim();
                        var c_zip = ($('#input_zip').val()).trim();
                        var c_phone = ($('#input_phone').val()).trim();
                        var nb_error = 0;
                        if (c_name == '') {
                            var warning_icon = true;
                            var message = _t("Please Enter Customer Name.");
                            self.pos.open_alert_dialog(message, warning_icon);
                            nb_error++;
                            return false;
                        }
                        if (c_phone == '') {
                            var warning_icon = true;
                            var message = _t("Please Enter Customer Phone Number.");
                            self.pos.open_alert_dialog(message, warning_icon);
                            nb_error++;
                            return false;
                        }
                        if (nb_error > 0) {
                            var warning_icon = true;
                            var message = _t("Please Enter Correct Data");
                            self.pos.open_alert_dialog(message, warning_icon);
                        } else {
                            // var Partners = new Model('res.partner');
                            rpc.query({
                                model: 'res.partner',
                                method: 'create_customer_from_pos',
                                args: [c_name, c_street, c_street2, c_city, c_zip, c_phone],
                            }).then(function(clientId) {
                                // (new Model('res.partner')).get_func('read')(clientId)
                                rpc.query({
                                    model: 'res.partner',
                                    method: 'read',
                                    args: [
                                        [clientId]
                                    ],
                                }).then(function(callback) {
                                    self.pos.partners.push(callback[0]);
                                    if (! is_pos_quick_load_data){
                                        self.pos.partner_list.push(callback[0]);
                                    }
                                    self.pos.partner_dict[parseInt(callback[0].id)] = callback[0];
                                    $("#person_number_txt").val(callback[0].phone);
                                    self.gui.close_popup();
                                    self.gui.show_popup('delivery_order', {
                                        title: _t('Delivery'),
                                        delivey: true,
                                    });
                                });
                            }, function(err, event) {
                                event.preventDefault();
                                var warning_icon = true;
                                var message = _t('Error : Can not create customer.');
                                self.pos.open_alert_dialog(message, warning_icon);
                            });
                            // Partners.call('create_customer_from_pos', [c_name, c_street,c_street2,c_city,c_zip, c_phone])
                            $(this).remove();
                            self.add_customer_dialog.remove();
                            $("body").removeClass('hide_over_flow');
                        }
                        $('body').on('keyup', self.hotkey_handler);
                    },
                    "Close": function() {
                        $(this).remove();
                        $("body").removeClass('hide_over_flow');
                        self.add_customer_dialog.remove();
                        $('body').on('keyup', self.hotkey_handler);
                    }
                },
            });
        },
        close: function() {
            this._super();
            $('body').off('keyup', this.hotkey_handler);
        },
    });
    // Declare Delivery Order Popup Widget
    gui.define_popup({
        name: 'delivery_order',
        widget: DeliveryOrderPopupWidget
    });


    keyboard.OnscreenKeyboardWidget.include({
        //called after the keyboard is in the DOM, sets up the key bindings.
        start: function() {
            var self = this;
            $('.close_button').unbind('click').bind('click', function() {
                //self.deleteAllCharacters();
                self.hide();
            });
            // Keyboard key click handling
            $('.keyboard li').click(function() {
                var $this = $(this),
                    character = $this.html(); // If it's a lowercase letter, nothing happens to this variable
                if ($this.hasClass('left-shift') || $this.hasClass('right-shift')) {
                    self.toggleShift();
                    return false;
                }
                if ($this.hasClass('capslock')) {
                    self.toggleCapsLock();
                    return false;
                }
                if ($this.hasClass('delete')) {
                    self.deleteCharacter();
                    return false;
                }
                if ($this.hasClass('numlock')) {
                    self.toggleNumLock();
                    return false;
                }
                // Special characters
                if ($this.hasClass('symbol')) character = $('span:visible', $this).html();
                if ($this.hasClass('space')) character = ' ';
                if ($this.hasClass('tab')) character = "\t";
                if ($this.hasClass('return')) {
                    character = "\n";
                    self.hide();
                }
                // Uppercase letter
                if ($this.hasClass('uppercase')) character = character.toUpperCase();
                // Remove shift once a key is clicked.
                self.removeShift();
                self.writeCharacter(character);
            });
        },
    });

    chrome.OrderSelectorWidget.include({
        neworder_click_handler: function(event, $el) {
            if (this.pos.config.iface_floorplan) {
                this.gui.show_screen('floors');
                this.gui.screen_instances.floors.renderElement();
            } else {
                this.pos.add_new_order();
            }
        },
        renderElement: function() {
            var self = this;
            this._super();
            $('#options').click(function(event) {
                $.ajax({
                    type: 'GET',
                    success: function() {
                        self.gui.show_screen('reassign_table_screen');
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                        self.gui.show_popup('confirm', {
                            'title': _t('Offline Orders'),
                            'body': _t(['Check your internet connection and try again.']),
                            'confirm': function() {},
                        });
                    }
                });
            });
            $('#synch_order').click(function(event) {
                self.gui.screen_instances.unpaid_orders_screen.renderElement();
                self.gui.show_screen('unpaid_orders_screen');

            });
        },
    });
    NumberPopupWidget.widget.include({
        show: function(options) {
            options = options || {};
            this._super(options);
            var self = this;
            this.options = options
            this.add_customer = options.add_customer ? options.add_customer : false;
            this.inputbuffer = '' + (options.value || '');
            this.decimal_separator = _t.database.parameters.decimal_point;
            this.renderElement();
            this.firstinput = true;
            this.add_customer ? $(".pos .popup.popup-number").addClass('popup_height') : $(".pos .popup.popup-number").removeClass('popup_height')
            $("#customer_selection").select2({
                openOnEnter: false
            });
            self.numberpopup_event_handler = function(event) {
                if (event.which === 13) {
                    self.click_confirm();
                } else if (event.which === 27) {
                    self.gui.close_popup();
                }
            };
            document.body.addEventListener('keyup', self.numberpopup_event_handler);
        },
        close: function() {
            var self = this;
            this._super();
            document.body.removeEventListener('keyup', self.numberpopup_event_handler);
        },
    });

    resturant.TableWidget.include({
        click_handler: function() {
            var self = this;
            var floorplan = this.getParent();
            if (floorplan.editing) {
                setTimeout(function() { // in a setTimeout to debounce with drag&drop start
                    if (!self.dragging) {
                        if (self.moved) {
                            self.moved = false;
                        } else if (!self.selected) {
                            self.getParent().select_table(self);
                        } else {
                            self.getParent().deselect_tables();
                        }
                    }
                }, 50);
            } else {
                if (self.table.state == "reserved") {
                    //floorplan.pos.set_table(self.table);
                    for (var i = 0; i < self.pos.get('orders').models.length; i++) {
                        if (_.contains(self.pos.get('orders').models[i].get('table_ids'), self.table.id)) {
                            self.gui.show_screen('products')
                            self.pos.set({
                                'selectedOrder': self.pos.get('orders').models[i]
                            });
                            break;
                        }
                    }
                    return false;
                } else {
                    self.gui.show_popup('number', {
                        'title': _t('Number of Person ?'),
                        'cheap': true,
                        'add_customer': true,
                        'value': self.table.seating_capacities,
                        'confirm': function(value) {
                            self.table.client_detalis = null;
                            if ($('#customer_selection').val().length) {
                                _.each(self.pos.partners, function(partner) {
                                    if (partner.id == $("#customer_selection option").filter(':selected').attr("data-id")) {
                                        self.table.client_detalis = partner;
                                        $("#" + self.table.id + '_sit_reserv').val(value)
                                        floorplan.pos.set_table(self.table);
                                    }
                                });
                            } else {
                                $("#" + self.table.id + '_sit_reserv').val(value);
                                floorplan.pos.set_table(self.table);
                            }
                        },
                    });
                }
            }
        },
        set_table_seats: function(seats) {
            if (seats) {
                this.table.capacities = Number(seats);
                this.table.seating_capacities = Number(seats);
                this.table.seats = Number(seats);
                this.renderElement();
            }
        },
        table_style: function() {
            var table = this.table;

            function unit(val) {
                return '' + val + 'px';
            }
            var style = {
                'width': unit(table.width),
                'height': unit(table.height),
                'line-height': unit(table.height),
                'margin-left': unit(-table.width / 2),
                'margin-top': unit(-table.height / 2),
                'top': unit(table.position_v + table.height / 2),
                'left': unit(table.position_h + table.width / 2),
                'border-radius': table.shape === 'round' ?
                    unit(Math.max(table.width, table.height) / 2) : '3px',
            };
            if (table.color) {
                style.background = table.color;
            }
            if (table.available_capacities != 0 && table.state == 'available') {
                style.background = 'red';
            }
            if (table.state != 'available') {
                style.background = 'gray';
            }
            if (table.height >= 150 && table.width >= 150) {
                style['font-size'] = '32px';
            }
            if (table.shape == 'round' && table.width < 85) {
                style.width = '85px';
            }
            return style;
        },
    });

    resturant.FloorScreenWidget.include({
        init: function(parent, options) {
            this._super(parent, options);
            this.width = (this.pos.config.display_parcel && is_admin) ? '49%' : '100%';
            this.width = (this.pos.config.display_delivery && is_admin) ? '49%' : this.width;
            this.width = (this.pos.config.display_delivery && this.pos.config.display_parcel) ? '49%' : this.width;
            this.width = (this.pos.config.display_delivery && this.pos.config.display_parcel && is_admin) ? '33%' : this.width;
            this.is_admin = is_admin;
        },
        click_back_button: function(event, $el) {
            if (this.pos.get('orders').size() > 0) {
                this.pos.set({
                    'selectedOrder': this.pos.get('orders').last()
                });
                this.gui.show_screen('products')
            }
        },
        sync_orders: function() {
            var self = this;
            // new Model('pos.order').call('get_draft_state_order', [
            //     []
            // ])
            rpc.query({
                model: 'pos.order',
                method: 'get_draft_state_order',
                args: [
                    []
                ],
            }).done(function(callback) {
                if (callback) {
                    _.each(callback, function(ord) {
                        var flag = true;
                        for (o in self.pos.attributes.orders.models) {
                            if (self.pos.attributes.orders.models[o].attributes.name == ord.pos_reference) {
                                flag = false;
                                break;
                            }
                        }
                        if (flag) {
                            var selected_order = new models.Order({}, {
                                pos: self.pos
                            });
                            var template = '<span class="order-sequence">' + selected_order.sequence_number + '</span>'
                            $("#" + selected_order.name.replace(' ', '_')).attr("name", ord.order_name);
                            $("#" + selected_order.name.replace(' ', '_')).attr("item", ord.order_name);
                            if (ord.reserved_seat) {
                                $("#" + selected_order.name.replace(' ', '_')).attr("data", ord.reserved_seat);
                                selected_order.attributes.table_data = ord.table_data;
                                selected_order.attributes.reserved_seat = ord.reserved_seat;
                                selected_order.set('table_data', ord.table_data);
                                selected_order.set('reserved_seat', ord.reserved_seat);
                            }
                            $("#" + selected_order.name.replace(' ', '_')).html(template + ord.order_name);
                            selected_order.attributes.creationDate = ord.order_name;
                            selected_order.attributes.creationDateId = ord.order_name;
                            selected_order.set('creationDate', ord.order_name);
                            selected_order.set('creationDateId', ord.creation_date_id);
                            if (ord.table_ids) {
                                selected_order.attributes.table_ids = ord.table_ids;
                                selected_order.set('table_ids', ord.table_ids);
                            }
                            if (ord.pflag) {
                                selected_order.set('creationDate', false);
                            }
                            if (ord.driver_name) {
                                selected_order.set('creationDate', false);
                                selected_order.set('driver_name', ord.driver_name);
                            }
                            selected_order.set('name', ord.pos_reference);
                            selected_order.attributes.name = ord.pos_reference;
                            selected_order.attributes.id = ord.id;
                            selected_order.attributes.pflag = ord.pflag;
                            selected_order.attributes.parcel = ord.parcel;
                            selected_order.attributes.phone = ord.phone;
                            selected_order.set('pflag', ord.pflag);
                            selected_order.set('parcel', ord.parcel);
                            selected_order.set('phone', ord.phone);
                            if (ord.partner_ids) {
                                var partner = self.pos.db.get_partner_by_id(ord.partner_ids);
                                selected_order.set_client(partner);
                            }
                            var products = [];
                            _.each(ord.lines, function(get_line) {
                                product = self.pos.db.get_product_by_id(get_line.product_id);
                                var line_set = new models.Orderline({}, {
                                    pos: self.pos,
                                    order: selected_order,
                                    product: product
                                });
                                line_set.id = get_line.id;
                                line_set.line_id = get_line.id;
                                line_set.quantity = get_line.qty;
                                line_set.set_quantity(get_line.qty);
                                line_set.price = get_line.price_unit;
                                line_set.set_unit_price(get_line.price_unit);
                                line_set.discount = get_line.discount;
                                line_set.set_product_lot(product)
                                products.push(product);
                                selected_order.orderlines.add(line_set);
                            });
                            // pos_order_model.call("write",[[ord.id],{'is_synch_order':true}])
                            rpc.query({
                                model: 'pos.order',
                                method: 'write',
                                args: [
                                    [ord.id], {
                                        'is_synch_order': true
                                    }
                                ],
                            }).then(
                                function(callback) {},
                                function(err, event) {
                                    event.preventDefault();
                                });
                            self.pos.get('orders').add(selected_order);
                        }
                    });
                    if (self.pos.get('orders').size() > 0) {
                        self.pos.set({
                            'selectedOrder': self.pos.get('orders').last()
                        });
                        self.gui.show_screen('products');
                    }
                } else {
                    self.gui.show_popup('alert', {
                        title: _t('Warning !'),
                        body: _t("There is no any draft orders!!")
                    });
                }
            });
        },
        set_floor_tables: function() {
            var self = this;
            this.table_widgets = [];
            screens.ScreenWidget.prototype.renderElement.apply(self, arguments);
            self.chrome.widget.order_selector.hide();
            _.each(self.pos.table_details, function(rec) {
                for (var i = 0; i < self.floor.tables.length; i++) {
                    if (rec.id == self.floor.tables[i].id) {
                        self.floor.tables[i].seating_capacities = rec.capacities - rec.available_capacities;
                        self.floor.tables[i].available_capacities = rec.available_capacities;
                        self.floor.tables[i].state = rec.state;
                        var tw = new resturant.TableWidget(self, {
                            table: self.floor.tables[i],
                        });
                        tw.appendTo(self.$('.floor-map .tables'));
                        self.table_widgets.push(tw);
                        break;
                    }
                }
            });
            self.$('.floor-selector .button').click(function(event) {
                self.click_floor_button(event, $(this));
            });
            self.$('.edit-button.shape').click(function() {
                self.tool_shape_action();
            });
            self.$('.edit-button.color').click(function() {
                self.tool_colorpicker_open();
            });
            self.$('.edit-button.dup-table').click(function() {
                self.tool_duplicate_table();
            });
            self.$('.edit-button.new-table').click(function() {
                self.tool_new_table();
            });
            self.$('.edit-button.rename').click(function() {
                self.tool_rename_table();
            });
            self.$('.edit-button.seats').click(function() {
                self.tool_change_seats();
            });
            self.$('.edit-button.trash').click(function() {
                self.tool_trash_table();
            });
            self.$('.color-picker .close-picker').click(function(event) {
                self.tool_colorpicker_close();
                event.stopPropagation();
            });
            self.$('.color-picker .color').click(function(event) {
                self.tool_colorpicker_pick(event, $(this));
                event.stopPropagation();
            });
            self.$('.edit-button.editing').click(function() {
                $.ajax({
                    type: 'GET',
                    success: function() {
                        self.toggle_editing();
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {}
                });
            });
            self.$('.floor-map,.floor-map .tables').click(function(event) {
                if (event.target === self.$('.floor-map')[0] ||
                    event.target === self.$('.floor-map .tables')[0]) {
                    self.deselect_tables();
                }
            });
            self.$('.color-picker .close-picker').click(function(event) {
                self.tool_colorpicker_close();
                event.stopPropagation();
            });
            self.$('.back').click(function(event) {
                self.click_back_button(event, $(this));
            });
            self.$('#delivery').bind('click', function() {
                self.gui.show_popup('delivery_order', {
                    title: _t('Delivery'),
                    delivey: true,
                });
            });
            self.$('#take_away').bind('click', function() {
                self.gui.show_popup('parcel_order', {
                    title: _t('Take Away'),
                });
            });
            self.$('#synchroniz_order').bind('click', function() {
                self.sync_orders();
            });
            self.update_toolbar();
        },
        render_floor_data: function() {
            var self = this;
            $.when(self.pos.initialize_table_details(false, false)).done(function() {
                self.set_floor_tables();
            }).fail(function(err, event) {
                self.set_floor_tables();
            });
        },
        renderElement: function() {
            var self = this;
            // cleanup table widgets from previous renders
            for (var i = 0; i < this.table_widgets.length; i++) {
                this.table_widgets[i].destroy();
            }
            this.table_widgets = [];
            var unpaid_orders = self.pos.db.get_unpaid_orders();
            if (unpaid_orders.length != 0) {
                var order_ids_to_sync = _.omit(_.indexBy(unpaid_orders, 'offline_order_name'), 'false', 'undefined');
                if (_.size(order_ids_to_sync) != 0) {
                    var table_vals = {};
                    _.each(order_ids_to_sync, function(order, key) {
                        if (order.table_data && order.table_data.length > 0) {
                            _.each(order.table_data, function(table_record) {
                                if (!order.split_order) {
                                    if (_.has(table_vals, table_record.table_id)) {
                                        table_vals[table_record.table_id] = parseInt(table_vals[table_record.table_id]) + parseInt(table_record.reserver_seat);
                                    } else {
                                        table_vals[table_record.table_id] = parseInt(table_record.reserver_seat);
                                    }
                                }
                            });
                        }
                    });
                    $.blockUI();
                    //             // restaurant_table_model.call("update_offline_table_order", [table_vals])
                    rpc.query({
                        model: 'restaurant.table',
                        method: 'update_offline_table_order',
                        args: [table_vals],
                    }).done(function() {
                        _.each(order_ids_to_sync, function(order, key) {
                            if (order.table_data && order.table_data.length > 0) {
                                order.offline_order_name = false;
                                self.pos.db.save_unpaid_update_order(order);
                            }
                        });
                        $.unblockUI();
                        self.render_floor_data();
                    }).fail(function(err, event) {
                        $.unblockUI();
                        self.render_floor_data();
                    });
                } else {
                    self.render_floor_data();
                }
            } else {
                self.render_floor_data();
            }
        },
        tool_change_seats: function() {
            var self = this;
            if (this.selected_table) {
                this.gui.show_popup('number', {
                    'title': _t('Number of Seats ?'),
                    'cheap': true,
                    'add_customer': false,
                    'value': self.selected_table.table.seating_capacities,
                    'confirm': function(value) {
                        self.selected_table.set_table_seats(value);
                    },
                });
            }
        },
        tool_change_seats: function() {
            var self = this;
            if (this.selected_table) {
                this.gui.show_popup('number', {
                    'title': _t('Number of Seats ?'),
                    'cheap': true,
                    'add_customer': false,
                    'value': self.selected_table.table.seating_capacities,
                    'confirm': function(value) {
                        self.selected_table.set_table_seats(value);
                    },
                });
            }
        },
        tool_duplicate_table: function() {
            if (this.selected_table) {
                var tw = this.create_table(this.selected_table.table);
                tw.table.position_h += 10;
                tw.table.position_v += 10;
                tw.table.users_ids = [
                    [6, 0, this.selected_table.table.users_ids]
                ];
                tw.save_changes();
                this.select_table(tw);
            }
        },
        tool_new_table: function() {
            var tw = this.create_table({
                'position_v': 100,
                'position_h': 100,
                'width': 75,
                'height': 75,
                'shape': 'square',
                'seats': 1,
                'capacities': 1,
                'seating_capacities': 1,
                'available_capacities': 0,
                'users_ids': [
                    [6, 0, [this.pos.session.uid]]
                ],
            });
            tw.save_changes();
            this.select_table(tw);
            this.check_empty_floor();
        },
        create_table: function(params) {
            var table = {};
            for (var p in params) {
                table[p] = params[p];
            }
            table.name = this.new_table_name(params.name);
            delete table.id;
            table.floor_id = [this.floor.id, ''];
            table.floor = this.floor;
            table.state = 'available'
            this.pos.table_details.push(table)

            this.floor.tables.push(table);
            var tw = new resturant.TableWidget(this, {
                table: table
            });
            tw.appendTo('.floor-map .tables');
            this.table_widgets.push(tw);
            return tw;
        },

    });

    gui.Gui.include({
        show_saved_screen: function(order, options) {
            options = options || {};
            this.close_popup();
            if (order) {
                if (order.get_screen_data('screen') != 'floors') {
                    this.show_screen(order.get_screen_data('screen') ||
                        options.default_screen ||
                        this.default_screen,
                        null, 'refresh');
                } else {
                    this.show_screen(options.default_screen || this.default_screen,
                        null, 'refresh');
                }
            } else {
                this.show_screen(this.startup_screen);
            }
        },
    });

    var ReassignTableScreenWidget = screens.ScreenWidget.extend({
        template: 'ReassignTableScreenWidget',
        hide: function() {
            this._super();
            $(".pos-leftpane").show();
            $(".rightpane").removeClass("full_screen");
        },
        show: function() {
            var self = this;
            this._super();
            this.renderElement();
            $(".pos-leftpane").hide();
            $(".rightpane").addClass("full_screen");
        },
        renderElement: function() {
            this._super();
            var self = this;
            this.$el.find("#back_screen").bind("click", function() {
                self.gui.show_screen('products');
            });
            this.$el.find(".oe_sidebar_print").bind("click", function() {
                self.pos.option_value = '';
                self.pos.option_text = $(this).text();
                self.pos.option_value = $(this).attr("id");
                self.$el.find(".oe_sidebar_print").removeClass('highlight')
                $(this).addClass('highlight')
                $(".reassign_table_screen_content").html("")
                flag = 0;
                _.each(self.pos.attributes.orders.models, function(order) {
                    if (order.attributes.reserved_seat)
                        flag++;
                });
                if (flag) {
                    self.pos.initialize_table_details(false, true);
                }
            });
            this.$el.find('.re_assign_order_button').click(function(e) {
                $.ajax({
                    type: 'GET',
                    success: function() {
                        self.order_re_assign(self.pos);
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                        self.gui.show_popup('confirm', {
                            'title': _t('Offline Orders'),
                            'body': _t(['Check your internet connection and try again.']),
                            'confirm': function() {},
                        });
                    }
                });
            });
            $("#re_assign_order").click();
            //            document.body.removeEventListener('keyup',this.pos.re_assign_event_handler);
        },
        order_re_assign: function(pos) {
            var self = pos;
            var tabel_screen = this;
            var selection_name = '';
            var reserved_seat = '';
            var selection_id = [];
            var select_tables = [];
            var flag = true;
            self.is_any_checked_table = false;
            $('#table_list tr input[type="checkbox"]:checked').each(function(index) {
                self.is_any_checked_table = true;
                selection_name += ' ' + this.value + "/" + $("#" + $(this).attr('id') + '_reserv_sit').val(); //selected_row[1]
                table_id = parseInt($(this).attr('id'));
                selection_id.push(table_id); //selected_row[0]
                reserved_seat += $(this).attr('id') + "/" + $("#" + $(this).attr('id') + '_reserv_sit').val() + '_';
                actual_reserved_seat = parseInt($("#" + $(this).attr('id') + '_reserv_sit').val());
                already_booked_seat = parseInt($("#" + $(this).attr('id') + '_reserv_sit').attr('booked'));
                available_seat = parseInt($("#" + $(this).attr('id') + '_leaft_seat')[0].innerHTML);
                select_tables.push({
                    reserver_seat: $("#" + $(this).attr('id') + '_reserv_sit').val(),
                    table_id: table_id
                });
                var table_vals = {
                    'available_capacities': actual_reserved_seat + already_booked_seat
                };

                if (actual_reserved_seat == available_seat) {
                    table_vals['state'] = 'reserved';
                }
                if ((actual_reserved_seat > available_seat) || (available_seat == 0)) {
                    self.gui.show_popup('alert', {
                        title: _t('Warning !'),
                        body: _t("Table capacity is ") + $("#" + $(this).attr('id') + '_leaft_seat')[0].innerHTML + _t(" person you cannot enter more then ") + $("#" + $(this).attr('id') + '_leaft_seat')[0].innerHTML + _t(" or less than 1. "),
                    });
                    flag = false;
                    return false;
                }
                if (self.re_assign) {
                    if ($("#booked_table option").filter(':selected').val()) {
                        rpc.query({
                            model: 'restaurant.table',
                            method: 'write',
                            args: [
                                [table_id], table_vals
                            ],
                        }).then(function(callback) {}, function(err, event) {
                            event.preventDefault();
                        });
                    } else {
                        return false;
                    }
                } else {
                    rpc.query({
                        model: 'restaurant.table',
                        method: 'write',
                        args: [
                            [table_id], table_vals
                        ],
                    }).then(function(callback) {}, function(err, event) {
                        event.preventDefault();
                    });
                }
                if (actual_reserved_seat <= 0) {
                    self.gui.show_popup('alert', {
                        title: _t('Warning !'),
                        body: _t("You must be add some person in this table"),
                    });
                    flag = false;
                    return false;
                }
                this.checked = false;
            });
            if (self.re_assign && !self.delivery && flag) { //flag not 
                this.re_assign(self, selection_name, selection_id, reserved_seat, select_tables);
            }
        },
        re_assign: function(pos, selection_name, selection_id, reserved_seat, select_tables) {
            var self = pos;
            var tabel_screen = this;
            var booked_selected_table = $("#booked_table option").filter(':selected').val();
            booked_selected_table = booked_selected_table.toString().replace('_,', '_');
            if (booked_selected_table) {
                if (self.option_value == "re_assign_order" && !self.is_any_checked_table) {
                    self.gui.show_popup('alert', {
                        title: _t('Warning !'),
                        body: _t('Please select table , without table user can not make order.'),
                    });
                    return false;
                }
                var items = $("#booked_table option:selected").map(function() {
                    return $(this).attr('item');
                }).get();
                items.join();
                var items_id = $("#booked_table option:selected").map(function() {
                    return $(this).attr('id');
                }).get();
                items_id.join();
                var re_assign_orders = false;
                var merge_orders = false
                for (var i = 0; i < self.attributes.orders.models.length; i++) {
                    order = _.clone(self.attributes.orders.models[i]);
                    var template = '<span class="order-sequence">' + order.sequence_number + '</span>'
                        /*Reassign Order code */
                    if (order && $("#booked_table option").filter(':selected').val() == order.attributes.reserved_seat &&
                        items_id.indexOf(order.name.toString().replace(' ', '_')) != -1 &&
                        !order.attributes.pflag && !$(".marge_table").is(":checked")) {
                        rpc.query({
                            model: 'pos.order',
                            method: 'reassign_table',
                            args: [booked_selected_table],
                        })
                        _.each(order.attributes.table_ids, function(id) {
                            rpc.query({
                                model: 'restaurant.table',
                                method: 'write',
                                args: [
                                    [id], {
                                        "state": "available"
                                    }
                                ],
                            })


                        });
                        $("#" + order.name.replace(' ', '_')).attr("name", selection_name);
                        $("#" + order.name.replace(' ', '_')).attr("item", selection_name);
                        $("#" + order.name.replace(' ', '_')).attr("data", reserved_seat);
                        $("#" + order.name.replace(' ', '_')).html(template + selection_name);
                        order.set('reserved_seat', reserved_seat);
                        order.set('creationDate', selection_name);
                        order.set('table_ids', selection_id);
                        order.set('table_data', select_tables);
                        order.set('offline_order', false);
                        re_assign_orders = order;
                        var send_order_to_kitchen = {
                            'data': re_assign_orders.export_as_JSON()
                        };
                        rpc.query({
                            model: 'pos.order',
                            method: 'create_from_ui',
                            args: [
                                [send_order_to_kitchen], true
                            ],
                        }).done(function(order_id) {
                            re_assign_orders.set('id', order_id[0]);
                            for (idx in re_assign_orders.orderlines.models) {
                                re_assign_orders.orderlines.models[idx].ol_flag = false;
                                re_assign_orders.orderlines.models[idx].flag = false;
                                re_assign_orders.orderlines.models[idx].line_id = order_id[1][idx];
                            }
                        });
                        self.gui.show_screen('products');
                    } else if (self.option_value == "merge_order") { /*Merge Order code */
                        var table_name = (items.toString().replace(',', ' ') + selection_name).trim();
                        table_name += ' ';
                        if (order && booked_selected_table == order.attributes.reserved_seat &&
                            items_id.indexOf(order.name.toString().replace(' ', '_')) != -1) {
                            if (selection_name) {
                                $("#" + order.name.replace(' ', '_')).attr("data", order.attributes.reserved_seat + reserved_seat);
                                $("#" + order.name.replace(' ', '_')).attr("name", table_name);
                                $("#" + order.name.replace(' ', '_')).attr("item", table_name);
                                $("#" + order.name.replace(' ', '_')).html(template + table_name);
                                order.set('creationDate', table_name);
                                order.set('reserved_seat', order.attributes.reserved_seat + reserved_seat);
                                order.set('offline_order', false);
                                _.each(selection_id, function(id) {
                                    order.attributes.table_ids.push(id);
                                });
                                _.each(select_tables, function(data) {
                                    order.attributes.table_data.push(data);
                                });
                                self.set('selectedOrder', self.attributes.orders.models[i]);
                                merge_orders = order;
                                var send_order_to_kitchen = {
                                    'data': order.export_as_JSON()
                                };
                                rpc.query({
                                    model: 'pos.order',
                                    method: 'create_from_ui',
                                    args: [
                                        [send_order_to_kitchen], true
                                    ],
                                }).done(function(order_id) {
                                    merge_orders.set('id', order_id[0]);
                                    for (idx in merge_orders.orderlines.models) {
                                        merge_orders.orderlines.models[idx].ol_flag = false;
                                        merge_orders.orderlines.models[idx].flag = false;
                                        merge_orders.orderlines.models[idx].line_id = order_id[1][idx];
                                    }
                                    tabel_screen.merge_order(self, merge_orders, table_name, items_id);
                                });
                            } else {
                                tabel_screen.merge_order(self, order, table_name, items_id)
                            }
                        }
                    }
                    self.gui.show_screen('products');
                }
            } else {
                self.gui.show_popup('alert', {
                    title: _t('Warning !'),
                    body: _t('Please select table , without table user can not make order.'),
                });
                return false;
            }
        },
        merge_order: function(pos, order, table_name, items_id) {
            var self = pos;
            for (var j = 0; j < self.get('orders').models.length; j++) {
                second_order = _.clone(self.get('orders').models[j]);
                second_order.attributes.state = 'draft';
                // if(order.attributes.user_id == second_order.attributes.user_id){
                if (second_order && second_order.attributes.creationDate && table_name.search(second_order.attributes.creationDate.trim(' ')) != -1 &&
                    items_id.indexOf(order.name.toString().replace(' ', '_')) != -1) {
                    if (second_order.partner_id && order.partner_id &&
                        (order.partner_id != second_order.partner_id)) {
                        self.gui.show_popup('alert', {
                            title: _t('Warning !'),
                            body: _t('Partner are not same! So can not Merge table!'),
                        });
                        return false;
                    } else if (second_order.user_id && order.user_id &&
                        (second_order.user_id != order.user_id)) {
                        self.gui.show_popup('alert', {
                            title: _t('Warning !'),
                            body: _t('Salesman are not same! So can not Merge table!'),
                        });
                        return false;
                    } else {
                        if (second_order.name != order.name) {
                            if (second_order.attributes.id && order.attributes.id) {
                                rpc.query({
                                    model: 'pos.order',
                                    method: 'remove_order',
                                    args: [
                                        [order.attributes.id], second_order.attributes.id
                                    ],
                                }).then(function(callback) {
                                    if (callback) {
                                        order.orderlines.add(second_order.orderlines.models);
                                        var template = '<span class="order-sequence">' + order.sequence_number + '</span>'
                                        $("#" + order.name.replace(' ', '_')).attr("data", order.attributes.reserved_seat + second_order.attributes.reserved_seat);
                                        $("#" + order.name.replace(' ', '_')).html(template + table_name);
                                        $("#" + order.name.replace(' ', '_')).attr("name", table_name);
                                        $("#" + order.name.replace(' ', '_')).attr("item", table_name);
                                        _.each(second_order.attributes.table_ids, function(id) {
                                            order.attributes.table_ids.push(id);
                                        });
                                        order.set('reserved_seat', order.attributes.reserved_seat + second_order.attributes.reserved_seat);
                                        order.set('creationDate', table_name);
                                        _.each(second_order.attributes.table_data, function(data) {
                                            order.attributes.table_data.push(data);
                                        });
                                        order.set('offline_order', false);
                                        self.set('selectedOrder', self.attributes.orders.models[i]);
                                        var send_order_to_kitchen = {
                                            'data': order.export_as_JSON()
                                        };
                                        rpc.query({
                                            model: 'pos.order',
                                            method: 'create_from_ui',
                                            args: [
                                                [send_order_to_kitchen], true
                                            ],
                                        }).done(function(order_id) {
                                            order.set('id', order_id[0]);
                                            for (idx in order.orderlines.models) {
                                                order.orderlines.models[idx].ol_flag = false;
                                                order.orderlines.models[idx].flag = false;
                                                order.orderlines.models[idx].line_id = order_id[1][idx];
                                            }
                                        });
                                        second_order.destroy();
                                        //new instance.web.DataSet(this, 'pos.order').unlink([second_order.attributes.id]);
                                    }
                                });
                            } else if (second_order.attributes.id && !order.attributes.id) {
                                second_order.orderlines.add(order.orderlines.models);
                                var template = '<span class="order-sequence">' + second_order.sequence_number + '</span>'
                                $("#" + second_order.name.replace(' ', '_')).attr("data", second_order.attributes.reserved_seat + order.attributes.reserved_seat);
                                $("#" + second_order.name.replace(' ', '_')).html(template + table_name);
                                $("#" + second_order.name.replace(' ', '_')).attr("name", table_name);
                                $("#" + second_order.name.replace(' ', '_')).attr("item", table_name);
                                _.each(order.attributes.table_ids, function(id) {
                                    second_order.attributes.table_ids.push(id);
                                });
                                second_order.set('creationDate', table_name);
                                second_order.set('reserved_seat', second_order.attributes.reserved_seat + order.attributes.reserved_seat);
                                _.each(order.attributes.table_data, function(data) {
                                    second_order.attributes.table_data.push(data);
                                });
                                second_order.set('offline_order', false);
                                self.set('selectedOrder', second_order);
                                var send_order_to_kitchen = {
                                    'data': second_order.export_as_JSON()
                                };
                                rpc.query({
                                    model: 'pos.order',
                                    method: 'create_from_ui',
                                    args: [
                                        [send_order_to_kitchen], true
                                    ],
                                }).done(function(order_id) {
                                    second_order.set('id', order_id[0]);
                                    for (idx in second_order.orderlines.models) {
                                        second_order.orderlines.models[idx].ol_flag = false;
                                        second_order.orderlines.models[idx].flag = false;
                                        second_order.orderlines.models[idx].line_id = order_id[1][idx];
                                        second_order.orderlines.models[idx].read_only = true
                                    }
                                });
                                order.destroy();
                            } else {
                                order.orderlines.add(second_order.orderlines.models);
                                var template = '<span class="order-sequence">' + order.sequence_number + '</span>'
                                $("#" + order.name.replace(' ', '_')).attr("data", order.attributes.reserved_seat + second_order.attributes.reserved_seat);
                                $("#" + order.name.replace(' ', '_')).html(template + table_name);
                                $("#" + order.name.replace(' ', '_')).attr("name", table_name);
                                $("#" + order.name.replace(' ', '_')).attr("item", table_name);
                                _.each(second_order.attributes.table_ids, function(id) {
                                    order.attributes.table_ids.push(id);
                                });
                                order.set('creationDate', table_name);
                                order.set('reserved_seat', order.attributes.reserved_seat + second_order.attributes.reserved_seat);
                                $("#" + order.name.replace(' ', '_')).attr("name", table_name);
                                _.each(second_order.attributes.table_data, function(data) {
                                    order.attributes.table_data.push(data);
                                });
                                order.set('offline_order', false);
                                self.set('selectedOrder', order);
                                var send_order_to_kitchen = {
                                    'data': order.export_as_JSON()
                                };
                                rpc.query({
                                    model: 'pos.order',
                                    method: 'create_from_ui',
                                    args: [
                                        [send_order_to_kitchen], true
                                    ],
                                }).done(function(order_id) {
                                    order.set('id', order_id[0]);
                                    for (idx in order.orderlines.models) {
                                        order.orderlines.models[idx].ol_flag = false;
                                        order.orderlines.models[idx].flag = false;
                                        order.orderlines.models[idx].line_id = order_id[1][idx];
                                    }
                                });
                                second_order.destroy();
                            }
                        }
                    }
                }
                //  }
            }
        },
    });
    gui.define_screen({
        'name': 'reassign_table_screen',
        'widget': ReassignTableScreenWidget
    });
    screens.ReceiptScreenWidget.include({
        show: function() {
            this.chrome.widget.order_selector.hide();
            this._super();
        },
        hide: function() {
            this.chrome.widget.order_selector.show();
            this._super();
        },
    });

    function set_ui_widget_overlay() {
        $(window).unbind('resize').bind('resize', function() {
            $(".ui-widget-overlay").height($(document).height() + 15);
        });
    }
    PosDB.include({
        add_table_order: function(order) {
            var order_id = order.uid;
            var orders = this.load('table_orders', []);
            var serialized = order.export_as_JSON();
            // if the order was already stored, we overwrite its data
            for (var i = 0, len = orders.length; i < len; i++) {
                if (orders[i].id === order_id) {
                    orders[i].data = order;
                    this.save('table_orders', orders);
                    return order_id;
                }
            }
            orders.push({
                id: order_id,
                data: serialized
            });
            this.save('table_orders', orders);
            return order_id;
        },
        get_table_orders: function() {
            var saved = this.load('table_orders', []);
            var orders = [];
            for (var i = 0; i < saved.length; i++) {
                orders.push(saved[i].data);
            }
            return orders;
        },
        remove_table_order: function(order) {
            var orders = this.load('table_orders', []);
            orders = _.filter(orders, function(o) {
                return o.id !== order.uid;
            });
            this.save('table_orders', orders);
        },
        remove_all_table_orders: function() {
            this.save('table_orders', []);
        },
        save_unpaid_update_order: function(order) {
            var order_id = order.uid;
            var orders = this.load('unpaid_orders', []);
            var serialized = order;
            for (var i = 0; i < orders.length; i++) {
                if (orders[i].id === order_id) {
                    orders[i].data = serialized;
                    this.save('unpaid_orders', orders);
                    return order_id;
                }
            }
            return order_id;
        },
    });
    var pos_manager_dataset = new data.DataSetSearch(this, 'res.users', {}, []);
    // pos_manager_dataset.call('has_group', ['point_of_sale.group_pos_manager'])
    // var args = ['point_of_sale.group_pos_manager']
    rpc.query({
            model: 'res.users',
            method: 'has_group',
            args: ['point_of_sale.group_pos_manager'],
        })
        .then(function(result) {
            is_admin = result;
            if (!result) {
                screens.ActionpadWidget.include({
                    renderElement: function() {
                        var self = this;
                        this._super();
                        this.$('.pay').addClass("confirm_pay");
                        this.$('.pay').off("click");
                        this.$('.pay').removeClass("pay");
                        this.$('.confirm_pay').css('height', '162px');
                        this.$('.confirm_pay').html(" <div class='pay-circle'> <i class='fa fa-chevron-right' /> </div> Confirm");
                        this.$('.confirm_pay').click(function() {
                            if (self.pos.attributes.selectedOrder.orderlines.models == '') {
                                self.gui.show_popup('alert', {
                                    title: _t('Warning !'),
                                    body: _t('Can not create order which have no order line.'),
                                });
                                return false;
                            } else {
                                var order = [];
                                var current_order = self.pos.get_order();
                                // var posOrderModel = new Model('pos.order');
                                current_order.attributes.confirm_order = true;
                                current_order.set_confirm_receipt(true);
                                order.push({
                                        'data': current_order.export_as_JSON()
                                    })
                                    // posOrderModel.call('create_from_ui', [order, true])
                                rpc.query({
                                        model: 'pos.order',
                                        method: 'create_from_ui',
                                        args: [order, true],
                                    })
                                    .then(function(callback) {
                                        current_order.attributes.id = callback[0];
                                        for (idx in current_order.orderlines.models) {
                                            current_order.orderlines.models[idx].line_id = callback[1][idx];
                                            current_order.orderlines.models[idx].set_line_id(callback[1][idx]);
                                        }
                                        current_order.kitchen_receipt = false;
                                        current_order.customer_receipt = true;
                                        current_order.confirm_receipt = true;
                                        if (self.pos.config.iface_print_via_proxy) {
                                            var receipt = current_order.export_for_printing();
                                            self.pos.proxy.print_receipt(QWeb.render('XmlReceipt', {
                                                widget: self,
                                                pos: self.pos,
                                                receipt: receipt,
                                                order: current_order,
                                                orderlines: current_order.orderlines.models,
                                                paymentlines: current_order.get_paymentlines(),
                                            }));
                                            current_order.destroy({
                                                'reason': 'abandon'
                                            });
                                        } else {
                                            self.gui.show_screen('receipt');
                                        }
                                    }, function(err, event) {
                                        event.preventDefault();
                                        var current_order = self.pos.get_order();
                                        current_order.attributes.confirm_order = true;
                                        current_order.attributes.offline_confirm_order = true;
                                        self.set('offline_confirm_order', true)
                                        self.pos.push_order(current_order);
                                        setTimeout(function() {
                                            current_order.destroy({
                                                'reason': 'abandon'
                                            });
                                        }, 300);
                                    });
                            }
                        });

                    }
                });
            }
        });
    screens.ActionButtonWidget.include({
        renderElement: function() {
            var self = this;
            this._super();
            self.$el.unbind('click').bind('click', function() {
                if (!is_admin) {
                    if ($(this).attr('id') && $(this).attr('id').trim('') == 'order-split-button') {
                        self.gui.show_popup('alert', {
                            title: _t('Warning !'),
                            body: _t('You do not have access.Please Contact Administator.'),
                        });
                    } else {
                        self.button_click();
                    }
                } else {
                    self.button_click();
                }
            })
        },
    });
    var UnpaidOrdersWidget = screens.ScreenWidget.extend({
        template: "UnpaidOrdersWidget",
        init: function(parent, options) {
            this._super(parent, options);
            var self = this;
        },
        hide: function() {
            this._super();
            $("#order-selector").show();
            $("#options").show();
            $(".pos-leftpane").show();
            $(".rightpane").removeClass("full_screen");
            $("#synch_order").show();
            $(".pos-rightheader").show();
            this.chrome.widget.order_selector.show();
        },
        show: function() {
            this._super();
            $("#order-selector").hide();
            $("#options").hide();
            $("#synch_order").hide();
            $(".pos-leftpane").hide();
            $(".rightpane").addClass("full_screen");
            $(".pos-rightheader").hide();
            this.chrome.widget.order_selector.hide();
        },
        renderElement: function() {
            var self = this;
            var left = 40
            var top = 40
            var check_limit = []
            _.each(self.pos.get('orders').models, function(order) {
                order.attributes.order_color = "rgb(53, 211, 116)"
                if (check_limit.length == 8) {
                    check_limit = []
                    top = top + 85
                    left = 40
                }
                check_limit.push(order.attributes.creationDate);
                top = top;
                order.attributes.left = left + 'px';
                order.attributes.top = top + 'px';
                left = left + 145;
            })
            this._super();
            var self = this;
            this.$('.reserved_order_label').click(function(event) {
                self.click_reserved_node(event, $(this));
            });
        },
        click_reserved_node: function(event, $el) {
            var self = this
            data = $el.attr('data')
            _.each(self.pos.get('orders').models, function(order) {
                if (order.name == data) {
                    self.gui.show_screen('products')
                    self.pos.set({
                        'selectedOrder': order
                    });
                }
            })
        },
        reserved_table_string: function(name) {
            var str = (name.replace(/\d+/g, ''));
            return str
        },
        reserved_table_number: function(order) {
            var reserved_table = '';
            _.each(this.pos.table_details, function(table, index) {
                if (order.get('table_ids').indexOf(table.id) != -1) {
                    var num = Number((table.name.match(/\d+/g) || [])[0] || 0);
                    if (reserved_table.length != 0) {
                        reserved_table = reserved_table + ','
                    }
                    reserved_table = reserved_table + num
                }
            });
            return reserved_table
        }
    });
    gui.define_screen({
        'name': 'unpaid_orders_screen',
        'widget': UnpaidOrdersWidget
    });
    screens.OrderWidget.include({
        update_summary: function() {
            var order = this.pos.get_order();
            if (!order || !order.get_orderlines().length) {
                return;
            }

            var total = order ? order.get_total_with_tax() : 0;
            var taxes = order ? total - order.get_total_without_tax() : 0;

            this.el.querySelector('.summary .total > .value').textContent = this.format_currency(total);
            this.el.querySelector('.summary .total .subentry .value').textContent = this.format_currency(taxes);
            var changes = this.pos.get_order().hasChangesToPrint();
            var skipped = changes ? false : this.pos.get_order().hasSkippedChanges();
            var buttons = this.getParent().action_buttons;

            if (buttons && buttons.submit_order) {
                buttons.submit_order.highlight(changes);
                buttons.submit_order.altlight(skipped);
            }
        },
    });
    chrome.Chrome.include({
        build_widgets: function() {
            this._super();
            this.do_call_recursive();
        },
        offline_orders: function(db_orders, options) {
            var self = this;
            push_order_call = true;
            self.pos._flush_offline_order(db_orders, options).done(function(server_ids) {
                var pending = self.pos.db.get_orders().length;
                self.pos.set('synch', {
                    state: pending ? 'connecting' : 'connected',
                    pending: pending
                });
                $.unblockUI();
            });
        },
        do_call_recursive: function() {
            var self = this;
            var order_ids = [];
            // var posOrderModel = new models('pos.order');
            _.each(this.pos.attributes.orders.models, function(order) {
                if (order.attributes.id) {
                    order_ids.push(order.attributes.id);
                    clearInterval(self[order.uid]);
                    $("span[data-uid=" + order.uid + "]").closest("span").css({
                        "visibility": "visible"
                    });
                }
            });
            if (order_ids != []) {
                rpc.query({
                    model: 'pos.order',
                    method: 'get_done_orderline',
                    args: [order_ids],
                }).then(function(callback) {
                    var unpaid_orders = self.pos.db.get_unpaid_orders();
                    if (unpaid_orders.length != 0) {
                        var order_ids_to_sync = _.omit(_.indexBy(unpaid_orders, 'offline_order_name'), 'false', 'undefined');
                        if (_.size(order_ids_to_sync) != 0) {
                            $.blockUI();
                            var table_vals = {};
                            _.each(order_ids_to_sync, function(order, key) {
                                if (order.table_data && order.table_data.length > 0) {
                                    if (!order.split_order) {
                                        _.each(order.table_data, function(table_record) {
                                            if (_.has(table_vals, table_record.table_id)) {
                                                table_vals[table_record.table_id] = parseInt(table_vals[table_record.table_id]) + parseInt(table_record.reserver_seat);
                                            } else {
                                                table_vals[table_record.table_id] = parseInt(table_record.reserver_seat);
                                            }
                                        });
                                    }
                                }
                            });
                            // var restaurant_table_model =  new models('restaurant.table');
                            // restaurant_table_model.call("update_offline_table_order", [table_vals]).done(function(){
                            rpc.query({
                                model: 'restaurant.table',
                                method: 'update_offline_table_order',
                                args: [table_vals],
                            }).done(function() {
                                $.unblockUI();
                                var table_vals = {};
                                _.each(order_ids_to_sync, function(order, key) {
                                    if (order.table_data && order.table_data.length > 0) {
                                        _.each(order.table_data, function(table_record) {
                                            if (_.has(table_vals, table_record.table_id)) {
                                                table_vals[table_record.table_id] = parseInt(table_vals[table_record.table_id]) + parseInt(table_record.reserver_seat);
                                            } else {
                                                table_vals[table_record.table_id] = parseInt(table_record.reserver_seat);
                                            }
                                        });
                                        order.offline_order_name = false;
                                        self.pos.db.save_unpaid_update_order(order);
                                    }
                                });
                                _.each(table_vals, function(val, table_id) {
                                    var table_res = {
                                        'available_capacities': val
                                    };
                                    for (var i = 0; i < self.pos.table_details.length; i++) {
                                        if (self.pos.table_details[i].id === parseInt(table_id)) {
                                            var final_capacity = parseInt(self.pos.table_details[i].available_capacities) + parseInt(table_res.available_capacities);
                                            self.pos.table_details[i].available_capacities = final_capacity;
                                            if (parseInt(self.pos.table_details[i].capacities) - final_capacity === 0) {
                                                self.pos.table_details[i].state = 'reserved';
                                            }
                                            break;
                                        }
                                    }
                                });
                                if (self.gui.get_current_screen() == 'floors') {
                                    self.gui.screen_instances.floors.renderElement();
                                }
                            })
                        } else {
                            if (self.gui.get_current_screen() == 'floors') {
                                self.gui.screen_instances.floors.renderElement();
                            }
                        }
                    } else {
                        if (self.gui.get_current_screen() == 'floors') {
                            self.gui.screen_instances.floors.renderElement();
                        }
                    }

                    var db_table_orders = self.pos.db.get_table_orders();
                    var db_orders = self.pos.db.get_orders();
                    if (db_table_orders.length != 0 && db_orders.length != 0) {
                        $.blockUI();
                        // var restaurant_table_model =  new models('restaurant.table');
                        // restaurant_table_model.call("remove_delete_table_order", [db_table_orders]).then(function(callback){
                        rpc.query({
                            model: 'restaurant.table',
                            method: 'remove_delete_table_order',
                            args: [db_table_orders],
                        }).then(function(callback) {
                            self.pos.db.remove_all_table_orders();
                            self.offline_orders(db_orders, options);
                        }).fail(function(error, event) {
                            event.preventDefault();
                            self.offline_orders(db_orders, options);
                        });
                    } else if (db_table_orders.length != 0) {
                        $.blockUI();
                        // var restaurant_table_model =  new models('restaurant.table');
                        // restaurant_table_model.call("remove_delete_table_order", [db_table_orders]).then(function(callback){
                        rpc.query({
                            model: 'restaurant.table',
                            method: 'remove_delete_table_order',
                            args: [db_table_orders],
                        }).then(function(callback) {
                            $.unblockUI();
                            self.pos.db.remove_all_table_orders();
                        }).fail(function(error, event) {
                            $.unblockUI();
                            event.preventDefault();
                        });
                    } else if (db_orders.length != 0) {
                        if (self.gui.get_current_screen() != 'payment' && self.gui.get_current_screen() != 'receipt') {
                            $.blockUI();
                            self.offline_orders(db_orders, options);
                        }
                    } else {
                        //$.unblockUI();
                    }
                    _.each(self.pos.attributes.orders.models, function(order) {
                        if (callback) {
                            _.each(callback, function(ord) {
                                if (ord.id == order.attributes.id) {
                                    var set = false;
                                    self[order.uid] = setInterval(function() {
                                        $("span[data-uid=" + order.uid + "]").closest("span").css({
                                            "visibility": set ? "hidden" : "visible",
                                        });
                                        set = !set;
                                    }, 800);
                                }
                            });
                        }
                    });
                }, function(err, event) {
                    event.preventDefault();
                });
                setTimeout(function() {
                    self.do_call_recursive()
                }, 10000)
            } else {
                setTimeout(function() {
                    self.do_call_recursive()
                }, 10000)
            }
        },
    });
    screens.PaymentScreenWidget.include({
        order_is_valid: function(force_validation) {
            var self = this;
            var order = this.pos.get_order();

            // FIXME: this check is there because the backend is unable to
            // process empty orders. This is not the right place to fix it.
            if (order.get_orderlines().length === 0) {
                this.gui.show_popup('error', {
                    'title': _t('Empty Order'),
                    'body': _t('There must be at least one product in your order before it can be validated'),
                });
                return false;
            }

            if (!order.is_paid() || this.invoicing) {
                return false;
            }
            var plines = order.get_paymentlines();
            for (var i = 0; i < plines.length; i++) {
                if (plines[i].get_type() === 'bank' && plines[i].get_amount() <= 0) {
                    this.gui.show_popup('error', {
                        'title': _t('Negative Bank Payment'),
                        'body': _t('You cannot have a negative amount in a Bank payment. Use a cash payment method to return money to the customer.'),
                    });
                    return false;
                }
                if (plines[i].get_type() === 'cash' && plines[i].get_amount() == 0) {
                    this.gui.show_popup('error', {
                        'title': _t('Payment'),
                        'body': _t('Please remove 0 amount line.'),
                    });
                    return false;
                }
            }
            // The exact amount must be paid if there is no cash payment method defined.
            if (Math.abs(order.get_total_with_tax() - order.get_total_paid()) > 0.00001) {
                var cash = false;
                for (var i = 0; i < this.pos.cashregisters.length; i++) {
                    cash = cash || (this.pos.cashregisters[i].journal.type === 'cash');
                }
                if (!cash) {
                    this.gui.show_popup('error', {
                        title: _t('Cannot return change without a cash payment method'),
                        body: _t('There is no cash payment method available in this point of sale to handle the change.\n\n Please pay the exact amount or add a cash payment method in the point of sale configuration'),
                    });
                    return false;
                }
            }
            return true;
        },
        show: function() {
            this.chrome.widget.order_selector.hide();
            this._super();
        },
        hide: function() {
            this.chrome.widget.order_selector.show();
            this._super();
        },
    });
})