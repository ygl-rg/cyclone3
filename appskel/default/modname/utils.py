# coding: utf-8
#
$license

import cyclone.escape
import cyclone.web


class TemplateFields(dict):
    """Helper class to make sure our
        template doesn't fail due to an invalid key"""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name, value):
        self[name] = value


class BaseHandler(cyclone.web.RequestHandler):
    #def get_current_user(self):
    #    user_json = self.get_secure_cookie("user")
    #    if user_json:
    #        return cyclone.escape.json_decode(user_json)

    def get_user_locale(self):
        lang = self.get_secure_cookie("lang")
        if lang:
            return cyclone.locale.get(lang)
