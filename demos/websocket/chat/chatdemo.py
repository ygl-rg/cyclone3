#!/usr/bin/env python
#
# Copyright 2009 Facebook
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
"""Simplified chat demo for websockets.

Authentication, error handling, etc are left as an exercise for the reader :)
"""

import os.path
import uuid
import sys
import time
from collections import defaultdict

from twisted.python import log
from twisted.internet import reactor, task

import cyclone.escape
import cyclone.web
import cyclone.websocket


class Application(cyclone.web.Application):
    def __init__(self):

        stats = Stats()

        handlers = [
            (r"/", MainHandler, dict(stats=stats)),
            (r"/stats", StatsPageHandler),
            (r"/statssocket", StatsSocketHandler, dict(stats=stats)),
            (r"/chatsocket", ChatSocketHandler, dict(stats=stats)),
        ]
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            autoescape=None,
        )
        cyclone.web.Application.__init__(self, handlers, **settings)


class MainHandler(cyclone.web.RequestHandler):
    def initialize(self, stats):
        self.stats = stats

    def get(self):
        self.stats.newVisit()
        self.render("index.html", messages=ChatSocketHandler.cache)


class ChatSocketHandler(cyclone.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 200

    def initialize(self, stats):
        self.stats = stats

    def connectionMade(self):
        ChatSocketHandler.waiters.add(self)
        self.stats.newChatter()

    def connectionLost(self, reason):
        ChatSocketHandler.waiters.remove(self)
        self.stats.lostChatter()

    @classmethod
    def update_cache(cls, chat):
        cls.cache.append(chat)
        if len(cls.cache) > cls.cache_size:
            cls.cache = cls.cache[-cls.cache_size:]

    @classmethod
    def send_updates(cls, chat):
        log.msg("sending message to %d waiters" % len(cls.waiters))
        for waiter in cls.waiters:
            try:
                waiter.sendMessage(chat)
            except Exception, e:
                log.err("Error sending message. %s" % str(e))

    def messageReceived(self, message):
        log.msg("got message %s" % message)
        parsed = cyclone.escape.json_decode(message)
        chat = {
            "id": str(uuid.uuid4()),
            "body": parsed["body"],
            }
        chat["html"] = self.render_string("message.html", message=chat)

        ChatSocketHandler.update_cache(chat)
        ChatSocketHandler.send_updates(chat)

class StatsSocketHandler(cyclone.websocket.WebSocketHandler):
    def initialize(self, stats):
        self.stats = stats

        self._updater = task.LoopingCall(self._sendData)

    def connectionMade(self):
        self._updater.start(2)

    def connectionLost(self, reason):
        self._updater.stop()

    def _sendData(self):
        data = dict(visits=self.stats.todaysVisits(),
                    chatters=self.stats.chatters)
        self.sendMessage(cyclone.escape.json_encode(data))


class Stats(object):
    def __init__(self):
        self.visits = defaultdict(int) 
        self.chatters = 0

    def todaysVisits(self):
        today = time.localtime()
        key = time.strftime('%Y%m%d', today)
        return self.visits[key]

    def newChatter(self):
        self.chatters += 1

    def lostChatter(self):
        self.chatters -= 1

    def newVisit(self):
        today = time.localtime()
        key = time.strftime('%Y%m%d', today)
        self.visits[key] += 1


class StatsPageHandler(cyclone.web.RequestHandler):
    def get(self):
        self.render("stats.html")


def main():
    reactor.listenTCP(8888, Application())
    reactor.run()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    main()

