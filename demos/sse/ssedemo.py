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

import cyclone.sse
import cyclone.web

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.protocols import telnet
from twisted.python import log


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", cyclone.web.RedirectHandler, {"url": "/static/index.html"}),
            (r"/live", LiveHandler),
        ]
        settings = dict(
            debug=True,
            static_path="./static",
            template_path="./template",
        )
        cyclone.web.Application.__init__(self, handlers, **settings)


class StarWarsMixin(object):
    mbuffer = ""
    waiters = []

    def subscribe(self, client):
        StarWarsMixin.waiters.append(client)

    def unsubscribe(self, client):
        StarWarsMixin.waiters.remove(client)

    def broadcast(self, message):
        cls = StarWarsMixin

        chunks = (self.mbuffer + message.replace("\x1b[J", "")).split("\x1b[H")
        self.mbuffer = ""
        for chunk in chunks:
            if len(chunk) == 985:
                chunk = chunk.replace("\r\n", "<br>")
                log.msg("Sending new message to %r listeners" % \
                        len(cls.waiters))
                for client in cls.waiters:
                    try:
                        client.sendEvent(chunk)
                    except:
                        log.err()
            else:
                self.mbuffer = chunk


class LiveHandler(cyclone.sse.SSEHandler, StarWarsMixin):
    def bind(self):
        self.subscribe(self)

    def unbind(self):
        self.unsubscribe(self)


class BlinkenlightsProtocol(telnet.Telnet, StarWarsMixin):
    def dataReceived(self, data):
        self.broadcast(data)


def main():
    log.startLogging(sys.stdout)

    blinkenlights = protocol.ReconnectingClientFactory()
    blinkenlights.protocol = BlinkenlightsProtocol
    reactor.connectTCP("towel.blinkenlights.nl", 23, blinkenlights)

    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()


if __name__ == "__main__":
    main()
