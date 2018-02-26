# coding: utf-8
#
# Copyright 2012 Alexandre Fiori
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
import imp
import os
import sys
import types

from twisted.application import internet
from twisted.application import service
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python import reflect
from zope.interface import implementer

try:
    from twisted.internet import ssl
except ImportError:
    ssl_support = False
else:
    ssl_support = True


class Options(usage.Options):
    # The reason for having app=x and ssl-app=y is to be able to have
    # different URI routing on HTTP and HTTPS.
    # Example: A login handler that only exists in HTTPS.
    optParameters = [
        ["port", "p", 8888, "tcp port to listen on", int],
        ["listen", "l", "0.0.0.0", "interface to listen on"],
        ["unix", "u", None, "listen on unix socket instead of ip:port"],
        ["app", "r", None, "cyclone application to run"],
        ["appopts", "c", None, "arguments to your application"],
        ["ssl-port", None, 8443, "port to listen on for ssl", int],
        ["ssl-listen", None, "0.0.0.0", "interface to listen on for ssl"],
        ["ssl-cert", None, "server.crt", "ssl certificate"],
        ["ssl-key", None, "server.key", "ssl server key"],
        ["ssl-app", None, None, "ssl application (same as --app)"],
        ["ssl-appopts", None, None, "arguments to the ssl application"],
    ]

    def parseArgs(self, *args):
        if args:
            self["filename"] = args[0]


@implementer(service.IServiceMaker, IPlugin)
class ServiceMaker(object):
    tapname = "cyclone"
    description = "A high performance web server"
    options = Options

    def makeService(self, options):
        srv = service.MultiService()
        s = None

        if "app" in options and (options["app"] or "")[-3:].lower() == ".py":
            options["filename"] = options["app"]

        if "filename" in options and os.path.exists(options["filename"]):
            n = os.path.splitext(os.path.split(options["filename"])[-1])[0]
            appmod = imp.load_source(n, options["filename"])
            for name in dir(appmod):
                kls = getattr(appmod, name)
                if isinstance(kls, (type, types.ClassType)):
                    if issubclass(kls, cyclone.web.Application):
                        options["app"] = kls
                        if ssl_support and os.path.exists(options["ssl-cert"]):
                            options["ssl-app"] = kls

        # http
        if options["app"]:
            if callable(options["app"]):
                appmod = options["app"]
            else:
                appmod = reflect.namedAny(options["app"])

            if options["appopts"]:
                app = appmod(options["appopts"])
            else:
                app = appmod()

            unix = options.get("unix")
            if unix:
                s = internet.UNIXServer(unix, app)
            else:
                s = internet.TCPServer(options["port"], app,
                                       interface=options["listen"])
            s.setServiceParent(srv)

        # https
        if options["ssl-app"]:
            if ssl_support:
                if callable(options["ssl-app"]):
                    appmod = options["ssl-app"]
                else:
                    appmod = reflect.namedAny(options["ssl-app"])

                if options["ssl-appopts"]:
                    app = appmod(options["ssl-appopts"])
                else:
                    app = appmod()
                s = internet.SSLServer(options["ssl-port"], app,
                                       ssl.DefaultOpenSSLContextFactory(
                                       options["ssl-key"],
                                       options["ssl-cert"]),
                                       interface=options["ssl-listen"])
                s.setServiceParent(srv)
            else:
                print("SSL support is disabled. "
                      "Install PyOpenSSL and try again.")

        if s is None:
            print("usage: cyclone run [server.py|--help]")
            sys.exit(1)

        return srv

serviceMaker = ServiceMaker()
