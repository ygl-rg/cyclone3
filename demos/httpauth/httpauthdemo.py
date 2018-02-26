#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2010 Alexandre Fiori
# based on the original Tornado by Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import base64
import functools
import sys

import cyclone.web

from twisted.python import log
from twisted.internet import reactor


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
        ]
        cyclone.web.Application.__init__(self, handlers, debug=True)


def HTTPBasic(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        msg = None
        if "Authorization" in self.request.headers:
            auth_type, data = self.request.headers["Authorization"].split()
            try:
                assert auth_type == "Basic"
                usr, pwd = base64.b64decode(data).split(":", 1)
                assert usr == "root@localhost"
                assert pwd == "123"
            except AssertionError:
                msg = "Authentication failed"
        else:
            msg = "Authentication required"

        if msg:
            raise cyclone.web.HTTPAuthenticationRequired(
                            log_message=msg, auth_type="Basic", realm="DEMO")
        else:
            self._current_user = usr
            return method(self, *args, **kwargs)
    return wrapper


class IndexHandler(cyclone.web.RequestHandler):
    @HTTPBasic
    def get(self):
        self.write("Hi, %s." % self._current_user)


def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="0.0.0.0")
    reactor.run()


if __name__ == "__main__":
    main()
