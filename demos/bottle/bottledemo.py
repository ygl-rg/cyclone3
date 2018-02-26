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

import cyclone.escape
import cyclone.redis
import cyclone.sqlite
import cyclone.util
import cyclone.web
import cyclone.websocket
import cyclone.xmlrpc
from cyclone.bottle import run, route

from twisted.internet import defer
from twisted.python import log


class BaseHandler(cyclone.web.RequestHandler):
    @property
    def redisdb(self):
        return self.settings.db_handlers.redis

    def get_current_user(self):
        print "Getting user cookie"
        return self.get_secure_cookie("user")


@route("/")
def index(cli):
    cli.write('<a href="/auth/login">sign in</a>')


@route("/auth/login")
def auth_login_page(cli):
    cli.write("""
    <html><body><form method="post">
    username: <input type="text" name="usr"/><br/>
    password: <input type="password" name="pwd"/><br/>
    <input type="submit">
    </form></body></html>
    """)


@route("/auth/login", method="post")
@defer.inlineCallbacks
def auth_login(cli):
    usr = cli.get_argument("usr")
    pwd = cli.get_argument("pwd")

    try:
        redis_pwd = yield cli.redisdb.get("cyclone:%s" % usr)
    except Exception, e:
        log.msg("Redis failed to get('cyclone:%s'): %s" % (usr, str(e)))
        raise cyclone.web.HTTPError(503)  # Service Unavailable

    if pwd != str(redis_pwd):
        cli.write("Invalid user or password.<br>"
                  '<a href="/auth/login">try again</a>')
    else:
        cli.set_secure_cookie("user", usr)
        cli.redirect(cli.get_argument("next", "/private"))


@route("/auth/logout")
@cyclone.web.authenticated
def auth_logout(cli):
    cli.clear_cookie("user")
    cli.redirect("/")


@route("/private")
@cyclone.web.authenticated
def private(cli):
    cli.write("Hi, %s<br/>" % cli.current_user)
    cli.write("""<a href="/auth/logout">logout</a>""")


class WebSocketHandler(cyclone.websocket.WebSocketHandler):
    def connectionMade(self, *args, **kwargs):
        print "connection made:", args, kwargs

    def messageReceived(self, message):
        self.sendMessage("echo: %s" % message)

    def connectionLost(self, why):
        print "connection lost:", why


class XmlrpcHandler(cyclone.xmlrpc.XmlrpcRequestHandler):
    allowNone = True

    def xmlrpc_echo(self, text):
        return text


try:
    raise Exception("COMMENT_THIS_LINE_AND_LOG_TO_DAILY_FILE")
    from twisted.python.logfile import DailyLogFile
    logFile = DailyLogFile.fromFullPath("server.log")
    print("Logging to daily log file: server.log")
except Exception, e:
    import sys
    logFile = sys.stdout

run(host="127.0.0.1", port=8888,
    log=logFile,
    debug=True,
    static_path="./static",
    template_path="./template",
    locale_path="./locale",
    login_url="/auth/login",
    cookie_secret="32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
    base_handler=BaseHandler,
    db_handlers=cyclone.util.ObjectDict(
        #sqlite=cyclone.sqlite.InlineSQLite(":memory:"),
        redis=cyclone.redis.lazyConnectionPool(),
    ),
    more_handlers=[
        (r"/websocket", WebSocketHandler),
        (r"/xmlrpc",    XmlrpcHandler),
    ])
