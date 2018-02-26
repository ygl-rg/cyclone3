#!/usr/bin/env twistd -ny
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
from twisted.application import internet
from twisted.application import service


class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

webapp = cyclone.web.Application([
    (r"/", MainHandler)
])

application = service.Application("helloworld_twistd")
server = internet.TCPServer(8888, webapp, interface="127.0.0.1")
server.setServiceParent(application)
