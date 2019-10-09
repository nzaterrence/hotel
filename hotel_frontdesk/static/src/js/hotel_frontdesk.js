odoo.define('hotel_frontdesk.HotelFrontdeskView', function(require) {
    "use strict";

    var AbstractAction = require('web.AbstractAction');
    var ajax = require('web.ajax');
    var ControlPanelMixin = require('web.ControlPanelMixin');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var field_utils = require('web.field_utils');
    var session = require('web.session');
    var web_client = require('web.web_client');

    var _t = core._t;
    var _lt = core._lt;
    var QWeb = core.qweb;

    var HotelFrontdesk = AbstractAction.extend({

        init: function(parent, context) {
            this._super(parent, context);
            this.gantt_chart = {}
            this.model = 'hotel.frontdesk';
        },

        willStart: function() {
            var self = this;
            return $.when(ajax.loadLibs(this), this._super()).then(function() {
                return self.fetch_data();
            });
        },

        start: function() {
            var self = this;
            return this._super().then(function() {
                self.render_frontdesk();
            });
        },

        fetch_data: function() {
            // Overwrite this function with useful data
            return $.when();
        },

        format_value: function(value) {
            return field_utils.format.date(field_utils.parse.date(value, {}, {
                isUTC: true
            }))
        },

        parse_value: function(value) {

            var d = new Date(value),
                month = '' + (d.getMonth() + 1),
                day = '' + d.getDate(),
                year = d.getFullYear();

            if (month.length < 2) month = '0' + month;
            if (day.length < 2) day = '0' + day;

            return [year, month, day].join('-');

            // return field_utils.parse.date(value, {}, {
            //     isUTC: true
            // }).format("YYYY-MM-DD");
        },

        render_frontdesk: function() {
            var self = this;
            return this.fetch_data().then(function(result) {
                var frontedesk = QWeb.render('hotel_frontdesk.HotelFrontdesk', {
                    widget: self,
                    values: result,
                });
                $(frontedesk).prependTo(self.$el);
                self.$el.find('.gantt-target').width($(document).find('.o_main').width() - 15);
                self.init_frontdesk_view(self.$el.find('.gantt-target'));
                // $(document).find('.o_cp_left').remove();
            });
        },

        init_frontdesk_view: function(gantt_target) {
            var self = this;
            var frontdesk_tasks = [];
            var frontdesk_tasks_call = this._rpc({
                model: this.model,
                method: 'room_detail',
            }).done(function(details) {
                if (details.length <= 0) {
                    var start = new Date().toISOString().substr(0, 10);
                    var end = new Date().toISOString().substr(0, 10);

                    var ganttdata = {
                        start: start,
                        end: end,
                        name: "",
                        id: 'Task 0',
                        custom_class: "no-data",
                        invalid: true,
                    };
                    details.push(ganttdata);
                } else {
                    _.each(details, function(task) {
                        task.progress = 100;
                        if (task.title_row !== null && task.title_row) {
                            task.custom_class = 'title_row'
                            task.id = 'Title-' + task.room_id
                            task.title = task.room_name
                            task.title_row = true
                            task.resid = 'Title-' + task.room_id
                        }
                        if (task.state == 'assigned') {
                            task.custom_class = 'state_assigned'
                            task.done = false
                            task.state = 'Booked'
                        } else if (task.state == 'reserved') {
                            task.custom_class = 'state_reserved'
                            task.done = false
                            task.state = 'Reserved'
                        } else if (task.state == 'done') {
                            task.custom_class = 'state_done'
                            task.state = 'Done'
                            task.done = true
                        }
                    });
                }
                self.gantt_chart = new Gantt(gantt_target[0], details, {
                    // on_click: function(task) {
                    //     gantt_target.html('');
                    //     self.init_frontdesk_view(gantt_target)
                    // },
                    on_date_change: function(task, start, end) {
                        self._rpc({
                            model: self.model,
                            method: 'get_date_change_rate',
                            args: [
                                task.room_id,
                                self.parse_value(start),
                                self.parse_value(end),
                            ]
                        }).done(function(result) {
                            var $content = `
                                    <div class='row'>
                                        <div class='col-md-6'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-danger font-bold'> Old Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4>
                                                        <strong>Room : </strong> ${task.title}
                                                    </h4>
                                                    <h4 class='data_changed_source'>
                                                        <strong>Date : </strong> ${self.format_value(task.start)} <strong> - To - </strong> ${self.format_value(task.end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${task.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${task.price_unit} </h5>
                                                        <h4 class='amount_change_src'>
                                                            <strong>Amount : </strong> ${task.price_subtotal}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class='col-md-6' style='border-left:1px solid #eee'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-success font-bold'> New Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4>
                                                        <strong>Room : </strong> ${task.title}
                                                    </h4>
                                                    <h4 class='data_changed_dest'>
                                                        <strong>Date : </strong> ${self.format_value(start)} <strong> - To - </strong> ${self.format_value(end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${result.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${result.new_unit_price} </h5>
                                                        <h4 class='amount_change_dest'>
                                                            <strong>Amount : </strong> ${result.new_total_price}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    `;
                            var dialog = new Dialog(this, {
                                title: _t('Change Date'),
                                buttons: [{
                                        text: _t('Save'),
                                        classes: 'btn-primary',
                                        close: true,
                                        click: function() {
                                            if (task.folio_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel.folio.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.folio_line_id)], {
                                                            checkin_date: self.format_value(start),
                                                            checkout_date: self.format_value(end),
                                                            price_unit: result.new_unit_price,
                                                            price_subtotal: result.new_total_price,
                                                            product_uom_qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)],
                                                            {
                                                                check_in: self.format_value(start),
                                                                check_out: self.format_value(end),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED DATE move");
                                                        // window.location.reload();
                                                        // self.gantt_chart.refresh(details);
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                            if (task.reservation_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel_reservation.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.reservation_line_id)],
                                                        {
                                                            checkin: self.format_value(start),
                                                            checkout: self.format_value(end),
                                                            price_unit: result.new_unit_price,
                                                            // price_subtotal: result.new_total_price,
                                                            // qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)],
                                                            {
                                                                check_in: self.format_value(start),
                                                                check_out: self.format_value(end),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED DATE move");
                                                        // window.location.reload();
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                        }
                                    },
                                    {
                                        text: _t('Discard'),
                                        close: true,
                                    }
                                ],
                                $content: $content,
                            }).open();
                            dialog.on('closed', self, function () {
                                gantt_target.html('');
                                self.init_frontdesk_view(gantt_target)
                            });
                        });
                    },

                    on_vertical_change: function(task, old_title, new_task_resid) {
                        self._rpc({
                            model: self.model,
                            method: 'get_date_change_rate',
                            args: [
                                new_task_resid.resid,
                                self.parse_value(task.start),
                                self.parse_value(task.end),
                            ]
                        }).done(function(result) {
                            var $content = `
                                    <div class='row'>
                                        <div class='col-md-6'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-danger font-bold'> Old Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4 class='data_changed_source'>
                                                        <strong>Room : </strong> ${old_title}
                                                    </h4>
                                                    <h4>
                                                        <strong>Date : </strong> ${self.format_value(task.start)} <strong> - To - </strong> ${self.format_value(task.end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${task.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${task.price_unit} </h5>
                                                        <h4 class='amount_change_src'>
                                                            <strong>Amount : </strong> ${task.price_subtotal}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class='col-md-6' style='border-left:1px solid #eee'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-success font-bold'> New Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4 class='data_changed_dest'>
                                                        <strong>Room : </strong> ${new_task_resid.title}
                                                    </h4>
                                                    <h4>
                                                        <strong>Date : </strong> ${self.format_value(task.start)} <strong> - To - </strong> ${self.format_value(task.end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${result.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${result.new_unit_price} </h5>
                                                        <h4 class='amount_change_dest'>
                                                            <strong>Amount : </strong> ${result.new_total_price}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    `;
                            var dialog = new Dialog(this, {
                                title: _t('Change Room'),
                                buttons: [{
                                        text: _t('Save'),
                                        classes: 'btn-primary',
                                        close: true,
                                        click: function() {
                                            if (task.folio_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel.folio.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.folio_line_id)], {
                                                            room_number_id: parseInt(new_task_resid.resid),
                                                            room_id: parseInt(new_task_resid.room_id),
                                                            price_unit: result.new_unit_price,
                                                            price_subtotal: result.new_total_price,
                                                            product_uom_qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)], {
                                                                room_number_id: parseInt(new_task_resid.resid),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED ROOM move");
                                                        // window.location.reload();
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                            if (task.reservation_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel_reservation.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.reservation_line_id)],
                                                        {
                                                            room_id: parseInt(new_task_resid.room_id),
                                                            room_number_id: parseInt(new_task_resid.resid),
                                                            price_unit: result.new_unit_price,
                                                            // price_subtotal: result.new_total_price,
                                                            // qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)],
                                                            {
                                                                room_number_id: parseInt(new_task_resid.resid),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED ROOM move");
                                                        // window.location.reload();
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                        }
                                    },
                                    {
                                        text: _t('Discard'),
                                        close: true,
                                    }
                                ],
                                $content: $content,
                            }).open();
                            dialog.on('closed', self, function () {
                                gantt_target.html('');
                                self.init_frontdesk_view(gantt_target)
                            });
                        });
                    },

                    on_vertically_date_change: function(task, old_title, new_task_resid, start, end) {
                        self._rpc({
                            model: self.model,
                            method: 'get_date_change_rate',
                            args: [
                                new_task_resid.resid,
                                self.parse_value(start),
                                self.parse_value(end),
                            ]
                        }).done(function(result) {
                            var $content = `
                                    <div class='row'>
                                        <div class='col-md-6'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-danger font-bold'> Old Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4 class='data_changed_source'>
                                                        <strong>Room : </strong> ${old_title}
                                                    </h4>
                                                    <h4 class='data_changed_source'>
                                                        <strong>Date : </strong> ${self.format_value(task.start)} <strong> - To - </strong> ${self.format_value(task.end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${task.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${task.price_unit} </h5>
                                                        <h4 class='amount_change_src'>
                                                            <strong>Amount : </strong> ${task.price_subtotal}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class='col-md-6' style='border-left:1px solid #eee'>
                                            <div class='text-center date_change_wizard'>
                                                <h2 class='text-success font-bold'> New Detail </h2>
                                                <div class='text-left change_wizard_block'>
                                                    <h4>
                                                        <strong> ${(task.reservation_id !== null) ? 'Reservation' : 'Folio'} No : </strong> ${task.seq_no}
                                                    </h4>
                                                    <h4>
                                                        <strong>Guest : </strong> ${task.name}
                                                    </h4>
                                                    <h4 class='data_changed_dest'>
                                                        <strong>Room : </strong> ${new_task_resid.title}
                                                    </h4>
                                                    <h4 class='data_changed_dest'>
                                                        <strong>Date : </strong> ${self.format_value(start)} <strong> - To - </strong> ${self.format_value(end)}
                                                    </h4>
                                                    <div class='col-md-offset-4 text-right mr-25'>
                                                        <h5 class='data_changed_dest_sub'> <strong> Qty : </strong> ${result.qty} </h5>
                                                        <h5 class='data_changed_dest_sub' style='border-bottom: 1px solid #eee;'> <strong> Rate : </strong> ${result.new_unit_price} </h5>
                                                        <h4 class='amount_change_dest'>
                                                            <strong>Amount : </strong> ${result.new_total_price}
                                                        </h4>
                                                    </div>
                                                    <div class='col-md-offset-1'></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    `;
                            var dialog = new Dialog(this, {
                                title: _t('Change Room'),
                                buttons: [{
                                        text: _t('Save'),
                                        classes: 'btn-primary',
                                        close: true,
                                        click: function() {
                                            if (task.folio_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel.folio.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.folio_line_id)],
                                                        {
                                                            room_number_id: parseInt(new_task_resid.resid),
                                                            checkin_date: self.format_value(start),
                                                            checkout_date: self.format_value(end),
                                                            room_id: parseInt(new_task_resid.room_id),
                                                            price_unit: result.new_unit_price,
                                                            price_subtotal: result.new_total_price,
                                                            product_uom_qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)],
                                                            {
                                                                room_number_id: parseInt(new_task_resid.resid),
                                                                check_in: self.format_value(start),
                                                                check_out: self.format_value(end),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED ROOM move");
                                                        // window.location.reload();
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                            if (task.reservation_line_id !== null) {
                                                self._rpc({
                                                    model: 'hotel_reservation.line',
                                                    method: 'write',
                                                    args: [
                                                        [parseInt(task.reservation_line_id)], {
                                                            room_number_id: parseInt(new_task_resid.resid),
                                                            checkin: self.format_value(start),
                                                            checkout: self.format_value(end),
                                                            room_id: parseInt(new_task_resid.room_id),
                                                            price_unit: result.new_unit_price,
                                                            // price_subtotal: result.new_total_price,
                                                            // qty: result.qty,
                                                        }
                                                    ]
                                                }).done(function() {
                                                    self._rpc({
                                                        model: 'hotel.room.move.line',
                                                        method: 'write',
                                                        args: [
                                                            [parseInt(task.id)], {
                                                                room_number_id: parseInt(new_task_resid.resid),
                                                                check_in: self.format_value(start),
                                                                check_out: self.format_value(end),
                                                            }
                                                        ]
                                                    }).done(function() {
                                                        // console.log("UPDATED ROOM move");
                                                        // window.location.reload();
                                                    }).fail(function() {
                                                        gantt_target.html('');
                                                        self.init_frontdesk_view(gantt_target)
                                                    });
                                                }).fail(function() {
                                                    gantt_target.html('');
                                                    self.init_frontdesk_view(gantt_target)
                                                });
                                            }
                                        }
                                    },
                                    {
                                        text: _t('Discard'),
                                        close: true,
                                    }
                                ],
                                $content: $content,
                            }).open();
                            dialog.on('closed', self, function () {
                                gantt_target.html('');
                                self.init_frontdesk_view(gantt_target)
                            });
                        });
                    },

                    // on_progress_change: function(task, progress) {
                    //     console.log(task, progress);
                    // },

                    custom_popup_html: function(task) {
                        return `
                <div class="details-container">
                  <h5 class="text-center"><strong>Guest: &nbsp; &nbsp;</strong>${task.name}</h5>
                  <hr class="popup-hr"/>
                  <p><b>Room: &nbsp; &nbsp;</b>${task.title}</p>
                  <p><b>Status: &nbsp; &nbsp;</b>${task.state}</p>
                  <p><b>Arrival: &nbsp; &nbsp; </b>${self.format_value(task.start)}</p>
                  <p><b>Departure: &nbsp; &nbsp;</b>${self.format_value(task.end)}</p>
                </div>
          `;
                    },
                    header_height: 50,
                    column_width: 30,
                    step: 24,
                    view_modes: ['Day', 'Week', 'Month'],
                    bar_height: 25,
                    bar_corner_radius: 3,
                    padding: 18,
                    view_mode: 'Day',
                    date_format: 'YYYY-MM-DD',
                    language: 'en',
                });

                $(".bar-wrapper[data-id='Task 0']").remove(); // remove bar made by sample data

                $(document).on('click', '.btn_day_filter', function(event) {
                    event.preventDefault();
                    self.gantt_chart.change_view_mode('Day');
                    _.each(self.$el.find('.frontdesk_filter_btn'), function(btn) {
                        if ($(btn).hasClass('btn_day_filter')) {
                            $(btn).attr('disabled', true);
                        } else {
                            $(btn).attr('disabled', false);
                        }
                    });
                });

                $(document).on('click', '.btn_week_filter', function(event) {
                    event.preventDefault();
                    self.gantt_chart.change_view_mode('Week')
                    _.each(self.$el.find('.frontdesk_filter_btn'), function(btn) {
                        if ($(btn).hasClass('btn_week_filter')) {
                            $(btn).attr('disabled', true);
                        } else {
                            $(btn).attr('disabled', false);
                        }
                    });
                });

                $(document).on('click', '.btn_month_filter', function(event) {
                    event.preventDefault();
                    self.gantt_chart.change_view_mode('Month');
                    _.each(self.$el.find('.frontdesk_filter_btn'), function(btn) {
                        if ($(btn).hasClass('btn_month_filter')) {
                            $(btn).attr('disabled', true);
                        } else {
                            $(btn).attr('disabled', false);
                        }
                    });
                });
            });
        },

    })

    core.action_registry.add('hotel_frontdesk', HotelFrontdesk);

    return HotelFrontdesk;
});
