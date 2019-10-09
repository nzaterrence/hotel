odoo.define("pos_kot_receipt.pos_kot_receipt", function(require) {

    var bus = require('bus.BusService');
    var core = require('web.core');
    var rpc = require('web.rpc')
    var screens = require('point_of_sale.screens');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var PosDB = require('point_of_sale.DB');
    var models = require('point_of_sale.models');
    var data = require('web.data');
    var session = require('web.session')
    var chrome = require('point_of_sale.chrome');
    var pop_up = require('point_of_sale.popups');
    var gui = require('point_of_sale.gui');
    var QWeb = core.qweb;
    var _t = core._t;
    // var logo_barcode =  session.module_list
    var is_pos_logo_barcode_receipt = _.contains(session.module_list, 'pos_logo_barcode_receipt');
    var SendToKitchenButton = PosBaseWidget.extend({
        template: 'SendToKitchenButton',
    });

    var CustomerReceiptButton = PosBaseWidget.extend({
        template: 'CustomerReceiptButton',
    });

    var KitchenReceiptButton = PosBaseWidget.extend({
        template: 'KitchenReceiptButton',
    });

    var AddSequence = PosBaseWidget.extend({
        template: 'AddSequence',
    })

    models.PosModel.prototype.models.push({
        model: 'pos.category',
        fields: ['id', 'name', 'parent_id', 'child_id', 'image'],
        domain: null,
        loaded: function(self, categories) {
            self.categories = categories;
            rpc.query({
                model: 'pos.category',
                method: 'get_root_of_category',
                args: [],
            }).done(function(root_category_data) {
                self.root_category = root_category_data;
            });
        },
    });

    var _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        delete_current_order: function() {
            var order = this.get_order();
            // var posOrderModel = new models('pos.order');
            if (order) {
                var self = this;
                if (order.attributes.id) {
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
                            self.push_order(order);
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
                        var restaurant_table_model = new models('restaurant.table');
                        if (!order.attributes.split_order) {
                            rpc.query({
                                model: 'restaurant.table',
                                method: 'remove_table_order',
                                args: [table_details],
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
                    }
                    order.destroy({
                        'reason': 'abandon'
                    });
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
    });



    var SquencePopupWidget = pop_up.extend({
        template: 'SquencePopupWidget',
        show: function(options) {
            options = options || {};
            var self = this;
            this._super();
            this.options = options;
            this.title = options.title;
            this.category_data = options.category_data
            this.send_to_kitchen = options.send_to_kitchen || false;
            this.orderlines = [];
            this.orderlines = self.pos.get('selectedOrder').orderlines.models;
            this.renderElement();
            self.hotkey_handler = function(event) {
                if (event.which === 27) {
                    self.gui.close_popup();
                }
            };
            $('body').on('keyup', self.hotkey_handler);
        },
        click_confirm: function() {
            this.gui.close_popup();
            if (this.options.confirm) {
                this.options.confirm.call(this);
            }
        },
        close: function() {
            this._super();
            $('body').off('keyup', this.hotkey_handler);
        },
    });
    gui.define_popup({
        name: 'sequence_popup',
        widget: SquencePopupWidget
    });

    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function() {
            var self = this
            self.set({
                'id': null,
            })
            _super_order.initialize.apply(this, arguments);
        },
        init_from_JSON: function(json) {
            _super_order.init_from_JSON.apply(this, arguments);
            var self = this;
            self.attributes.id = json.id;
        },
        add_product: function(product, options) {
            this._printed = false;
            _super_order.add_product.apply(this, arguments);
        },
        export_as_JSON: function(json) {
            var json = _super_order.export_as_JSON.apply(this, arguments);
            var self = this;
            json.id = self.attributes.id;
            json.creation_date = self.validation_date || self.creation_date;
            return json;
        },
        export_for_printing: function() {
            var json = _super_order.export_for_printing.apply(this, arguments);
            if (is_pos_logo_barcode_receipt) {
                json.company_logo = this.pos.company_logo_base64
            }
            return json;
        },
        get_table_name: function() {
            if (this.get('creationDate')) {
                return this.get('creationDate');
            } else {
                return false
            }
        },
    });

    var _super_order_line = models.Orderline.prototype;
    var temporary_sequence_number = 1;
    models.Orderline = models.Orderline.extend({
        initialize: function() {
            this.temporary_sequence_number = temporary_sequence_number++;
            this.sequence_number = 1;
            _super_order_line.initialize.apply(this, arguments);
        },
        init_from_JSON: function(json) {
            _super_order_line.init_from_JSON.apply(this, arguments);
            var self = this;
            self.line_id = json.line_id;
            self.order_line_state_id = json.order_line_state_id
        },
        export_for_printing: function() {
            var json = _super_order_line.export_for_printing.apply(this, arguments);
            json.quantity_str_with_unit = this.get_quantity_str_with_unit();
            return json;
        },
        set_line_id: function(line_id) {
            this.line_id = line_id;
            this.trigger('change', this);
        },
        export_as_JSON: function(json) {
            var json = _super_order_line.export_as_JSON.apply(this, arguments);
            var self = this;
            json.line_id = self.line_id;
            json.order_line_state_id = 1
            return json;
        },
    });

    var ActionpadWidget = PosBaseWidget.extend({
        template: 'ActionpadWidget',
        init: function(parent, options) {
            var self = this;
            this._super(parent, options);
            this.pos.bind('change:selectedClient', function() {
                self.renderElement();
            });
        },
        renderElement: function() {
            var self = this;
            $('.pay').unbind('click').bind('click', function() {
                var currentOrder = self.pos.get('selectedOrder');
                currentOrder.kitchen_receipt = false;
                currentOrder.customer_receipt = false;
                self.gui.show_screen('payment');
            });
            this._super();
        }
    });

    screens.ProductScreenWidget.include({
        start: function() {
            var self = this;
            this._super();
            this.actionpad = new ActionpadWidget(this, {});
            this.SendToKitchenButton = new SendToKitchenButton(this, {});
            this.SendToKitchenButton.appendTo(this.$('.placeholder-OptionsListWidget .option_list_box_container'));

            this.CustomerReceiptButton = new CustomerReceiptButton(this, {});
            this.CustomerReceiptButton.appendTo(this.$('.placeholder-OptionsListWidget .option_list_box_container'));

            this.KitchenReceiptButton = new KitchenReceiptButton(this, {});
            this.KitchenReceiptButton.appendTo(this.$('.placeholder-OptionsListWidget .option_list_box_container'));

            this.AddSequence = new AddSequence(this, {});
            this.AddSequence.appendTo(this.$('.placeholder-OptionsListWidget .option_list_box_container'));

            this.$(".send_to_kitchen_button").on('click', function() {
                self.send_to_kitchen();
            });

            this.$(".customer_receipt_button").on('click', function() {
                self.customer_receipt();
            });

            this.$(".kitchen_receipt_button").on('click', function() {
                self.kitchen_receipt();
            });

            this.$(".add_sequence").on('click', function() {
                self.add_sequence();
            });
        },
        send_to_kitchen: function() {
            var self = this;
            if (self.pos.attributes.selectedOrder.orderlines.models == '') {
                self.gui.show_popup('alert', {
                    title: _t('Warning !'),
                    body: _t('Can not create order which have no order line.'),
                });
                return false;
            } else {
                var order = [];
                var current_order = this.pos.get_order();
                // var posOrderModel = new models('pos.order');
                order.push({
                    'data': current_order.export_as_JSON()
                })
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
                    }, function(err, event) {
                        event.preventDefault();
                    });
                setTimeout(function() {
                    self.gui.show_popup('alert', {
                        title: _t('Successful'),
                        warning_icon: false,
                        body: _t('Order send to the kitchen successfully!'),
                    });
                }, 300);
            }
        },
        kitchen_receipt: function() {
            var self = this;
            var currentOrder = self.pos.get('selectedOrder');
            if (self.pos.attributes.selectedOrder.orderlines.models == '') {
                self.gui.show_popup('alert', {
                    title: _t('Warning !'),
                    body: _t('Can not Print order which have no order line.'),
                });
                return false;
            } else {
                self.gui.show_screen('kitchen_receipt');
            }
        },
        customer_receipt: function() {
            var self = this;
            if (self.pos.attributes.selectedOrder.orderlines.models == '') {
                self.gui.show_popup('alert', {
                    title: _t('Warning !'),
                    warning_icon: true,
                    body: _t('Can not Print order which have no order line.'),
                });
                return false;
            } else {
                self.gui.show_screen('customer_receipt');
            }
        },
        category_data: function() {
            var self = this;
            var currentOrder = self.pos.get('selectedOrder');
            var duplicate_root_category_id = [];
            var res = [];
            _.each(self.pos.get('selectedOrder').orderlines.models, function(line) {
                var root_category_id;
                var root_category_name;
                if (!line.product.pos_categ_id || self.pos.root_category[line.product.pos_categ_id[0]] == undefined) {
                    root_category_id = 'Undefined';
                    root_category_name = 'Undefined'
                } else if (line.product.pos_categ_id && !self.pos.root_category[line.product.pos_categ_id[0]].root_category_name) {
                    root_category_id = self.pos.root_category[line.product.pos_categ_id[0]].categ_id;
                    root_category_name = self.pos.root_category[line.product.pos_categ_id[0]].categ_name;
                } else {
                    root_category_id = self.pos.root_category[line.product.pos_categ_id[0]].root_category_id ;
                    root_category_name = self.pos.root_category[line.product.pos_categ_id[0]].root_category_name;
                }
                if (duplicate_root_category_id.indexOf(root_category_id) == -1) {
                    duplicate_root_category_id.push(root_category_id);
                    res.push({
                        'id': root_category_id,
                        'name': root_category_name,
                        'data': [{
                            'product': line.product,
                            'qty': line.quantity,
                            'sequence_number': line.sequence_number,
                            'temporary_sequence_number': line.temporary_sequence_number
                        }]
                    })
                } else {
                    _.each(res, function(record) {
                        if (record['id'] == root_category_id) {
                            product_categ_data = [];
                            product_categ_data = record['data'];
                            product_categ_data.push({
                                'product': line.product,
                                'qty': line.quantity,
                                'sequence_number': line.sequence_number,
                                'temporary_sequence_number': line.temporary_sequence_number
                            });
                            record['data'] = product_categ_data;
                        }
                    });
                }
            });
            return res;
        },
        add_sequence: function() {
            var self = this;
            if (self.pos.attributes.selectedOrder.orderlines.models == '') {
                self.gui.show_popup('alert', {
                    title: _t('Warning !'),
                    warning_icon: true,
                    body: _t('Can not create order which have no order line.'),
                });
                return false;
            } else {
                self.gui.show_popup('sequence_popup', {
                    title: _t('Orderline Sequence'),
                    send_to_kitchen: true,
                    category_data: self.category_data(),
                    'confirm': function(value) {
                        var dict = {}
                        $('#sequence_data tr input').each(function(index) {
                            var temporary_sequence_number_value = $(this).attr('temporary_sequence_number');
                            dict[temporary_sequence_number_value] = $("#sequence_data tr input[temporary_sequence_number=" + temporary_sequence_number_value + "]").val()
                        })
                        _.each(self.pos.get('selectedOrder').orderlines.models, function(line) {
                            line.sequence_number = parseInt(dict[line.temporary_sequence_number])
                        });
                        self.pos.get('selectedOrder').orderlines.models.sort(function(a, b) {
                            return a['sequence_number'] - b['sequence_number'];
                        });
                    },
                });
            }
        },
    });

    screens.NumpadWidget.include({
        clickDeleteLastChar: function() {
            var self = this;
            var order = this.pos.get('selectedOrder');
            if (order.selected_orderline != undefined) {
                if (order.selected_orderline.line_id && self.state.get('mode') != 'price' && self.state.get('mode') != 'discount') {
                    rpc.query({
                        model: 'pos.order.line',
                        method: 'orderline_state_id',
                        args: [order.selected_orderline.line_id, order.attributes.id],
                    }).then(function(state_id) {
                        if (state_id == 1) {
                            self.pos_orderline_dataset = new data.DataSetSearch(self, 'pos.order.line', {}, []);
                            self.pos_orderline_dataset.unlink([order.selected_orderline.line_id]);
                            return self.state.deleteLastChar();
                        } else if (state_id == 'cancel') {
                            return self.state.deleteLastChar();
                        } else if (state_id != 1) {
                            self.gui.show_popup('alert', {
                                title: _t('Warning'),
                                warning_icon: true,
                                body: _t('Current orderline is not remove'),
                            });
                            return false;
                        }
                    });
                } else {
                    return this._super.apply(this);
                }
            } else {
                return this._super.apply(this);
            }
        },
    });

    screens.ReceiptScreenWidget.include({
        click_back: function() {
            this.gui.show_screen('products');
        },
        show: function() {
            this._super();
            var self = this;
            var order = this.pos.get_order()
            var is_confirm_receipt = order.confirm_receipt;
            var is_kitchen = order.kitchen_receipt;
            if (!is_kitchen) {
                if (!order.customer_receipt) {
                    this.$('.next').show();
                    this.$('.back').hide();
                    this.$('.change-value').parent().show();
                } else {
                    this.$('.next').hide();
                    this.$('.change-value').parent().hide();
                    this.$('.back').show();
                    if (is_confirm_receipt) {
                        this.$('.next').show();
                        this.$('.change-value').parent().show();
                        this.$('.back').hide();
                        self.pos.db.remove_unpaid_order(order);
                    }
                }
            } else {
                this.$('.next').hide();
                this.$('.change-value').parent().hide();
            }
        },
        renderElement: function() {
            var self = this;
            this._super();
            this.$('.back').click(function() {
                self.click_back();
            });
        },
    });

    var splitBillScreenWidget;
    var pos_config_dataset = new data.DataSet(this, 'pos.config', {}, []);
    pos_config_dataset.call('check_is_pos_restaurant').done(function(result) {
        if (result) {
            if (result) {
                _.each(gui.Gui.prototype.screen_classes, function(screen_class) {
                    if (screen_class.name == "splitbill") {
                        splitBillScreenWidget = screen_class;
                    }
                });
                splitBillScreenWidget.widget.include({
                    renderElement: function() {
                        var order = this.pos.get_order();
                        if (!order) {
                            return;
                        }
                        order.kitchen_receipt = false;
                        order.customer_receipt = false;
                        this._super();
                    },
                    pay: function(order, neworder, splitlines) {
                        var orderlines = order.get_orderlines();
                        var empty = true;
                        var full = true;
                        var self = this;
                        for (var i = 0; i < orderlines.length; i++) {
                            var id = orderlines[i].id;
                            var split = splitlines[id];
                            if (!split) {
                                full = false;
                            } else {
                                if (split.quantity) {
                                    empty = false;
                                    if (split.quantity !== orderlines[i].get_quantity()) {
                                        full = false;
                                    }
                                }
                            }
                        }
                        if (empty) {
                            return;
                        }
                        if (full) {
                            neworder.destroy({
                                'reason': 'abandon'
                            });
                            this.gui.show_screen('payment');
                        } else {
                            for (var id in splitlines) {
                                var split = splitlines[id];
                                var line = order.get_orderline(parseInt(id));
                                line.set_quantity(line.get_quantity() - split.quantity);
                                if (Math.abs(line.get_quantity()) < 0.00001) {
                                    order.remove_orderline(line);
                                }
                                if (line.line_id != undefined) {
                                    var data = require('web.data');
                                    self.pos_line = new data.DataSetSearch(self, 'pos.order.line');
                                    self.pos_line.unlink(line.line_id)
                                }
                                delete splitlines[id];
                            }
                            neworder.set_screen_data('screen', 'payment');
                            // for the kitchen printer we assume that everything
                            // has already been sent to the kitchen before splitting 
                            // the bill. So we save all changes both for the old 
                            // order and for the new one. This is not entirely correct 
                            // but avoids flooding the kitchen with unnecessary orders. 
                            // Not sure what to do in this case.
                            if (neworder.saveChanges) {
                                order.saveChanges();
                                neworder.saveChanges();
                            }
                            neworder.set_customer_count(1);
                            order.set_customer_count(order.get_customer_count() - 1);
                            $.ajax({
                                type: 'GET',
                                success: function() {
                                    neworder.set('offline_order', false);
                                    neworder.set('offline_order_name', false)
                                    self.pos.db.save_unpaid_order(neworder);
                                },
                                error: function(XMLHttpRequest, textStatus, errorThrown) {
                                    neworder.set('offline_order', true);
                                    neworder.set('offline_order_name', neworder.name)
                                    self.pos.db.save_unpaid_order(neworder);
                                }
                            });
                            // self.pos.db.save_unpaid_order(neworder);
                            this.pos.get('orders').add(neworder);
                            this.pos.set('selectedOrder', neworder);
                            this.gui.show_screen('payment');
                        }
                    },
                    show: function() {
                        var self = this;
                        screens.ScreenWidget.prototype.show.call(this)
                        this.renderElement();
                        var order = this.pos.get_order();
                        var neworder = new models.Order({}, {
                            pos: this.pos,
                            temporary: true,
                        });
                        neworder.set('client', order.get('client'));
                        neworder.set('pflag', order.get('pflag'));
                        neworder.set('parcel', order.get('parcel'));
                        neworder.set('pricelist_id', order.get('pricelist_id'));
                        neworder.set('phone', order.get('phone'));
                        neworder.set('partner_id', order.get('partner_id'));
                        neworder.set('driver_name', order.get('driver_name'));
                        neworder.set('creationDate', order.get('creationDate'));
                        neworder.set('table_data', order.get('table_data'));
                        neworder.set('table', order.get('table'));
                        neworder.set('table_ids', order.get('table_ids'));
                        neworder.set('split_order', true);
                        //   neworder.trigger('change',neworder)

                        var splitlines = {};
                        this.$('.orderlines').on('click', '.orderline', function() {
                            var id = parseInt($(this).data('id'));
                            var $el = $(this);
                            self.lineselect($el, order, neworder, splitlines, id);
                        });
                        this.$('.paymentmethods .button').click(function() {
                            self.pay(order, neworder, splitlines);
                        });
                        this.$('.back').unbind('click').bind('click', function() {
                            neworder.destroy({
                                'reason': 'abandon'
                            });
                            self.gui.show_screen(self.previous_screen);
                        });
                    },
                });
            }
        }
    });

    chrome.Chrome.include({
        build_widgets: function() {
            this._super();
            var self = this;
            self.call('bus_service', 'onNotification', self, self.on_notification);
            var channel = JSON.stringify([odoo.session_info.db, 'pos.order', odoo.session_info.uid]);
            self.call('bus_service', 'addChannel', channel);
            self.call('bus_service', 'startPolling');
        },
        on_notification: function(notification) {
            var self = this;
            var order_id = false
            var channel = notification[0] ? notification[0][0] ? notification[0][0] : false : false;
            var message = notification[0] ? notification[0][1] ? notification[0][1] : false : false;
            if ((Array.isArray(channel) && (channel[1] === 'pos.order'))) {
                if (message) {
                    order_id = message['order_id'];
                }
            }
            var all_orders = self.pos.get('orders').models;
            for (var i = 0; i < all_orders.length; i++) {
                if (parseInt(order_id) == parseInt(all_orders[i].get('id'))) {
                    all_orders[i].destroy();
                }
            }
        }
    });

    PosDB.include({
        get_table_orders: function() {
            var saved = this.load('table_orders', []);
            var orders = [];
            for (var i = 0; i < saved.length; i++) {
                orders.push(saved[i].data);
            }
            return orders;
        },
    });

    var KitchenReceiptScreenWidget = screens.ScreenWidget.extend({
        template: 'KitchenReceiptScreen',
        show: function() {
            this._super();
            var self = this;
            this.render_receipt();
        },
        print_xml: function() {
            var env = {
                widget: this,
                pexport_for_printingos: this.pos,
                order: this.pos.get_order(),
                receipt: this.pos.get_order().export_for_printing(),
                paymentlines: this.pos.get_order().get_paymentlines(),
                orderlines: this.pos.get_order().orderlines.models,
            };
            var receipt = QWeb.render('kitchen_receipt', env);
            this.pos.proxy.print_receipt(receipt);
        },
        renderElement: function() {
            var self = this;
            this._super();
            this.$('.next').click(function() {
                if (!self._locked) {
                    self.click_next();
                }
            });
            this.$('.button.print').click(function() {
                window.print();
            });
        },
        click_next: function() {
            this.gui.show_screen('products');
        },
        render_receipt: function() {
            var order = this.pos.get_order();
            _.each(order.orderlines.models, function(order_line) {
                order_line.categ_name = "All";
                order_line.product_name = order_line.product.display_name;
                order_line.print_qty = order_line.quantity;
                order_line.print = true;
                order_line.ol_flag = false;
            });
            if (!this.pos.config.iface_print_via_proxy) {
                this.$('.Kitchen-receipt-container').html(QWeb.render('KitchenReceiptTicket', {
                    widget: this,
                    order: order,
                    receipt: order.export_for_printing(),
                    orderlines: order.get_orderlines(),
                    paymentlines: order.get_paymentlines(),
                }));
            } else {
                this.print_xml();
            }
        },
    });
    gui.define_screen({
        name: 'kitchen_receipt',
        widget: KitchenReceiptScreenWidget
    });

    var CustomerReceiptScreenWidget = screens.ScreenWidget.extend({
        template: 'CustomerReceiptScreen',
        show: function() {
            this._super();
            var self = this;
            this.render_receipt();
        },
        print_xml: function() {
            var env = {
                widget: this,
                pos: this.pos,
                order: this.pos.get_order(),
                receipt: this.pos.get_order().export_for_printing(),
                paymentlines: this.pos.get_order().get_paymentlines()
            };
            var receipt = QWeb.render('CustomerReceipt', env);
            this.pos.proxy.print_receipt(receipt);
        },
        renderElement: function() {
            var self = this;
            this._super();
            this.$('.next').click(function() {
                if (!self._locked) {
                    self.click_next();
                }
            });
            this.$('.button.print').click(function() {
                window.print();
            });
        },
        click_next: function() {
            this.gui.show_screen('products');
        },
        render_receipt: function() {
            var order = this.pos.get_order();
            _.each(order.orderlines.models, function(order_line) {
                order_line.categ_name = "All";
                order_line.product_name = order_line.product.display_name;
                order_line.print_qty = order_line.quantity;
                order_line.print = true;
                order_line.ol_flag = false;
            });
            if (!this.pos.config.iface_print_via_proxy) {
                this.$('.Customer-receipt-container').html(QWeb.render('CustomerReceiptTicket', {
                    widget: this,
                    order: order,
                    receipt: order.export_for_printing(),
                    orderlines: order.get_orderlines(),
                    paymentlines: order.get_paymentlines(),
                }));
            } else {
                this.print_xml();
            }
        },
    });
    gui.define_screen({
        name: 'customer_receipt',
        widget: CustomerReceiptScreenWidget
    });

});