odoo.define('hotel.RoomPricelist', function(require) {
    "use strict";

    var core = require('web.core');
    var FieldOne2Many = require('web.relational_fields').FieldOne2Many;
    var fieldRegistry = require('web.field_registry');
    var ListRenderer = require('web.ListRenderer');
    var rpc = require('web.rpc');

    var _t = core._t;
    var QWeb = core.qweb;

    var RoomPricelistListRenderer = ListRenderer.extend({
        events: {
            'click .oe_room_pricelist_weekly a': 'go_to',
            'change input': '_onFieldChanged',
            'keyup .validate_input': '_onInputKeyUp',
        },

        init: function(parent, state, params) {
            var self = this;
            this._super.apply(this, arguments);
            this.set({
                sheets: {},
                room_sheet: {},
                line_sheet: {},
                date_from: false,
                date_to: false,
                company_id: false,
                room_id: {},
                hotel: {},
            });
            this.date_from = parent.recordData.date_from;
            this.date_to = parent.recordData.date_to;
            this.mode = parent.mode;
            self.rendered = false;
        },

        setRowMode: function(recordID, mode) {
            return $.when();
        },

        _selectCell: function(rowIndex, fieldIndex, options) {
            return $.when();
        },

        _render: function() {
            var self = this;
            rpc.query({
                model: 'hotel.room',
                method: 'search_read',
                domain: [
                    ['active', '=', 'True']
                ],
            }).then(function(result) {
                self.rooms_types = result;
                self.$widget = $(QWeb.render('hotel_room_availability.RoomPricelist', {
                    widget: self
                }));
                if (!self.rendered) {
                    self.rendered = true;
                    self.$el.html('');
                    self.$widget.appendTo(self.$el);
                    _.each(result, function(room) {
                        self.get_room_data(room.id);
                    });
                    self.$el.parent().find('.o_cp_pager').hide();
                }
            });
        },

        start: function() {
            var self = this;
            this._super.apply(this, arguments);
            var dates = [];
            var start = self.date_from;
            var end = self.date_to;
            while (start <= end) {
                dates.push(start);
                var m_start = moment(start).add(1, 'days');
                start = m_start.toDate();
            }
            self.dates = dates;
        },

        get_room_data: function(room_id) {
            var self = this;
            var data_row = document.getElementById("room_name-" + room_id);
            if (!$(data_row).hasClass('rendered')) {
                var day_count = 0;
                rpc.query({
                    model: 'hotel_reservation.line',
                    method: 'get_room_price_from_daterange',
                    args: [
                        room_id, moment(self.date_from).format('YYYY-MM-DD'), moment(self.date_to).format('YYYY-MM-DD')
                    ],
                }).then(function(result) {
                    _.each(self.dates, function(date) {
                        var room_data = _.find(result, function(data) {
                            return data.date == moment(date).format('YYYY-MM-DD');
                        });
                        if (typeof room_data !== "undefined") {
                            // First Row
                            var price_cell = data_row.insertCell();
                            var cell = '';
                            if (self.mode == 'readonly') {
                                cell = '<span style="color:#000;" class="oe_timesheet_weekly_box oe_timesheet_weekly_input" data-day-count="' + day_count + '" data-room="' + room_id + '">' + room_data.price + '</span>'
                            } else {
                                cell = '<input style="color:#000;" data-date="' + room_data.date + '" ' + ((date < new Date()) ? 'readonly=""' : '') + ' name="room_price" class="oe_timesheet_weekly_input validate_input" type="text" data-day-count="' + day_count + '" data-room="' + room_id + '" value="' + room_data.price + '">';
                            }
                            price_cell.innerHTML = cell;
                            $(price_cell).addClass('input_td')

                            if (room_data.price > 0) {
                                $(price_cell).addClass('bg-success')
                            } else {
                                $(price_cell).addClass('bg-danger')
                            }
                            day_count++;
                        }
                    });

                    var total_rowprice_cell = data_row.insertCell();
                    $(total_rowprice_cell).addClass('total_rowprice_cell bg-default');
                    $(total_rowprice_cell).attr('data-room', room_id);
                    self.display_rowprice(room_id)

                    self.style_caption(room_id);
                    $(data_row).addClass('rendered');
                });

                if (!self.mode == 'readonly') {
                    $(document).on('change', '.close_checkbox', function(event) {
                        event.preventDefault();
                        var room_qty = $('.oe_timesheet_weekly_input[data-room="' + $(this).data('room') + '"][data-day-count="' + $(this).data('day-count') + '"]');
                        self.style_checkbox($(this).data('day-count'), $(this).data('room'));
                        if ($(this).data('origin') !== $(this).prop('checked') && !room_qty.hasClass('value_changed')) {
                            $(this).addClass('value_changed');
                        } else {
                            $(this).removeClass('value_changed');
                        }
                        // self.set_o2m_values();
                    });
                    $(document).on('change', '.oe_timesheet_weekly_input', function(event) {
                        event.preventDefault();
                        var close = $('.close_checkbox[data-room="' + $(this).data('room') + '"][data-day-count="' + $(this).data('day-count') + '"]');
                        if ($(this).data('origin') != $(this).val() && !close.hasClass('value_changed')) {
                            $(this).addClass('value_changed');
                        } else {
                            $(this).removeClass('value_changed');
                        }
                        // self.set_o2m_values();
                        self.display_total_qty($(this).data('room'));
                        self.display_booked_qty($(this).data('room'));
                        self.display_avail_qty($(this).data('room'));
                        var booked = $('.booked_rooms[data-room="' + $(this).data('room') + '"][data-day-count="' + $(this).data('day-count') + '"]').text();
                        var avail = parseInt($(this).val()) - parseInt(booked)
                        $('.avail_rooms[data-room="' + $(this).data('room') + '"][data-day-count="' + $(this).data('day-count') + '"]').text(avail)
                    });
                }
            }
        },

        display_rowprice: function(room_id) {
            var self = this;
            var total = 0;
            if (self.mode == 'readonly') {
                _.each($(".oe_timesheet_weekly_input[data-room='" + room_id + "']"), function(input) {
                    total += parseInt($(input).text());
                });
            } else {
                _.each($(".oe_timesheet_weekly_input[data-room='" + room_id + "']"), function(input) {
                    total += parseInt($(input).val());
                });
            }
            $(".total_rowprice_cell[data-room='" + room_id + "']").html(total);
        },

        style_caption: function(room_id) {
            var name_row = $("#room_caption-" + room_id);
            $('head').append("<style>#room_name-" + room_id + "::before{ content:'Room'; overflow: hidden; text-overflow: ellipsis; padding-top: calc(" + name_row.parents().outerHeight() + "px - 3rem); width: " + (name_row.outerWidth() + (name_row.next().outerWidth() * 2)) + "px !important; height: " + name_row.parents().outerHeight() + "px !important; }</style>");
        },

        _onInputKeyUp: function(ev) {
            if (isNaN(ev.currentTarget.value)) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
            } else if ((parseInt(ev.currentTarget.value) < 0) || ev.currentTarget.value.length > 9) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
            }
        },

        _onFieldChanged: function(ev) {
            var self = this;

            if (isNaN(ev.currentTarget.value)) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
                return;
            } else if ((parseInt(ev.currentTarget.value) < 0) || ev.currentTarget.value.length > 9) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
                return;
            }

            var datas = self.state.data;
            var dataset = ev.currentTarget.dataset;
            var value = ev.target.value;
            var res_date = dataset.date;
            var res_room_id = parseInt(dataset.room);
            var prev_data = _.find(datas, function(data) {
                return moment(data.data.date).format('YYYY-MM-DD') == res_date && data.data.room_id.res_id == res_room_id
            });

            var args = {
                default_room_price: value,
                default_room_id: res_room_id,
                default_date: res_date,
            }

            if (prev_data !== undefined) {
                self.unselectRow().then(function() {
                    self.trigger_up('list_record_remove', {
                        id: prev_data.id
                    });
                    self.trigger_up('add_record', {
                        context: args && [args]
                    });
                });
            } else {
                self.unselectRow().then(function() {
                    self.trigger_up('add_record', {
                        context: args && [args]
                    });
                });
            }

            self.display_rowprice(res_room_id);
        },

        _date_changed(date_from, date_to) {
            var self = this;
            self.rendered = false;
            self.date_from = date_from;
            self.date_to = date_to
            self.start();
        }

    });

    var RoomPricelistFieldOne2Many = FieldOne2Many.extend({
        /**
         * We want to use our custom renderer for the list.
         *
         * @override
         */
        _getRenderer: function() {
            if (this.view.arch.tag === 'tree') {
                return RoomPricelistListRenderer;
            }
            return this._super.apply(this, arguments);
        },

        reset: function(record, ev, fieldChanged) {
            if (!fieldChanged) {
                this.renderer._date_changed(record.data.date_from, record.data.date_to);
            }
            return this._super.apply(this, arguments);
        },

    });

    fieldRegistry.add('RoomPricelist', RoomPricelistFieldOne2Many);
});
