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

import os
import sys

import cyclone.web

from twisted.python import log
from twisted.internet import reactor


# Helper function to convert bytes to human readable strings
humanreadable = lambda s: [(s % 1024 ** i and "%.1f" % (s / 1024.0 ** i) or \
                          str(s / 1024 ** i)) + x.strip() + "B" \
                          for i, x in enumerate(' KMGTPEZY') \
                          if s < 1024 ** (i + 1) or i == 8][0]


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
        ]
        settings = dict(
            debug=True,
            template_path="./template",
            repository_path="./uploaded_files",
        )

        if not os.path.exists(settings["repository_path"]):
            try:
                os.mkdir(settings["repository_path"])
            except Exception, e:
                print("mkdir failed: %s" % str(e))
                sys.exit(1)

        cyclone.web.Application.__init__(self, handlers, **settings)


class IndexHandler(cyclone.web.RequestHandler):
    def get(self):
        self.render("index.html", missing=[], info=None)

    def post(self):
        name = self.get_argument("fullname", None)
        if name is None:
            self.render("index.html", missing=["fullname"], info=None)
            return

        picture = self.request.files.get("picture")
        if picture is None:
            self.render("index.html", missing=["picture"], info=None)
            return
        else:
            picture = picture[0]

        # File properties
        filename = picture["filename"]
        content_type = picture["content_type"]
        body = picture["body"]  # bytes!

        try:
            fn = os.path.join(self.settings.repository_path, filename)
            fp = open(os.path.abspath(fn), "w")
            fp.write(body)
            fp.close()
        except Exception, e:
            log.msg("Could not write file: %s" % str(e))
            raise cyclone.web.HTTPError(500)

        self.render("index.html", missing=[], info={
                    "name": name,
                    "file": "%s, type=%s, size=%s" % \
                    (filename, content_type, humanreadable(len(body)))})


def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()


if __name__ == "__main__":
    main()
