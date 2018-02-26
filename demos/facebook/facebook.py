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
import os.path
import cyclone.auth
import cyclone.escape
import cyclone.web
from twisted.python import log
from twisted.internet import reactor


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
        ]
        settings = dict(
            cookie_secret="12oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            facebook_api_key="9e2ada1b462142c4dfcc8e894ea1e37c",
            facebook_secret="32fc6114554e3c53d5952594510021e2",
            ui_modules={"Post": PostModule},
            debug=True,
        )
        cyclone.web.Application.__init__(self, handlers, **settings)


class BaseHandler(cyclone.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            return None
        return cyclone.escape.json_decode(user_json)


class MainHandler(BaseHandler, cyclone.auth.FacebookMixin):
    @cyclone.web.authenticated
    @cyclone.web.asynchronous
    def get(self):
        self.facebook_request(
            method="stream.get",
            callback=self._on_stream,
            session_key=self.current_user["session_key"])

    def _on_stream(self, stream):
        if stream is None:
            # Session may have expired
            self.redirect("/auth/login")
            return
        # Turn profiles into a dict mapping id => profile
        stream["profiles"] = dict((p["id"], p) for p in stream["profiles"])
        self.render("stream.html", stream=stream)


class AuthLoginHandler(BaseHandler, cyclone.auth.FacebookMixin):
    @cyclone.web.asynchronous
    def get(self):
        if self.get_argument("session", None):
            self.get_authenticated_user(self._on_auth)
            return
        self.authorize_redirect("read_stream")

    def _on_auth(self, user):
        if not user:
            raise cyclone.web.HTTPError(500, "Facebook auth failed")
        self.set_secure_cookie("user", cyclone.escape.json_encode(user))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler, cyclone.auth.FacebookMixin):
    @cyclone.web.asynchronous
    def get(self):
        self.clear_cookie("user")
        if not self.current_user:
            self.redirect(self.get_argument("next", "/"))
            return
        self.facebook_request(
            method="auth.revokeAuthorization",
            callback=self._on_deauthorize,
            session_key=self.current_user["session_key"])

    def _on_deauthorize(self, response):
        self.redirect(self.get_argument("next", "/"))


class PostModule(cyclone.web.UIModule):
    def render(self, post, actor):
        return self.render_string("modules/post.html", post=post, actor=actor)


def main():
    reactor.listenTCP(8888, Application())
    reactor.run()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    main()
