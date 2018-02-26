import cyclone.web
import cyclone.auth
from twisted.python import log
from twisted.internet import task, defer, reactor
import sys
from dropbox import DropboxMixin

class AuthHandler(cyclone.web.RequestHandler, DropboxMixin):
    @cyclone.web.asynchronous
    @defer.inlineCallbacks
    def get(self):
        code = self.get_argument("code", None)

        if code:
            user = yield self.get_authenticated_user(code=code)
            print user
            self.set_secure_cookie("oauth_user", user.get("uid", ""))
            self.set_secure_cookie("oauth_token", user.get("access_token", ""))
            self.redirect("/")
        else:
            yield self.authorize_redirect()


class LogoutHandler(cyclone.web.RequestHandler, DropboxMixin):
    def get(self):
        self.clear_cookie("oauth_user")
        self.clear_cookie("oauth_token")
        return "Logged out"
                                 

class MainHandler(cyclone.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("oauth_user")

    #@cyclone.web.authenticated
    def get(self):
        user = self.get_current_user()
        print user
        if not user:
            raise cyclone.web.HTTPError(401, "Access denied")

        self.write("Welcome back, {}".format(user))


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/auth", AuthHandler),
            (r"/logout", LogoutHandler),
            (r"/", MainHandler),
        ]


        opts = {
            "cookie_secret": "II*^WvQiOkv)QihQwQZ<JH!YY/q)v%TY",
            "debug": True,
            "login_url": "http://localhost:8888/auth",
            #https://www.dropbox.com/developers
            "dropbox_oauth": {
                "redirect": "http://localhost:8888/auth",

                "key": "",
                "secret": ""
            }
        }

        cyclone.web.Application.__init__(self, handlers, **opts)

def main():
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, Application(), interface="127.0.0.1")
    reactor.run()

if __name__ == "__main__":
    main()
