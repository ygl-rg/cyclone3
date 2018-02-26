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
        handlers = [
            (r"/",              views.IndexHandler),
            (r"/lang/(.+)",     views.LangHandler),
            (r"/sample/mysql",  views.SampleMySQLHandler),
            (r"/sample/redis",  views.SampleRedisHandler),
            (r"/sample/sqlite", views.SampleSQLiteHandler),
        ]

        conf = config.parse_config(config_file)

        # Initialize locales
        if "locale_path" in conf:
            cyclone.locale.load_gettext_translations(conf["locale_path"],
                                                     "$modname")

        # Set up database connections
        DatabaseMixin.setup(conf)

        #conf["login_url"] = "/auth/login"
        #conf["autoescape"] = None
        cyclone.web.Application.__init__(self, handlers, **conf)
