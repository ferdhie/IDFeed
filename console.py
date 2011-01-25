#!/usr/bin/env python

import sys
import traceback
import common

from google.appengine.api import users

class ConsolePage(common.BaseRequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))

        if not users.is_current_user_admin():
            return self.error(403)

        self.generate('console.html')

    def post(self):
        if not users.is_current_user_admin():
            return self.error(403)
        self.response.headers['Content-Type'] = 'text/plain'

        statement = self.request.get('statement')
        if statement:
            save_stdout = sys.stdout
            save_stderr = sys.stderr
            try:
                sys.stdout = self.response.out
                sys.stderr = self.response.out
                if isinstance(statement, unicode):
                    statement = "# -*- coding: utf-8 -*-\n\n" + statement
                    statement = statement.encode('utf-8')
                s = statement.replace("\r\n", "\n")
                try:
                    compiled_code = compile(s, '<string>', 'exec')
                    exec(compiled_code, globals())
                    self.response.out.write("#OK")
                except:
                    lines = traceback.format_exception(*sys.exc_info())
                    self.response.out.write(''.join(lines))
            finally:
                sys.stdout = save_stdout
                sys.stderr = save_stderr
