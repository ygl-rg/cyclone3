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

"""Server-side implementation of the XML-RPC protocol.

`XML-RPC <http://en.wikipedia.org/wiki/XML-RPC>`_ is a remote procedure call
protocol which uses XML to encode its calls and HTTP as a transport mechanism.

For more information, check out the `RPC demo
<https://github.com/fiorix/cyclone/tree/master/demos/rpc>`_.
"""

#import xmlrpclib
from xmlrpc import client as xmlrpc_client
from xmlrpc import server as xmlrpc_server

from twisted.internet import defer
from cyclone.web import RequestHandler


class XmlrpcRequestHandler(RequestHandler):
    """Subclass this class and define xmlrpc_* to make a handler.

    Example::

        class MyRequestHandler(XmlrpcRequestHandler):
            allowNone = True

            def xmlrpc_echo(self, text):
                return text

            def xmlrpc_sort(self, items):
                return sorted(items)

            @defer.inlineCallbacks
            def xmlrpc_geoip_lookup(self, address):
                response = yield cyclone.httpclient.fetch(
                    "http://freegeoip.net/xml/%s" % address.encode("utf-8"))
                defer.returnValue(response.body)
    """

    FAILURE = 8002
    NOT_FOUND = 8001
    separator = "."
    allowNone = False

    def post(self):
        self._auto_finish = False
        self.set_header("Content-Type", "text/xml")
        try:
            args, functionPath = xmlrpc_server.loads(self.request.body)
        except Exception as e:
            f = xmlrpc_server.Fault(self.FAILURE, "Can't deserialize input: %s" % e)
            self._cbRender(f)
        else:
            try:
                function = self._getFunction(functionPath)
            except xmlrpc_server.Fault as f:
                self._cbRender(f)
            else:
                d = defer.maybeDeferred(function, *args)
                d.addCallback(self._cbRender)
                d.addErrback(self._ebRender)

    def _getFunction(self, functionPath):
        if functionPath.find(self.separator) != -1:
            prefix, functionPath = functionPath.split(self.separator, 1)
            handler = self.getSubHandler(prefix)
            if handler is None:
                raise xmlrpc_server.Fault(self.NOT_FOUND,
                    "no such subHandler %s" % prefix)
            return self._getFunction(functionPath)

        f = getattr(self, "xmlrpc_%s" % functionPath, None)
        if f is None:
            raise xmlrpc_server.Fault(self.NOT_FOUND, "function %s not found" % functionPath)
        elif not callable(f):
            raise xmlrpc_server.Fault(self.NOT_FOUND, "function %s not callable" % functionPath)
        else:
            return f

    def _cbRender(self, result):
        if not isinstance(result, xmlrpc_server.Fault):
            result = (result,)

        try:
            s = xmlrpc_server.dumps(result, methodresponse=True, allow_none=self.allowNone)
        except Exception as e:
            f = xmlrpc_server.Fault(self.FAILURE, "can't serialize output: %s" % e)
            s = xmlrpc_server.dumps(f, methodresponse=True, allow_none=self.allowNone)

        self.finish(s)

    def _ebRender(self, failure):
        if isinstance(failure.value, xmlrpc_server.Fault):
            s = failure.value
        else:
            s = xmlrpc_server.Fault(self.FAILURE, "error")

        self.finish(xmlrpc_server.dumps(s, methodresponse=True))
