odoo.define('hotel_quick_reservation.quick_reservation', function(require) {
    "use strict";

    var AbstractRenderer = require('web.AbstractRenderer');
    var config = require('web.config');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var field_utils = require('web.field_utils');
    var FieldManagerMixin = require('web.FieldManagerMixin');
    var QWeb = require('web.QWeb');
    var relational_fields = require('web.relational_fields');
    var session = require('web.session');
    var dialogs = require('web.view_dialogs');
    var utils = require('web.utils');
    var Widget = require('web.Widget');
    var CalendarRenderer = require('web.CalendarRenderer');
    var CalendarController = require('web.CalendarController')

    var _t = core._t;
    var _lt = core._lt;
    var qweb = core.qweb;

    CalendarRenderer.include({

        init: function(parent, state, params) {
            this._super.apply(this, arguments);
            this.reservation_form = false
            if (this.model === 'hotel.quick.reservation') {
                this.reservation_form = true
            };
        },

        _renderFilters: function() {
            if (this.reservation_form === true) {
                this._super.apply(this, arguments);
                this.style_sidebar();
            } else {
                this._super.apply(this, arguments);
            }
        },

        style_sidebar: function() {
            var self = this;
            _.each(self.filters, function(filter) {
                filter.$el.find('input[type="checkbox"]').each(function(index, el) {
                    if ($(this).prop("checked")) {
                        $(this).parent().parent().removeClass('checkbox_uncheck').addClass('checkbox_checked');
                    } else {
                        $(this).parent().parent().removeClass('checkbox_checked').addClass('checkbox_uncheck');
                    }
                });
            });
            var sidebar = self.$sidebar_container.find('.o_calendar_contacts');
            sidebar.addClass('reservation_view_filters');
        },

    });

    CalendarController.include({
        init: function(parent, model, renderer, params) {
            this._super.apply(this, arguments);
            this.reservation_form = false
            if (model.modelName === 'hotel.quick.reservation') {
                this.reservation_form = true
            };
        },

        _onOpenEvent: function(event) {
            if (this.reservation_form === true) {
                if (event.data._start < new Date()) {
                    return false;
                }
                var self = this;
                var id = event.data._id;
                var search_domain = [
                    ['id', '=', id]
                ];
                var result;
                this._rpc({
                    model: self.modelName,
                    method: 'search_read',
                    //The event can be called by a view that can have another context than the default one.
                    args: [search_domain, []],
                }).done(function(result_set) {
                    var result = result_set[0];
                    var checkin_date = new Date(result.room_date);
                    var day = 60 * 60 * 24 * 1000;
                    var checkout_date = new Date(checkin_date.getTime() + day);
                    new dialogs.FormViewDialog(self, {
                        res_model: 'hotel.reservation',
                        context: {
                            default_checkin: checkin_date,
                            default_checkout: checkout_date,
                            default_reservation_line: [
                                [0, 0, {
                                    name: _lt('New'),
                                    room_id: result.room_id[0],
                                    stay_days: 1,
                                    price_unit: result.price,
                                    checkin: checkin_date,
                                    checkout: checkout_date,
                                }]
                            ]
                        },
                        title: 'Quick Reservation',
                    }).open();
                });
            } else {
                this._super.apply(this, arguments);
            }
        },

        _onOpenCreate: function(event) {
            if (this.reservation_form === true) {
                if (event.data.start < new Date()) {
                    return false;
                }
                var self = this;
                var context = _.extend({}, this.context, event.options && event.options.context);
                var data = this.model.calendarEventToRecord(event.data);
                var checkin_date = new Date(data[this.mapping.date_start]);
                if (event.data.end) {
                    var checkout_date = event.data.end.toDate();
                } else {
                    var day = 60 * 60 * 24 * 1000;
                    var checkout_date = new Date(checkin_date.getTime() + day);
                }
                var qty = event.data.end.diff(event.data.start, 'days');
                new dialogs.FormViewDialog(self, {
                    res_model: 'hotel.reservation',
                    context: {
                        default_checkin: checkin_date,
                        default_checkout: checkout_date,
                        default_reservation_line: [
                            [0, 0, {
                                name: _lt('New'),
                                stay_days: qty,
                                checkin: checkin_date,
                                checkout: checkout_date,
                            }]
                        ]
                    },
                    title: 'Quick Reservation',
                }).open();
            } else {
                this._super.apply(this, arguments);
            }
        },

    });

})
