# coding: utf-8
#
$license

import cyclone.locale
import cyclone.web

from $modname import views
from $modname import config


class Application(cyclone.web.Application):
    def __init__(self, config_file):
        handlers = [
            (r"/",              views.IndexHandler),
            (r"/lang/(.+)",     views.LangHandler),
        ]

        settings = config.parse_config(config_file)

        # Initialize locales
        locales = settings.get("locale_path")
        if locales:
            cyclone.locale.load_gettext_translations(locales, "$modname")

        #settings["login_url"] = "/auth/login"
        #settings["autoescape"] = None
        cyclone.web.Application.__init__(self, handlers, **settings)
