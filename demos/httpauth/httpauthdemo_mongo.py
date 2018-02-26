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

import base64
import functools
import sys

import cyclone.redis
import cyclone.web

from twisted.python import log
from twisted.internet import defer, reactor

try:
    import txmongo
except ImportError:
    print("You need txmongo: "
          "https://github.com/fiorix/mongo-async-python-driver")
    sys.exit(1)


class Application(cyclone.web.Application):
    def __init__(self):
        mongodb = txmongo.lazyMongoConnectionPool()

        handlers = [
            (r"/", IndexHandler, dict(mongodb=mongodb)),
            (r"/createuser", CreateUserHandler, dict(mongodb=mongodb)),
        ]
        cyclone.web.Application.__init__(self, handlers, debug=True)


def HTTPBasic(method):
    @defer.inlineCallbacks
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            auth_type, auth_data = \
                self.request.headers["Authorization"].split()
            assert auth_type == "Basic"
            usr, pwd = base64.b64decode(auth_data).split(":", 1)
        except:
            raise cyclone.web.HTTPAuthenticationRequired

        try:
            # search for user under the "cyclonedb.users" collection
            response = yield self.mongodb.cyclonedb.users.find_one(
                             {"usr": usr, "pwd": pwd}, fields=["usr"])
            mongo_usr = response.get("usr")
        except Exception, e:
            log.msg("MongoDB failed to find(): %s" % str(e))
            raise cyclone.web.HTTPError(503)  # Service Unavailable

        if usr != mongo_usr:
            raise cyclone.web.HTTPAuthenticationRequired
        else:
            self._current_user = usr
            defer.returnValue(method(self, *args, **kwargs))
    return wrapper


class IndexHandler(cyclone.web.RequestHandler):
    def initialize(self, mongodb):
        self.mongodb = mongodb

    @HTTPBasic
    def get(self):
        self.write("Hi, %s." % self._current_user)


class CreateUserHandler(cyclone.web.RequestHandler):
    def initialize(self, mongodb):
        self.mongodb = mongodb

    @defer.inlineCallbacks
    def post(self):
        usr = self.get_argument("username")
        pwd = self.get_argument("password")

        try:
            # create user under the "cyclonedb.users" collection
            ObjId = yield self.mongodb.cyclonedb.users.update(
                          {"usr": usr}, {"usr": usr, "pwd": pwd},
                          upsert=True, safe=True)
        except Exception, e:
            log.msg("MongoDB failed to upsert(): %s" % str(e))
            raise cyclone.web.HTTPError(503)  # Service Unavailable

        self.write("User created. ObjId=%s\r\n" % ObjId)


def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()


if __name__ == "__main__":
    main()
