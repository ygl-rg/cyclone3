# coding: utf-8
#
$license

import OpenSSL
import cyclone.escape
import cyclone.locale
import cyclone.mail
import cyclone.web
import hashlib
import random
import string

from datetime import datetime

from twisted.internet import defer
from twisted.python import log

from $modname import storage
from $modname.utils import BaseHandler
from $modname.utils import SessionMixin
from $modname.utils import TemplateFields


class IndexHandler(BaseHandler, SessionMixin):
    def get(self):
        if self.current_user:
            self.redirect("/dashboard")
        else:
            self.render("index.html")


class LangHandler(BaseHandler):
    def get(self, lang_code):
        if lang_code in cyclone.locale.get_supported_locales():
            self.set_secure_cookie("lang", lang_code, expires_days=20)

        self.redirect(self.request.headers.get("Referer",
                                           self.get_argument("next", "/")))


class DashboardHandler(BaseHandler):
    @cyclone.web.authenticated
    def get(self):
        self.render("dashboard.html")


class AccountHandler(BaseHandler, storage.DatabaseMixin):
    @cyclone.web.authenticated
    @storage.DatabaseSafe
    @defer.inlineCallbacks
    def get(self):
        user = yield storage.users.find_first(
                        where=("user_email=%s", self.current_user["email"]))

        if user:
            self.render("account.html",
                    fields=TemplateFields(full_name=user["user_full_name"]))
        else:
            self.clear_current_user()
            self.redirect("/")

    @cyclone.web.authenticated
    @storage.DatabaseSafe
    @defer.inlineCallbacks
    def post(self):
        user = yield storage.users.find_first(
                        where=("user_email=%s", self.current_user["email"]))
        if not user:
            self.clear_current_user()
            self.redirect("/")
            defer.returnValue(None)

        full_name = self.get_argument("full_name", None)
        f = TemplateFields(full_name=full_name)

        if full_name:
            full_name = full_name.strip()
            if len(full_name) > 80:
                f["err"] = ["invalid_name"]
                self.render("account.html", fields=f)
                defer.returnValue(None)
            elif full_name != user.user_full_name:
                user.user_full_name = full_name

        passwd_0 = self.get_argument("passwd_0", None)
        passwd_1 = self.get_argument("passwd_1", None)
        passwd_2 = self.get_argument("passwd_2", None)
        if passwd_0 and passwd_1:
            if hashlib.sha1(passwd_0).hexdigest() != user.user_passwd:
                f["err"] = ["old_nomatch"]
                self.render("account.html", fields=f)
                defer.returnValue(None)
            elif len(passwd_1) < 3 or len(passwd_1) > 20:
                f["err"] = ["invalid_passwd"]
                self.render("account.html", fields=f)
                defer.returnValue(None)
            elif passwd_1 != passwd_2:
                f["err"] = ["nomatch"]
                self.render("account.html", fields=f)
                defer.returnValue(None)
            else:
                user.user_passwd = hashlib.sha1(passwd_1).hexdigest()
        elif passwd_1:
            f["err"] = ["old_missing"]
            self.render("account.html", fields=f)
            defer.returnValue(None)

        if user.has_changes:
            yield user.save()
            f["updated"] = True

        self.render("account.html", fields=f)


