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

import cyclone.locale
import cyclone.web

from twisted.python import log
from twisted.internet import reactor


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
            (r"/hello", HelloHandler),
        ]
        settings = dict(
            debug=True,
            template_path="./frontend/template",
        )
        cyclone.locale.load_gettext_translations("./frontend/locale", "mytest")
        cyclone.web.Application.__init__(self, handlers, **settings)


class BaseHandler(cyclone.web.RequestHandler):
    def get_user_locale(self):
        lang = self.get_cookie("lang", default="en_US")
        return cyclone.locale.get(lang)


class IndexHandler(BaseHandler):
    def _apples(self):
        try:
            return int(self.get_argument("apples", 1))
        except:
            return 1

    def get(self):
        self.render("index.html",
                    apples=self._apples(),
                    locale=self.locale.code,
                    languages=cyclone.locale.get_supported_locales())

    def post(self):
        lang = self.get_argument("lang")
        # assert lang in cyclone.locale.get_supported_locales()

        # Either set self._locale or override get_user_locale()
        #   self._locale = cyclone.locale.get(lang)
        #   self.render(...)

        self.set_cookie("lang", lang)
        self.redirect("/?apples=%d" % self._apples())


class HelloHandler(BaseHandler):
    def get(self):
        # Test with es_ES or pt_BR:
        # curl -D - -H "Cookie: lang=es_ES" http://localhost:8888/hello
        _ = self.locale.translate
        msg = _("hello world")
        text = self.render_string("hello.txt", msg=msg)
        self.set_header("Content-Type", "text/plain")
        self.write(text)


def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()


if __name__ == "__main__":
    main()
