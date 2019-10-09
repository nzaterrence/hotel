odoo.define('hms_dashboard.HMSDashboardView', function(require) {
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

    var HMSDashboard = AbstractAction.extend({
        cssLibs: [
            '/hms_dashboard/static/src/css/dataTables.bootstrap4.css',
            '/hms_dashboard/static/src/css/sb-admin.css',
            '/hms_dashboard/static/src/css/bootstrap.css',
        ],
        jsLibs: [
            '/hms_dashboard/static/src/js/Chart.bundle.min.js',
            '/hms_dashboard/static/src/js/Chart.min.js',
            // '/hms_dashboard/static/src/js/dataTables.bootstrap4.min.js',
            '/hms_dashboard/static/src/js/jquery.dataTables.min.js',
            '/hms_dashboard/static/src/js/sb-admin.js'
        ],

        events: {
            'click .btn_today_booking': 'action_today_booking',
            'click .btn_total_booking': 'action_total_booking',
            'click .btn_today_revenue': 'action_today_revenue',
            'click .btn_total_revenue': 'action_total_revenue',
            'click .btn_today_arrival': 'action_today_arrival',
            'click .btn_total_arrival': 'action_total_arrival',
            'click .btn_today_departure': 'action_today_departure',
            'click .btn_total_departure': 'action_total_departure',
            'click .booking-refresh': 'action_booking_refresh',
            'click .room-refresh': 'action_room_refresh',
            'click .sales-refresh': 'action_sales_refresh',
            'click .occupancy-refresh': 'action_occupancy_refresh',
            'click .btn-tbl-confirm': 'confirm_booking',
            'click .btn-tbl-delete': 'cancel_booking',
            'click .btn-tbl-view': 'goto_booking',
        },

        init: function(parent, context) {
            this._super(parent, context);
            this.invoice_ids = [];
            this.today_arrivals_ids = [];
            this.today_departure_ids = [];
            this.total_departure_ids = [];
            self.new_reservation_count_id = 0;
            self.today_reservation_count_id = 0;
            self.total_revenue = 0.00;
            self.today_revenue = 0.00;
            self.arrivals_count_id = 0;
            self.departures_count_id = 0;
            self.is_hotel_manager = true;
            self.is_hotel_user = true;
            self.symbol = '$';
            self.position = 'left';
            self.total_reservation_count = 0;
            self.total_arrival_count = 0;
            self.total_departure_count = 0;
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
                self.render_dashboard();
                self.init_bar_chart();
                self.init_pie_chart();
                self.init_booking_detail_table();
                self.init_room_detail_table();
                self.init_reservation_table();
                self.init_prieclist_table();
                $("#room_detail_body").height($("#sales_chart_body").height());
            });
        },

        fetch_data: function() {
            var self = this;
            return this._rpc({
                model: 'hms.dashboard',
                method: 'get_hms_dashboard_details',
            }).done(function(details) {
                self.invoice_ids.push(details['invoice_ids'])
                self.today_arrivals_ids.push(details['today_arrival_ids'])
                self.today_departure_ids.push(details['today_departure_ids'])
                self.total_departure_ids.push(details['total_departure_ids'])
                self.new_reservation_count_id = details['hotel_reservation_count_id'];
                self.today_reservation_count_id = details['today_reservation_count_id'];
                self.total_revenue = parseFloat(details['total_revenue']).toFixed(2);
                self.today_revenue = parseFloat(details['today_revenue']).toFixed(2);
                self.arrivals_count_id = details['today_arrival_count_id'];
                self.departures_count_id = details['today_departure_count_id'];
                self.is_hotel_manager = is_hotel_manager;
                self.is_hotel_user = is_hotel_user;
                self.symbol = details['symbol'];
                self.position = details['position'];
                self.total_reservation_count = details['total_reservation_count'];
                self.total_arrival_count = details['total_arrival_count'];
                self.total_departure_count = details['total_departure_count'];
            });
        },

        render_dashboard: function() {
            var self = this;
            self.$el.append(QWeb.render('hms_dashboard.HMSDashboard', {
                widget: self
            }));
            // $(document).find('.o_cp_left').remove();
        },

        init_booking_detail_table: function() {
            var self = this;
            var table = self.$("#booking_detail");
            var tbody = self.$("#booking_table_body");
            tbody.html('');
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_last_10_reservations',
            }).done(function(details) {
                var count = 1;
                _.each(details, function(data) {
                    var reservation_no = data.reservation_no;
                    var id = data.id;
                    var name = data.guest_name;
                    var checkin = field_utils.format.date(field_utils.parse.date(data.checkin, {}, {isUTC: true}));
                    var checkout = field_utils.format.date(field_utils.parse.date(data.checkout, {}, {isUTC: true}));;
                    var buttons = '';
                    buttons += '<button class="btn btn-tbl-view btn-xs" data-id="' + data.id + '" data-toggle="tooltip" title="View">';
                    buttons += '<i class="fa fa-eye"></i>';
                    buttons += '</button>';
                    if (data.state == 'draft') {
                        var status = '<span class="hms-label hms-label-sm hms-label-warning">draft</span>';
                        buttons += '<button class="btn btn-tbl-confirm btn-xs" data-id="' + data.id + '" data-toggle="tooltip" title="Confirm">';
                        buttons += '<i class="fa fa-check"></i>';
                        buttons += '</button>';
                        buttons += '<button class="btn btn-tbl-delete btn-xs" data-id="' + data.id + '" data-toggle="tooltip" title="Cancel">';
                        buttons += '<i class="fa fa-times "></i>';
                        buttons += '</button>';
                    } else if (data.state == 'confirm') {
                        var status = '<span class="hms-label hms-label-sm hms-label-success">confirm</span>';
                        buttons += '<button class="btn btn-xs btn-hidden" data-id="' + data.id + '">';
                        buttons += '<i class="fa fa-check"></i>';
                        buttons += '</button>';
                        buttons += '<button class="btn btn-tbl-delete btn-xs" data-id="' + data.id + '" data-toggle="tooltip" title="Cancel">';
                        buttons += '<i class="fa fa-times "></i>';
                        buttons += '</button>';
                    } else if (data.state == 'cancel') {
                        var status = '<span class="hms-label hms-label-sm hms-label-danger">cancel</span>';
                        buttons += '<button class="btn btn-tbl-confirm btn-xs btn-hidden" data-id="' + data.id + '" data-toggle="tooltip" title="Confirm">';
                        buttons += '<i class="fa fa-check"></i>';
                        buttons += '</button>';
                        buttons += '<button class="btn btn-xs btn-hidden" data-id="' + data.id + '">';
                        buttons += '<i class="fa fa-times "></i>';
                        buttons += '</button>';
                    } else {
                        var status = '<span class="hms-label hms-label-sm hms-label-info">done</span>';
                        buttons += '<button class="btn btn-xs btn-hidden" data-id="' + data.id + '">';
                        buttons += '<i class="fa fa-check"></i>';
                        buttons += '</button>';
                        buttons += '<button class="btn btn-xs btn-hidden" data-id="' + data.id + '">';
                        buttons += '<i class="fa fa-times "></i>';
                        buttons += '</button>';
                    }
                    var phone = data.phone;
                    if (phone == null || !phone) {
                        phone = 'N/A';
                    }
                    // var room_type = data.room_type

                    var row = "<tr>";
                    row += "<td>";
                    row += reservation_no
                    row += "</td>";
                    row += "<td>";
                    row += name
                    row += "</td>";
                    row += "<td>";
                    row += checkin;
                    row += "</td>";
                    row += "<td>";
                    row += checkout;
                    row += "</td>";
                    row += "<td>";
                    row += status
                    row += "</td>";
                    row += "<td>";
                    row += phone
                    row += "</td>";
                    row += "<td>";
                    row += buttons
                    row += "</td>";
                    row += "</tr>";
                    tbody.append(row);
                })
            });
        },

        confirm_booking: function(ev){
            var self = this;
            self.action_booking_refresh();
            ev.preventDefault();
            ev.stopImmediatePropagation();
            var res_id = $(ev.currentTarget).data('id');
            self._rpc({
                model: 'hms.dashboard',
                method: 'confirm_reservation',
                args: [res_id],
            }).done(function(details) {
                self.action_booking_refresh();
            });
        },

        cancel_booking: function(ev){
            var self = this;
            ev.preventDefault();
            ev.stopImmediatePropagation();
            var res_id = $(ev.currentTarget).data('id');

            Dialog.confirm(self, (_t("Are you sure you want to Cancel this reservation?")), {
                confirm_callback: function () {
                    self._rpc({
                        model: 'hms.dashboard',
                        method: 'cancel_reservation',
                        args: [res_id],
                    }).done(function(details) {
                        self.action_booking_refresh();
                    });
                },
            });
        },

        goto_booking: function(ev){
            var self = this;
            ev.preventDefault();
            ev.stopImmediatePropagation();
            var id = JSON.parse($(ev.currentTarget).data("id"));
            self.do_action({
                type: 'ir.actions.act_window',
                res_model: "hotel.reservation",
                res_id: id,
                views: [
                    [false, 'form']
                ],
            });
        },

        action_booking_refresh: function() {
            $("<div class='refresh-block'><span class='refresh-loader'><i class='fa fa-spinner fa-spin'></i></span></div>").appendTo($("#booking-detail-table"));
            this.init_booking_detail_table();
            setTimeout(function() {
                $('.refresh-block').remove();
            }, 1000);
        },

        action_room_refresh: function() {
            $("<div class='refresh-block'><span class='refresh-loader'><i class='fa fa-spinner fa-spin'></i></span></div>").appendTo($("#room_detail_body"));
            this.init_room_detail_table();
            setTimeout(function() {
                $('.refresh-block').remove();
            }, 1000);
        },

        action_sales_refresh: function() {
            $("<div class='refresh-block'><span class='refresh-loader'><i class='fa fa-spinner fa-spin'></i></span></div>").appendTo($("#sales_chart_body"));
            this.init_bar_chart();
            setTimeout(function() {
                $('.refresh-block').remove();
            }, 1000);
        },

        action_occupancy_refresh: function() {
            $("<div class='refresh-block'><span class='refresh-loader'><i class='fa fa-spinner fa-spin'></i></span></div>").appendTo($("#occupancy_chart_body"));
            this.init_pie_chart();
            setTimeout(function() {
                $('.refresh-block').remove();
            }, 1000);
        },

        init_reservation_table: function() {
            var table = self.$('#reservation_table').DataTable({
                searching: false,
                "info": false,
                "lengthMenu": [
                    [5],
                    [5]
                ],
                "paging": false,
            });
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_last_5_reservations',
            }).done(function(details) {
                _.each(details, function(data) {
                    table.row.add([
                        data.reservation_no,
                        data.guest_name,
                        data.checkin,
                        data.checkout,
                        data.state
                    ]).draw(false);
                })
            });
        },

        init_prieclist_table: function() {
            var table = self.$('#prieclist_table').DataTable({
                searching: false,
                "info": false,
                "lengthMenu": [
                    [5],
                    [5]
                ],
                "paging": false,
            });
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_room_current_rate',
            }).done(function(details) {
                _.each(details, function(data) {
                    table.row.add([
                        data.room,
                        data.rate_price,
                        data.room_qty,
                    ]).draw(false);
                })
            });
        },

        init_room_detail_table: function() {
            var self = this;
            var table = self.$("#room_detail");
            var tbody = self.$("#room_table_body");
            tbody.html('');
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_room_current_rate',
            }).done(function(details) {
                var count = 1;
                _.each(details, function(data) {
                    var room = data.room;
                    var detail = data.description;
                    var avail = data.room_qty;
                    var price = data.rate_price;

                    var row = "<tr>";
                    row += "<td class='text-center'>";
                    row += count
                    row += "</td>";
                    row += "<td>";
                    row += room
                    row += "</td>";
                    row += "<td class='text-wrapped toggle-wrap' width='50%'>";
                    row += detail
                    row += "</td>";
                    row += "<td class='text-center'>";
                    row += avail
                    row += "</td>";
                    row += "<td class='text-right'>";
                    row += price
                    row += "</td>";
                    row += "</tr>";
                    tbody.append(row);
                    count++;
                })
            });
            $(document).on('click', '.toggle-wrap', function(event) {
                event.preventDefault();
                $(this).toggleClass('text-wrapped');
            });
        },

        init_chart: function() {
            Chart.defaults.global.defaultFontFamily = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
            Chart.defaults.global.defaultFontColor = '#292b2c';
            var dates = [];
            var counts = [];
            var start = new Date();
            var end = moment(start).add(1, 'M');
            while (start <= end) {
                dates.push(moment(start).format('DD MMM'));
                this._rpc({
                    model: 'hms.dashboard',
                    method: 'get_chart_data',
                    args: [moment(start).format('YYYY-MM-DD')]
                }).done(function(reserve_count) {
                    counts.push(reserve_count);
                });
                var m_start = moment(start).add(1, 'days');
                start = m_start.toDate();
            }
            var ctx = self.getElementById("myAreaChart");
            var myLineChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: _lt("Sessions"),
                        lineTension: 0.3,
                        backgroundColor: "rgba(2,117,216,0.2)",
                        borderColor: "rgba(2,117,216,1)",
                        pointRadius: 5,
                        pointBackgroundColor: "rgba(2,117,216,1)",
                        pointBorderColor: "rgba(255,255,255,0.8)",
                        pointHoverRadius: 5,
                        pointHoverBackgroundColor: "rgba(2,117,216,1)",
                        pointHitRadius: 50,
                        pointBorderWidth: 2,
                        data: counts,
                    }],
                },
                options: {
                    scales: {
                        xAxes: [{
                            time: {
                                unit: 'date'
                            },
                            gridLines: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 10
                            }
                        }],
                        yAxes: [{
                            ticks: {
                                min: 0,
                                max: 100,
                                maxTicksLimit: 5
                            },
                            gridLines: {
                                color: "rgba(0, 0, 0, .125)",
                            }
                        }],
                    },
                    legend: {
                        display: false
                    }
                }
            });
        },

        init_bar_chart: function() {
            // Bar Chart Example
            var self = this;
            Chart.defaults.global.defaultFontFamily = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
            Chart.defaults.global.defaultFontColor = '#292b2c';
            var ctx = self.$("#sales_chart")[0];
            // ctx.height = $(".reservation_table").height() - 10;
            ctx.height = 250;
            var myLineChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: [{
                        label: _lt("Revenue"),
                        backgroundColor: "rgba(2,117,216,1)",
                        borderColor: "rgba(2,117,216,1)",
                    }],
                },
                options: {
                    scales: {
                        xAxes: [{
                            time: {
                                unit: 'month'
                            },
                            gridLines: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 6
                            }
                        }],
                        yAxes: [{
                            ticks: {
                                min: 0,
                                max: 30000,
                                maxTicksLimit: 5
                            },
                            gridLines: {
                                display: true
                            }
                        }],
                    },
                    legend: {
                        display: false
                    }
                }
            });
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_last_6_months_sales',
            }).done(function(details) {
                _.each(details.datas, function(data) {
                    self.addBarChartData(myLineChart, $.trim(data.month), data.total, details.max_val);
                })
            });
        },

        addBarChartData: function(chart, label, data, max_val) {
            chart.data.labels.push(label);
            chart.data.datasets.forEach((dataset) => {
                dataset.data.push(data);
            });
            chart.options.scales.yAxes.forEach((yAxe) => {
                yAxe.ticks.max = max_val;
            });
            chart.update();
        },

        init_pie_chart: function() {
            var self = this;
            Chart.defaults.global.defaultFontFamily = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
            Chart.defaults.global.defaultFontColor = '#292b2c';
            var ctx = self.$("#room_chart")[0];
            ctx.height = 110;
            var myPieChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    // labels: ["Blue", "Red", "Yellow", "Green"],
                    datasets: [{
                        // data: [12.21, 15.58, 11.25, 8.32],
                        backgroundColor: ['#007bff'],
                    }],
                },
                options: {
                    legend: {
                        position: 'right'
                    },
                }
            });
            this._rpc({
                model: 'hms.dashboard',
                method: 'get_pie_chart_data',
            }).done(function(details) {
                _.each(details, function(data) {
                    self.addPieChartData(myPieChart, $.trim(data.name), data.total);
                })
            });
        },

        getRandomColor: function() {
            var letters = '0123456789ABCDEF'.split('');
            var color = '#';
            for (var i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
            }
            return color;
        },

        addPieChartData: function(chart, label, data) {
            var self = this;
            chart.data.labels.push(label);
            chart.data.datasets.forEach((dataset) => {
                dataset.data.push(data);
                dataset.backgroundColor.push(self.getRandomColor());
            });
            chart.update();
        },

        action_today_booking: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Today's Booking",
                res_model: 'hotel.reservation',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                context: {
                    'search_default_today_reservation': 'True'
                }
            });
        },

        action_total_booking: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Total Reservations",
                res_model: 'hotel.reservation',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                context: {
                    'search_default_confirm': 'True',
                    'search_default_done': 'True'
                }
            });
        },

        action_today_revenue: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Today Revenue",
                res_model: 'account.invoice',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                domain: [
                    ['type', 'in', ['out_invoice', 'out_refund']],
                    ['state', 'not in', ['cancel', 'draft']]
                ],
                context: {
                    'search_default_today_invoice': 'True'
                }
            });
        },

        action_total_revenue: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Today Revenue",
                res_model: 'account.invoice',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                domain: [
                    ['type', 'in', ['out_invoice', 'out_refund']],
                    ['state', 'not in', ['cancel', 'draft']]
                ],
                // context: {'search_default_today_invoice': 'True'}
            });
        },

        action_today_arrival: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Today Arrivals",
                res_model: 'hotel.reservation',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                // domain: [
                //     ['id', 'in', today_arrivals_ids[0] || []]
                // ],
                context: {
                    'search_default_arrival_today': 'True'
                }
            });
        },

        action_total_arrival: function(ev) {
            var self = this;
            ev.preventDefault();
            this.do_action({
                name: "Total Arrivals",
                res_model: 'hotel.reservation',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                // domain: [
                //     ['id', 'in', self.today_arrivals_ids[0] || []]
                // ],
                // context: {'search_default_arrival_today': 'True'}
            });
        },

        action_today_departure: function(ev) {
            ev.preventDefault();
            this.do_action({
                name: "Today Departure",
                res_model: 'hotel.folio',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                // domain: [
                //     ['id', 'in', today_departure_ids[0]]
                // ],
                context: {
                    'search_default_departure_today': 'True'
                }
            });
        },

        action_total_departure: function(ev) {
            var self = this;
            ev.preventDefault();
            console.log(self.total_departure_ids);
            this.do_action({
                name: "Total Departure",
                res_model: 'hotel.folio',
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban'],
                ],
                type: 'ir.actions.act_window',
                view_type: "list",
                view_mode: "list",
                domain: [
                    ['id', 'in', self.total_departure_ids[0]]
                ],
                // context: {'search_default_departure_today': 'True'}
            });
        },

    });

    core.action_registry.add('hms_dashboard', HMSDashboard);

    return HMSDashboard;

});
