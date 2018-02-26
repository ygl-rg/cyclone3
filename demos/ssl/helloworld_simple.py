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
#
# Run: twistd -n cyclone --ssl-app helloworld_simple.Application
# For more info: twistd -n cyclone --help

import cyclone.web


class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("Hello, %s" % self.request.protocol)


Application = lambda: cyclone.web.Application([(r"/", MainHandler)])
