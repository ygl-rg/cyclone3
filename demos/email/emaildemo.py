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

import os.path
import sys

import cyclone.mail
import cyclone.web

from twisted.python import log
from twisted.internet import defer, reactor


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", cyclone.web.RedirectHandler, {"url": "/static/index.html"}),
            (r"/sendmail", SendmailHandler),
        ]
        settings = dict(
            debug=True,
            static_path="./static",
            template_path="./template",
            email_settings=dict(
                host="smtp.gmail.com",  # mandatory
                port=587,               # optional. default=25 or 587 for TLS
                tls=True,               # optional. default=False
                username="foo",         # optional. no default
                password="bar",         # optional. no default
            )
        )
        cyclone.web.Application.__init__(self, handlers, **settings)


class SendmailHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    def post(self):
        to_addrs = self.get_argument("to_addrs").split(",")
        subject = self.get_argument("subject")
        message = self.get_argument("message")
        content_type = self.get_argument("content_type")

        # message may also be an html template:
        # message = self.render_string("email.html", name="foobar")

        msg = cyclone.mail.Message(
            from_addr="you@domain.com",
            to_addrs=to_addrs,
            subject=subject,
            message=message,
            mime=content_type,  # optional. default=text/plain
            charset="utf-8")    # optional. default=utf-8

        img_path = os.path.join(self.settings.static_path, "me.png")
        msg.attach(img_path, mime="image/png")

        txt_path = os.path.join(self.settings.static_path, "info.txt")
        msg.attach(txt_path, mime="text/plain", charset="utf-8")

        msg.attach("fake.txt", mime="text/plain", charset="utf-8",
                   content="this file is fake!")

        msg.add_header('X-MailTag', 'sampleUpload')  # custom email header

        try:
            response = yield cyclone.mail.sendmail(
                                self.settings.email_settings, msg)
            self.render("response.html", title="Success", response=response)
        except Exception, e:
            self.render("response.html", title="Failure", response=str(e))


def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()


if __name__ == "__main__":
    main()
