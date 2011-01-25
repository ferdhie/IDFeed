#!/usr/bin/env python

import os
import re
import functools

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from django.utils import simplejson

_DEBUG = True

mobile_re = re.compile( r'acs|alav|alca|amoi|audi|avan|benq|bird|blac|blaz|brew|cell|cldc|cmd-' +
        '|dang|doco|erics|hipt|inno|ipaq|jigs|kddi|keji|leno|lg-c|lg-d|lg-g|lge-' +
        '|maui|maxo|midp|mits|mmef|mobi|mot-|moto|mwbp|nec-|newt|noki|opwv' +
        '|palm|pana|pant|pdxg|phil|play|pluc|portab|prox|qtek|qwap|sage|sams|sany' +
        '|sch-|sec-|send|seri|sgh-|shar|sie-|siem|smal|sony|sph-|symb|t-mo' +
        '|teli|tim-|toshib|tsm-|upg1|upsi|vk-v|voda|w3cs' +
        '|winw|winw|xda|xda-' +
        '|up.browser|up\.link|windowssce|iemobile|mini|mmp' +
        '|symbian|midp|wap|phone|pocket|mobile|pda|psp', re.I )

template.register_template_library('templatefilters')

def login_required(method):
    '''Redirect to login URL if user not loggedin'''
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        if not users.is_current_user_admin():
            return self.error(403)
        return method(self, *args, **kwargs)
    return wrapper

class BaseRequestHandler(webapp.RequestHandler):
    '''This is the base of all RequestHandler, contains useful method'''
    def is_mobile_browser(self):
        '''Check if the client is a mobile browser or not'''
        accept = self.request.headers.get('Accept', '').lower()
        if 'application/vnd.wap.xhtml+xml' in accept or 'text/vnd.wap.wml' in accept:
            return 1
        ua  = self.request.headers.get('User-Agent', '').lower()
        if mobile_re.search(ua):
            return 1
        return 0

    def generate(self, template_name, template_values=None):
        '''Generate template and default parameter values'''
        if isinstance(template_name, (dict,tuple,list)):
            self.response.headers['Content-Type'] = 'text/json'
            if template_values:
                self.response.out.write('%s(%s)' % (template_values, simplejson.dumps(template_name)))
            else:
                self.response.out.write(simplejson.dumps(template_name))
            return

        if template_values is None:
            template_values = {}

        values = {
            'request': self.request,
            'debug': self.request.get('deb'),
            'application_name': 'Berita',
        }
        values.update(template_values)
        directory = os.path.dirname(__file__)
        path = os.path.join(directory, os.path.join('templates', template_name))
        self.response.out.write(template.render(path, values, debug=_DEBUG))
