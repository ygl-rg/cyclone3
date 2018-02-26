# coding: utf-8
#
$license

import cyclone.locale
import cyclone.web

from $modname import views
from $modname import config
from $modname.storage import DatabaseMixin


class Application(cyclone.web.Application):
    def __init__(self, config_file):
        conf = config.parse_config(config_file)
        handlers = [
            (r"/",          views.IndexHandler),
            (r"/lang/(.+)", views.LangHandler),
            (r"/dashboard", views.DashboardHandler),
            (r"/account",   views.AccountHandler),
            (r"/signup",    views.SignUpHandler),
            (r"/signin",    views.SignInHandler),
            (r"/signout",   views.SignOutHandler),
            (r"/passwd",    views.PasswdHandler),
            (r"/legal",     cyclone.web.RedirectHandler,
                                {"url": "/static/legal.txt"}),
        ]

        # Initialize locales
        if "locale_path" in conf:
            cyclone.locale.load_gettext_translations(conf["locale_path"],
                                                     "$modname")

        # Set up database connections
        DatabaseMixin.setup(conf)

        conf["login_url"] = "/signin"
        conf["autoescape"] = None
        cyclone.web.Application.__init__(self, handlers, **conf)