class SignUpHandler(BaseHandler, storage.DatabaseMixin):
    def get(self):
        if self.get_current_user():
            self.redirect("/")
        else:
            self.render("signup.html", fields=TemplateFields())

    @storage.DatabaseSafe
    @defer.inlineCallbacks
    def post(self):
        email = self.get_argument("email", None)
        legal = self.get_argument("legal", None)

        f = TemplateFields(email=email, legal=legal)

        if legal != "on":
            f["err"] = ["legal"]
            self.render("signup.html", fields=f)
            defer.returnValue(None)

        if not email:
            f["err"] = ["email"]
            self.render("signup.html", fields=f)
            defer.returnValue(None)

        if not self.valid_email(email):
            f["err"] = ["email"]
            self.render("signup.html", fields=f)
            defer.returnValue(None)

        # check if the email is awaiting confirmation
        if (yield self.redis.exists("u:%s" % email)):
            f["err"] = ["exists"]
            self.render("signup.html", fields=f)
            defer.returnValue(None)

        # check if the email exists in the database
        if (yield storage.users.find_first(where=("user_email=%s", email))):
            f["err"] = ["exists"]
            self.render("signup.html", fields=f)
            defer.returnValue(None)

        # create random password
        random.seed(OpenSSL.rand.bytes(16))
        passwd = "".join(random.choice(string.letters + string.digits)
                            for x in range(8))

        # store temporary password in redis
        k = "u:%s" % email
        t = yield self.redis.multi()
        t.set(k, passwd)
        t.expire(k, 86400)  # 1 day
        yield t.commit()

        # prepare the confirmation email
        msg = cyclone.mail.Message(
                    mime="text/html",
                    charset="utf-8",
                    to_addrs=[email],
                    from_addr=self.settings.email_settings.username,
                    subject=self.render_string("signup_email_subject.txt")
                                .replace("\n", "").strip(),
                    message=self.render_string("signup_email.html",
                    passwd=passwd, ip=self.request.remote_ip,
                    date=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")))

        try:
            r = yield cyclone.mail.sendmail(self.settings.email_settings, msg)
        except Exception, e:
            # delete password from redis
            yield self.redis.delete(k)

            log.err("failed to send signup email to %s: %s" % (email, e))
            f["err"] = ["send"]
            self.render("signup.html", fields=f)
        else:
            log.msg("signup email sent to %s: %s" % (email, r))
            self.render("signup_ok.html", email=email)


class SignInHandler(BaseHandler, storage.DatabaseMixin):
    def get(self):
        if self.get_current_user():
            self.redirect("/")
        else:
            self.render("signin.html", fields=TemplateFields())

    @storage.DatabaseSafe
    @defer.inlineCallbacks
    def post(self):
        email = self.get_argument("email", "")
        passwd = self.get_argument("passwd", "")
        remember = self.get_argument("remember", "")

        f = TemplateFields(email=email, remember=remember)

        if not email:
            f["err"] = ["auth"]
            self.render("signin.html", fields=f)
            defer.returnValue(None)

        if not self.valid_email(email):
            f["err"] = ["auth"]
            self.render("signin.html", fields=f)
            defer.returnValue(None)

        if not passwd:
            f["err"] = ["auth"]
            self.render("signin.html", fields=f)
            defer.returnValue(None)

        user = None

        # check if the user is awaiting confirmation
        k = "u:%s" % email
        pwd = yield self.redis.get(k)
        if pwd:
            if pwd != passwd:
                f["err"] = ["auth"]
                self.render("signin.html", fields=f)
                defer.returnValue(None)
            else:
                # check if the user is already in mysql
                user = yield storage.users.find_first(
                                            where=("user_email=%s", email))

                if not user:
                    # create the user in mysql
                    user = storage.users.new(user_email=email)

                user.user_passwd = hashlib.sha1(pwd).hexdigest()
                user.user_is_active = True

                yield user.save()
                yield self.redis.delete(k)

        if not user:
            user = yield storage.users.find_first(
                            where=("user_email=%s and user_passwd=%s",
                                    email, hashlib.sha1(passwd).hexdigest()))

            if not user:
                f["err"] = ["auth"]
                self.render("signin.html", fields=f)
                defer.returnValue(None)

        # always update the lang cookie
        if self.locale.code in cyclone.locale.get_supported_locales():
            self.set_secure_cookie("lang", self.locale.code, expires_days=20)

        # set session cookie
        self.set_current_user(email=email,
                                expires_days=15 if remember else None)
        self.redirect("/")


class SignOutHandler(BaseHandler):
    @cyclone.web.authenticated
    def get(self):
        self.clear_current_user()
        self.redirect("/")


class PasswdHandler(BaseHandler, storage.DatabaseMixin):
    def get(self):
        if self.get_current_user():
            self.redirect("/")
        else:
            self.render("passwd.html", fields=TemplateFields())

    @storage.DatabaseSafe
    @defer.inlineCallbacks
    def post(self):
        email = self.get_argument("email", None)

        f = TemplateFields(email=email)

        if not email:
            f["err"] = ["email"]
            self.render("passwd.html", fields=f)
            defer.returnValue(None)

        if not self.valid_email(email):
            f["err"] = ["email"]
            self.render("passwd.html", fields=f)
            defer.returnValue(None)

        k = "u:%s" % email

        # check if the user exists in redis, or mysql
        if (yield self.redis.exists(k)):
            f["err"] = ["pending"]
            self.render("passwd.html", fields=f)
            defer.returnValue(None)
        elif not (yield storage.users.find_first(
                                        where=("user_email=%s", email))):
            f["err"] = ["notfound"]
            self.render("passwd.html", fields=f)
            defer.returnValue(None)

        # create temporary password and store in redis
        random.seed(OpenSSL.rand.bytes(16))
        passwd = "".join(random.choice(string.letters + string.digits)
                            for x in range(8))

        t = yield self.redis.multi()
        t.set(k, passwd)
        t.expire(k, 86400)  # 1 day
        yield t.commit()

        # prepare the confirmation email
        msg = cyclone.mail.Message(
                    mime="text/html",
                    charset="utf-8",
                    to_addrs=[email],
                    from_addr=self.settings.email_settings.username,
                    subject=self.render_string("passwd_email_subject.txt")
                                .replace("\n", "").strip(),
                    message=self.render_string("passwd_email.html",
                    passwd=passwd, ip=self.request.remote_ip,
                    date=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")))

        try:
            r = yield cyclone.mail.sendmail(self.settings.email_settings, msg)
        except Exception, e:
            # do not delete from redis
            # yield self.redis.delete(k)

            log.err("failed to send passwd email to %s: %s" % (email, e))
            f["err"] = ["send"]
            self.render("passwd.html", fields=f)
        else:
            log.msg("passwd email sent to %s: %s" % (email, r))
            self.render("passwd_ok.html", email=email)
