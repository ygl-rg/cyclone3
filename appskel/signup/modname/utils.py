# coding: utf-8
#
$license

import OpenSSL
import cyclone.escape
import cyclone.web
import httplib
import re
import uuid

from twisted.internet import defer

from $modname.storage import DatabaseMixin


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
    _email = re.compile("^[a-zA-Z0-9._%-]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,8}$$")

    def valid_email(self, email):
        return self._email.match(email)

    def set_current_user(self, expires_days=1, **kwargs):
        self.set_secure_cookie("user", cyclone.escape.json_encode(kwargs),
                                expires_days=expires_days)

    def get_current_user(self):
        user_json = self.get_secure_cookie("user", max_age_days=1)
        if user_json:
            return cyclone.escape.json_decode(user_json)

    def clear_current_user(self):
        self.clear_cookie("user")

    def get_user_locale(self):
        lang = self.get_secure_cookie("lang")
        if lang:
            return cyclone.locale.get(lang)

    # custom http error pages
    def write_error(self, status_code, **kwargs):
        kwargs["code"] = status_code
        kwargs["message"] = httplib.responses[status_code]
        try:
            self.render("error_%d.html" % status_code, fields=kwargs)
        except IOError:
            self.render("error_all.html", fields=kwargs)


class SessionMixin(DatabaseMixin):
    session_cookie_name = "session"
    session_redis_prefix = "$modname:s:"

    @property
    def session_redis_key(self):
        token = self.get_secure_cookie(self.session_cookie_name)
        if token:
            return "%s%s" % (self.session_redis_prefix, token)

    @defer.inlineCallbacks
    def session_create(self, expires_days=1, **kwargs):
        if not kwargs:
            raise ValueError("session_create requires one or more key=val")

        token = uuid.UUID(bytes=OpenSSL.rand.bytes(16)).hex
        k = "%s%s" % (self.session_redis_prefix, token)

        yield self.redis.hmset(k, kwargs)
        yield self.redis.expire(k, expires_days * 86400)

        self.set_secure_cookie(self.session_cookie_name, token,
                                expires_days=expires_days)
        defer.returnValue(token)

    @defer.inlineCallbacks
    def session_exists(self):
        k = self.session_redis_key
        if k:
            defer.returnValue((yield self.redis.exists(k)))

    @defer.inlineCallbacks
    def session_set(self, **kwargs):
        if not kwargs:
            raise ValueError("session_set requires one or more key=val")

        k = self.session_redis_key
        if k:
            yield self.redis.hmset(k, kwargs)
            defer.returnValue(True)

    @defer.inlineCallbacks
    def session_get(self, *args):
        if not args:
            raise ValueError("session_get requires one or more key names")

        k = self.session_redis_key
        if k:
            r = yield self.redis.hmget(k, args)
            defer.returnValue(r[0] if len(args) == 1 else r)

    @defer.inlineCallbacks
    def session_getall(self):
        k = self.session_redis_key
        if k:
            defer.returnValue((yield self.redis.hgetall(k)))

    @defer.inlineCallbacks
    def session_destroy(self):
        k = self.session_redis_key
        if k:
            yield self.redis.delete(k)
            defer.returnValue(True)
