#!/usr/bin/env python
# coding: utf-8

import sys
import os.path
from github import GitHubMixin
import cyclone.escape
import cyclone.web
from twisted.python import log
from twisted.internet import reactor
from cyclone import escape

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
            github_client_id="see README",
            github_secret="see README",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True,
        )
        cyclone.web.Application.__init__(self, handlers, **settings)


class BaseHandler(cyclone.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            return None
        return cyclone.escape.json_decode(user_json)


class MainHandler(BaseHandler, GitHubMixin):
    @cyclone.web.authenticated
    @cyclone.web.asynchronous
    def get(self):
        access_token = self.current_user.get("access_token", None)

        if access_token:
            self.github_request("/gists", self._get_gists,
                                access_token=self.current_user["access_token"])
        else:
            self.redirect("/auth/login")

    def _get_gists(self, response):
        if response is None:
            # Session may have expired
            self.redirect("/auth/login")
            return
        self.render("gists.html",
                gists=cyclone.escape.json_decode(response.body))


class AuthLoginHandler(BaseHandler, GitHubMixin):
    @cyclone.web.asynchronous
    def get(self):
        my_url = (self.request.protocol + "://" + self.request.host +
                  "/auth/login?next=" +
                  cyclone.escape.url_escape(self.get_argument("next", "/")))

        if self.get_argument("code", False):
            self.get_authenticated_user(
                redirect_uri=my_url,
                client_id=self.settings["github_client_id"],
                client_secret=self.settings["github_secret"],
                code=self.get_argument("code"),
                callback=self._on_auth)
            return

        self.authorize_redirect(redirect_uri=my_url,
                                client_id=self.settings["github_client_id"],
                                extra_params={"scope": "bonito"})

    def _on_auth(self, user):
        if not user:
            raise cyclone.web.HTTPError(500, "GitHub auth failed")
        self.set_secure_cookie("user", cyclone.escape.json_encode(user))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler, cyclone.auth.FacebookGraphMixin):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


def main():
    reactor.listenTCP(8888, Application())
    reactor.run()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    main()
