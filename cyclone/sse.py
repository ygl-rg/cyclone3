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

"""`Server-sent events <http://en.wikipedia.org/wiki/Server-sent_events>`_
is a technology for providing push notifications from a server to a browser
client in the form of DOM events.

For more information, check out the `SEE demo
<https://github.com/fiorix/cyclone/tree/master/demos/sse>`_.
"""

from cyclone import escape
from cyclone.web import RequestHandler
from twisted.python import log


class SSEHandler(RequestHandler):
    """Subclass this class and define `bind` and `unbind` to get
    notified when a new client connects or disconnects, respectively.

    Once connected, you may send events to the browser via `sendEvent`.
    """
    def __init__(self, application, request, **kwargs):
        RequestHandler.__init__(self, application, request, **kwargs)
        self.transport = request.connection.transport
        self._auto_finish = False

    def sendEvent(self, message, event=None, eid=None, retry=None):
        """
        sendEvent is the single method to send events to clients.

        Parameters:

        message: the event itself

        event: optional event name

        eid: optional event id to be used as Last-Event-ID header or
             e.lastEventId property

        retry: set the retry timeout in ms. default 3 secs.
        """
        if isinstance(message, dict):
            message = escape.json_encode(message)
        if isinstance(message, str):
            message = message.encode("utf-8")
        assert isinstance(message, bytes)

        if eid:
            self.transport.write("id: %s\n" % eid)
        if event:
            self.transport.write("event: %s\n" % event)
        if retry:
            self.transport.write("retry: %s\n" % retry)

        self.transport.write("data: %s\n\n" % message)

    def _execute(self, transforms, *args, **kwargs):
        self._transforms = []  # transforms
        if self.settings.get("debug"):
            log.msg("SSE connection from %s" % self.request.remote_ip)
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()
        self.request.connection.setRawMode()
        self.notifyFinish().addCallback(self.on_connection_closed)
        self.bind(*args, **kwargs)

    def on_connection_closed(self, *args, **kwargs):
        if self.settings.get("debug"):
            log.msg("SSE client disconnected %s" % self.request.remote_ip)
        self.unbind()

    def bind(self):
        """Gets called when a new client connects."""
        pass

    def unbind(self):
        """Gets called when an existing client disconnects."""
        pass
