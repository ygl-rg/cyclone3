# coding: utf-8
#
$license

import cyclone.escape
import cyclone.locale
import cyclone.web

from twisted.internet import defer
from twisted.python import log

from $modname.utils import BaseHandler
from $modname.utils import TemplateFields


class IndexHandler(BaseHandler):
    def get(self):
        self.render("index.html", hello='world', awesome='bacon')
        # another option would be
        # fields = {'hello': 'world', 'awesome': 'bacon'}
        # self.render('index.html', **fields)

    def post(self):
        tpl_fields = TemplateFields()
        tpl_fields['post'] = True
        tpl_fields['ip'] = self.request.remote_ip
        # you can also fetch your own config variables defined in
        # $modname.conf using
        # self.settings.raw.get('section', 'parameter')
        tpl_fields['mysql_host'] = self.settings.raw.get('mysql', 'host')
        self.render("post.html", fields=tpl_fields)


class LangHandler(BaseHandler):
    def get(self, lang_code):
        if lang_code in cyclone.locale.get_supported_locales():
            self.set_secure_cookie("lang", lang_code)

        self.redirect(self.request.headers.get("Referer",
                                               self.get_argument("next", "/")))

