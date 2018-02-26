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

import sys

import cyclone.httpclient
import cyclone.jsonrpc
import cyclone.xmlrpc

from twisted.python import log
from twisted.internet import defer, reactor


class XmlrpcHandler(cyclone.xmlrpc.XmlrpcRequestHandler):
    allowNone = True

    def xmlrpc_echo(self, text):
        return text

    def xmlrpc_sort(self, items):
        return sorted(items)

    def xmlrpc_count(self, items):
        return len(items)

    @defer.inlineCallbacks
    def xmlrpc_geoip_lookup(self, address):
        result = yield cyclone.httpclient.fetch(
            "http://freegeoip.net/xml/%s" % address.encode("utf-8"))
        defer.returnValue(result.body)


class JsonrpcHandler(cyclone.jsonrpc.JsonrpcRequestHandler):
    def jsonrpc_echo(self, text):
        return text

    def jsonrpc_sort(self, items):
        return sorted(items)

    def jsonrpc_count(self, items):
        return len(items)

    @defer.inlineCallbacks
    def jsonrpc_geoip_lookup(self, address):
        result = yield cyclone.httpclient.fetch(
            "http://freegeoip.net/json/%s" % address.encode("utf-8"))
        defer.returnValue(result.body)


def main():
    log.startLogging(sys.stdout)
    application = cyclone.web.Application([
        (r"/xmlrpc", XmlrpcHandler),
        (r"/jsonrpc", JsonrpcHandler),
    ])

    reactor.listenTCP(8888, application)
    reactor.run()

if __name__ == "__main__":
    main()
