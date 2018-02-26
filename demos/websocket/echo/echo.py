#!/usr/bin/env python

import cyclone.escape
import cyclone.web
import cyclone.websocket
import os.path
import sys
from twisted.python import log
from twisted.internet import reactor


class Application(cyclone.web.Application):
    def __init__(self):
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            autoescape=None,
        )

        handlers = [
            (r"/", MainHandler),
            (r"/echo", EchoSocketHandler),
            (r"/(jquery-latest\.js)", cyclone.web.StaticFileHandler,
                dict(path=settings['static_path'])),
        ]
        cyclone.web.Application.__init__(self, handlers, **settings)


class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.render("echo.html")


class EchoSocketHandler(cyclone.websocket.WebSocketHandler):

    def connectionMade(self, *args, **kwargs):
        log.msg("ws opened")

    def connectionLost(self, reason):
        log.msg("ws closed")

    def messageReceived(self, message):
        log.msg("got message %s" % message)
        self.sendMessage(message)


def main():
    reactor.listenTCP(8888, Application())
    reactor.run()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    main()
