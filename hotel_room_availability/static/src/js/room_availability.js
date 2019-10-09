odoo.define('hotel.RoomAvailabilityView', function(require) {
    "use strict";

    var core = require('web.core');
    var FieldOne2Many = require('web.relational_fields').FieldOne2Many;
    var fieldRegistry = require('web.field_registry');
    var ListRenderer = require('web.ListRenderer');
    var rpc = require('web.rpc');

    var _t = core._t;
    var QWeb = core.qweb;

    var RoomAvailabilityListRenderer = ListRenderer.extend({
        events: {
            'click .oe_room_availability_weekly a': 'go_to',
            'change input': '_onFieldChanged',
            'click .accordian_btn': '_expand_room_detail',
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
                self.$widget = $(QWeb.render('hotel_room_availability.RoomAvailability', {
                    widget: self
                }));
                if (!self.rendered) {
                    self.rendered = true;
                    self.$el.html('');
                    self.$widget.appendTo(self.$el);
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

        _expand_room_detail: function(event) {
            var self = this;
            var target = event.target;
            if ($(target).hasClass('collapsed')) {
                $(target).removeClass('expanded_row').addClass('closed_row');
            } else if (!$(target).hasClass('collapsed')) {
                $(target).removeClass('closed_row').addClass('expanded_row');
                self.get_room_data($(target).data('room'));
            }
        },

        get_room_data: function(room_id) {
            var self = this;
            var name_row = document.getElementById("room_name-" + room_id);
            var closed_tr = document.getElementById("closed_tr-" + room_id);
            var booked_tr = document.getElementById("booked_tr-" + room_id);
            var avail_room_tr = document.getElementById("avail_room_tr-" + room_id);
            if (!$(name_row).hasClass('rendered')) {
                var day_count = 0;
                var sheet = self.get("sheets");
                rpc.query({
                    model: 'hotel_reservation.line',
                    method: 'get_room_value_from_daterange',
                    args: [
                        sheet[0], room_id, moment(self.date_from).format('YYYY-MM-DD'), moment(self.date_to).format('YYYY-MM-DD')
                    ],
                }).then(function(result) {
                    _.each(self.dates, function(date) {
                        var room_data = _.find(result, function(data) {
                            return data.date == moment(date).format('YYYY-MM-DD');
                        });
                        if (typeof room_data !== "undefined") {
                            // First Row
                            var name_cell = name_row.insertCell();
                            var cell = '';
                            if (self.mode == 'readonly') {
                                cell = '<span class="oe_timesheet_weekly_box oe_timesheet_weekly_input" data-day-count="' + day_count + '" data-room="' + room_id + '">' + room_data.total_qty + '</span>'
                            } else {
                                cell = '<input data-date="' + room_data.date + '" ' + ((date < new Date()) ? 'readonly=""' : '') + ' name="room_qty" data-close="' + room_data.closed + '" class="oe_timesheet_weekly_input validate_input" type="text" data-day-count="' + day_count + '" data-room="' + room_id + '" value="' + room_data.total_qty + '">';
                            }
                            name_cell.innerHTML = cell;
                            $(name_cell).addClass('input_td')

                            // Second Row
                            var closed_cell = closed_tr.insertCell();
                            var closed_cell_data = '';
                            var checked = room_data.closed;
                            if (self.mode == 'readonly') {
                                if (checked) {
                                    closed_cell_data = '<input class="close_checkbox" data-qty="' + room_data.total_qty + '" data-date="' + room_data.date + '" disabled="" data-origin="' + checked + '" checked="' + checked + '" type="checkbox" data-day-count="' + day_count + '" data-room="' + room_id + '"/>'
                                } else {
                                    closed_cell_data = '<input class="close_checkbox" data-qty="' + room_data.total_qty + '" data-date="' + room_data.date + '" disabled="" type="checkbox" data-origin="' + checked + '" data-day-count="' + day_count + '" data-room="' + room_id + '"/>'
                                }
                            } else {
                                if (checked) {
                                    closed_cell_data = '<input class="close_checkbox" ' + ((date < new Date()) ? 'readonly=""' : '') + ' data-qty="' + room_data.total_qty + '" data-date="' + room_data.date + '" checked="' + checked + '" type="checkbox" data-origin="' + checked + '" data-day-count="' + day_count + '" data-room="' + room_id + '"/>'
                                } else {
                                    closed_cell_data = '<input class="close_checkbox" ' + ((date < new Date()) ? 'readonly=""' : '') + ' data-qty="' + room_data.total_qty + '" data-date="' + room_data.date + '" type="checkbox" data-day-count="' + day_count + '" data-origin="' + checked + '" data-room="' + room_id + '"/>'
                                }
                            }
                            closed_cell.innerHTML = closed_cell_data;

                            // Third row
                            var booked_cell = booked_tr.insertCell();
                            var booked_cell_data = '';
                            booked_cell_data = '<span class="booked_rooms" data-day-count="' + day_count + '" data-room="' + room_id + '">' + room_data.booked + '</span>'
                            booked_cell.innerHTML = booked_cell_data;
                            $(booked_cell).addClass('pricelist_td')

                            // Fourth row
                            var avail_room_cell = avail_room_tr.insertCell();
                            var avail_cell_data = '';
                            avail_cell_data = '<span class="avail_rooms" data-day-count="' + day_count + '" data-room="' + room_id + '">' + room_data.avail + '</span>'
                            avail_room_cell.innerHTML = avail_cell_data;
                            if (room_data.avail > 0) {
                                $(avail_room_cell).addClass('bg-success')
                            } else {
                                $(avail_room_cell).addClass('bg-danger')
                            }

                            self.style_checkbox(day_count, room_id)
                            day_count++;
                        }
                    });
                    var total_qty_cell = name_row.insertCell();
                    $(total_qty_cell).addClass('total_qty_cell bg-default');
                    $(total_qty_cell).attr('data-room', room_id);
                    self.display_total_qty(room_id)

                    var total_checked_cell = closed_tr.insertCell();
                    $(total_checked_cell).addClass('total_checked_cell bg-default');

                    var total_booked_cell = booked_tr.insertCell();
                    $(total_booked_cell).addClass('total_booked_cell bg-default');
                    $(total_booked_cell).attr('data-room', room_id);
                    self.display_booked_qty(room_id)

                    var total_avail_cell = avail_room_tr.insertCell();
                    $(total_avail_cell).addClass('total_avail_cell bg-default');
                    $(total_avail_cell).attr('data-room', room_id);
                    self.display_avail_qty(room_id)

                    self.style_caption(room_id, $(total_qty_cell).outerHeight(), $(total_checked_cell).outerHeight(), $(total_booked_cell).outerHeight(), $(total_avail_cell).outerHeight());
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
                $(name_row).addClass('rendered');
            }
        },

        style_checkbox: function(day_count, room_id) {
            var input = $('.oe_timesheet_weekly_input[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').parent();
            var booked = $('.booked_rooms[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').parent();
            var available = $('.avail_rooms[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').parent();
            var checked = $('.close_checkbox[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').prop('checked');
            if (checked) {
                $('.close_checkbox[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').parent().css({
                    "background-color": "grey",
                    "color": "white"
                });
                $(input).css({
                    "background-color": "grey",
                });
                $(booked).css({
                    "background-color": "grey",
                    "color": "white"
                });
                $(available).css({
                    "background-color": "grey",
                    "color": "white"
                });
            } else {
                $('.close_checkbox[data-room="' + room_id + '"][data-day-count="' + day_count + '"]').parent().removeAttr("style");
                $(input).removeAttr("style");
                $(booked).removeAttr("style");
                $(available).removeAttr("style");
            }
        },

        style_caption: function(room_id, name_height, check_height, booked_height, avail_height) {
            var name_row = $("#room_caption-" + room_id);
            var closed_tr = $("#closed_caption-" + room_id);
            var booked_tr = $("#booked_caption-" + room_id);
            var avail_room_tr = $("#avail_caption-" + room_id);
            $('head').append("<style>#room_name-" + room_id + "::before{ content:'Room'; overflow: hidden; text-overflow: ellipsis; width: " + (name_row.outerWidth() + (name_row.next().outerWidth() * 2)) + "px !important; height: " + name_height + "px !important; }</style>");
            $('head').append("<style>#closed_tr-" + room_id + "::before{ content:'Closed'; overflow: hidden; text-overflow: ellipsis; width: " + (closed_tr.outerWidth() + (closed_tr.next().outerWidth() * 2)) + "px !important; height: " + check_height + "px !important; padding: 0.75rem; }</style>");
            $('head').append("<style>#booked_tr-" + room_id + "::before{ content:'Booked'; overflow: hidden; text-overflow: ellipsis; width: " + (booked_tr.outerWidth() + (booked_tr.next().outerWidth() * 2)) + "px !important; height: " + booked_height + "px !important; padding: 0.75rem; }</style>");
            $('head').append("<style>#avail_room_tr-" + room_id + "::before{ content:'Available'; overflow: hidden; text-overflow: ellipsis; width: " + (avail_room_tr.outerWidth() + (avail_room_tr.next().outerWidth() * 2)) + "px !important; height: " + avail_height + "px !important; padding: 0.75rem; }</style>");
        },

        display_total_qty: function(room_id) {
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
            $(".total_qty_cell[data-room='" + room_id + "']").html(total);
        },

        display_booked_qty: function(room_id) {
            var total = 0;
            _.each($(".booked_rooms[data-room='" + room_id + "']"), function(input) {
                total += parseInt($(input).text());
            });
            $(".total_booked_cell[data-room='" + room_id + "']").html(total);
        },

        display_avail_qty: function(room_id) {
            var total = 0;
            _.each($(".avail_rooms[data-room='" + room_id + "']"), function(input) {
                total += parseInt($(input).text());
            });
            $(".total_avail_cell[data-room='" + room_id + "']").html(total);
        },

        _onInputKeyUp: function(ev) {
            if (isNaN(ev.currentTarget.value)) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
            } else if ((parseInt(ev.currentTarget.value) < 0) || ev.currentTarget.value.length > 3) {
                ev.currentTarget.value = ev.currentTarget.defaultValue;
            }
        },

        _onFieldChanged: function(ev) {
            var self = this;

            if (ev.currentTarget.type != 'checkbox') {
                if (isNaN(ev.currentTarget.value)) {
                    ev.currentTarget.value = ev.currentTarget.defaultValue;
                    return;
                } else if ((parseInt(ev.currentTarget.value) < 0) || ev.currentTarget.value.length > 3) {
                    ev.currentTarget.value = ev.currentTarget.defaultValue;
                    return;
                }
             }

            var datas = self.state.data;
            var dataset = ev.currentTarget.dataset;
            var checked = ev.target.checked;
            var value = ev.target.value;
            var res_date = dataset.date;
            var res_room_id = parseInt(dataset.room);
            var prev_data = _.find(datas, function(data) {
                return moment(data.data.date).format('YYYY-MM-DD') == res_date && data.data.room_category_id.res_id == res_room_id
            });

            if (ev.currentTarget.type == 'checkbox') {
                var args = {
                    default_close: checked,
                    default_room_category_id: res_room_id,
                    default_date: res_date,
                    // default_room_qty: dataset.qty,
                }
            } else {
                var args = {
                    default_room_qty: value,
                    default_room_category_id: res_room_id,
                    default_date: res_date,
                    // default_close: dataset.close,
                }
            }

            if (prev_data !== undefined) {
                if (ev.currentTarget.type == 'checkbox') {
                    var args = {
                        default_close: checked,
                        default_room_qty: prev_data.data.room_qty,
                        default_room_category_id: res_room_id,
                        default_date: res_date,
                    }
                } else {
                    var args = {
                        default_close: prev_data.data.close,
                        default_room_qty: value,
                        default_room_category_id: res_room_id,
                        default_date: res_date,
                    }
                }
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

            self.style_checkbox(dataset.dayCount, res_room_id);
            self.display_total_qty(res_room_id);
            self.display_booked_qty(res_room_id);
            self.display_avail_qty(res_room_id);
        },

        _date_changed(date_from, date_to) {
            var self = this;
            self.rendered = false;
            self.date_from = date_from;
            self.date_to = date_to
            self.start();
        }

    });

    var RoomAvailabilityFieldOne2Many = FieldOne2Many.extend({
        /**
         * We want to use our custom renderer for the list.
         *
         * @override
         */
        _getRenderer: function() {
            if (this.view.arch.tag === 'tree') {
                return RoomAvailabilityListRenderer;
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

    fieldRegistry.add('RoomAvailabilityView', RoomAvailabilityFieldOne2Many);
});
