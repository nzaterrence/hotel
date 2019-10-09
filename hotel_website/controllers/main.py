# See LICENSE file for full copyright and licensing details

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import Home


class HotelManagement(Home):

    @http.route(['/', '/page/homepage', '/home'], type='http', auth="public", website=True)
    def hotel_homepage(self, **post):
        """Render the Homepage."""
        room_type = request.env['hotel.room'].sudo().search([])
        state_id = request.env['res.country.state'].sudo().search([])
        city_id = request.env['hotel.city'].sudo().search([])
        data = {
            'room_type': room_type,
            'state_id': state_id,
            'city_id': city_id,
        }
        return request.render('hotel_website.hotel_website_homepage1', data)

    @http.route('/about', type='http', auth="public", website=True)
    def hotel_aboutpage(self, **post):

        return request.render('hotel_website.hotel_about_layout', {})

    @http.route('/book', type='http', auth="public", website=True)
    def hotel_bookpage(self, **post):
        """Render the Book Page."""
        room_type = request.env['hotel.room'].sudo().search([])
        data = {
            'room_type': room_type,
        }
        return request.render('hotel_website.hotel_book_layout', data)

    @http.route('/gallary', type='http', auth="public", website=True)
    def hotel_gallarypage(self, **post):
        """Render the Gallary Page."""

        return request.render('hotel_website.hotel_gallary_layout', {})

    @http.route(['/room-detail/<model("hotel.room"):room>'], type='http', auth="public", website=True)
    def hotel_room_detail(self, room, **post):
        """Render the Gallary Page."""
        room_type = request.env['hotel.room'].sudo().search([])
        state_id = request.env['res.country.state'].sudo().search([])
        data = {
            'room': room,
            'room_type': room_type,
            'state_id': state_id,
        }
        return request.render('hotel_website.hotel_room_detail_layout2', data)
