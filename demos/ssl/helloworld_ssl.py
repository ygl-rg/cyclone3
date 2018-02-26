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

import cyclone.web
import sys
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.python import log


class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("Hello, %s" % self.request.protocol)


def main():
    log.startLogging(sys.stdout)
    application = cyclone.web.Application([
        (r"/", MainHandler)
    ])

    interface = "127.0.0.1"
    reactor.listenTCP(8888, application, interface=interface)
    reactor.listenSSL(8443, application,
                      ssl.DefaultOpenSSLContextFactory("server.key",
                                                       "server.crt"),
                      interface=interface)
    reactor.run()


if __name__ == "__main__":
    main()
