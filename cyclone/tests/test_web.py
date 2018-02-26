#
# Copyright 2014 David Novakovic
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


from twisted.trial import unittest
from cyclone.web import RequestHandler, HTTPError
from cyclone.web import Application, URLSpec, URLReverseError
from cyclone.escape import unicode_type
from unittest.mock import Mock
from datetime import datetime
from http import cookies as http_cookies
import email.utils
import calendar
import time
from twisted.internet import defer, reactor
from cyclone.template import DictLoader


class RequestHandlerTest(unittest.TestCase):
    def assertHasAttr(self, obj, attr_name):
        assert hasattr(obj, attr_name)

    def setUp(self):
        self.app = Application(some_setting="foo")
        self.request = Mock()
        self.rh = RequestHandler(self.app, self.request)

    def test_init(self):
        self.assertHasAttr(self.rh, "application")
        self.assertHasAttr(self.rh, "request")
        self.assertHasAttr(self.rh, "path_args")
        self.assertHasAttr(self.rh, "path_kwargs")
        self.assertHasAttr(self.rh, "ui")

    def test_settings(self):
        self.assertEqual(self.rh.settings, {"some_setting": "foo"})

    def test_default(self):
        self.assertRaises(HTTPError, self.rh.default)

    def test_prepare(self):
        self.assertEqual(self.rh.prepare(), None)

    def test_on_finish(self):
        self.assertEqual(self.rh.on_finish(), None)

    def test_on_connection_close(self):
        self.assertEqual(self.rh.on_connection_close(), None)

    def test_clear(self):
        self.request.headers = {
            "Connection": "Keep-Alive"
        }
        self.request.supports_http_1_1.return_value = False
        self.rh.clear()
        self.assertEqual(
            set(self.rh._headers.keys()),
            set(["Server", "Content-Type", "Date", "Connection"])
        )
        self.assertEqual(self.rh._list_headers, [])

    def test_set_status(self):
        self.rh.set_status(200)
        self.assertEqual(self.rh._status_code, 200)

    def test_set_status_with_reason(self):
        self.rh.set_status(200, "reason")
        self.assertEqual(self.rh._status_code, 200)
        self.assertEqual(self.rh._reason, "reason")

    def test_set_status_with_invalid_code(self):
        self.assertRaises(ValueError, self.rh.set_status, 9999)

    def test_get_status(self):
        self.rh.set_status(200)
        self.assertEqual(self.rh.get_status(), 200)

    def test_add_header(self):
        self.rh.add_header("X-Header", "something")
        self.assertEqual(
            self.rh._list_headers,
            [("X-Header", "something")]
        )
        self.rh.add_header("X-Header", "something")
        self.assertEqual(
            self.rh._list_headers,
            [("X-Header", "something"), ("X-Header", "something")]
        )

    def test_clear_header(self):
        self.rh.set_header("X-Header", "something")
        self.assertTrue("X-Header" in self.rh._headers)
        self.rh.clear_header("X-Header")
        self.assertTrue("X-Header" not in self.rh._headers)

    def test_convert_header_value(self):
        value = self.rh._convert_header_value("Value")
        self.assertEqual(value, "Value")

    def test_convert_unicode_header_value(self):
        value = self.rh._convert_header_value(u"Value")
        self.assertEqual(value, "Value")
        self.assertTrue(type(value) != unicode_type)

    def test_convert_unicode_datetime_header_value(self):
        now = datetime(2014, 4, 4)
        result = self.rh._convert_header_value(now)
        self.assertEqual(
            result,
            "Fri, 04 Apr 2014 00:00:00 GMT"
        )

    def test_convert_invalid_value(self):

        class Nothing:
            pass

        self.assertRaises(TypeError, self.rh._convert_header_value, Nothing())

    def test_convert_long_value(self):
        self.assertRaises(
            ValueError, self.rh._convert_header_value, "a" * 5000)

    def test_get_argument(self):
        self.rh.get_arguments = Mock()
        self.rh.get_arguments.return_value = ["a"]
        self.rh.get_argument("test")
        self.rh.get_arguments.assert_called_with("test", strip=True)
        self.rh.get_arguments.return_value = None
        self.assertEqual(
            self.rh.get_argument("arg", "something"),
            "something"
        )
        self.assertRaises(HTTPError, self.rh.get_argument, "arg")

    def test_get_arguments(self):
        self.rh.request.arguments = {"arg": ["something"]}
        val = self.rh.get_arguments("arg")
        self.assertEqual(val, ["something"])

    def test_cookies(self):
        self.rh.request.cookies = "rawr"
        self.assertEqual(self.rh.cookies, "rawr")

    def test_decode_argument(self):
        self.assertEqual(
            self.rh.decode_argument("somearg"),
            "somearg"
        )

    def test_get_cookie(self):
        morsel = Mock()
        morsel.value = "value"
        self.rh.request.cookies = {"testcookie": morsel}
        val = self.rh.get_cookie("testcookie")
        self.assertEqual(val, "value")
        val = self.rh.get_cookie("non_existent")
        self.assertEqual(val, None)

    def test_set_cookie(self):
        self.rh.set_cookie("mycookie", "cookievalue")
        self.assertEqual(
            self.rh._new_cookie["mycookie"].value,
            "cookievalue"
        )

    def test_set_invalid_cookie(self):
        self.assertRaises(
            ValueError, self.rh.set_cookie, "\x00bbb", "badcookie")

    def test_set_cookie_already_exists(self):
        self.rh._new_cookie = http_cookies.SimpleCookie()
        self.rh._new_cookie["name"] = "value"
        self.rh.set_cookie("name", "value")

    def test_set_cookie_domain(self):
        self.rh.set_cookie("name", "value", domain="foo.com")
        self.assertEqual(
            self.rh._new_cookie["name"]['domain'],
            "foo.com"
        )

    def test_set_cookie_expires_days(self):
        self.rh.set_cookie("name", "value", expires_days=5, max_age=55)
        expires = self.rh._new_cookie["name"]['expires']
        self.assertTrue(
            email.utils.parsedate(expires) >
            time.gmtime(),
        )

    def test_clear_cookie(self):
        morsel = Mock()
        self.rh.request.cookies = {"testcookie": morsel}
        self.rh.set_cookie("name", "value")
        self.rh.clear_cookie("name")
        self.assertEqual(None, self.rh.get_cookie("name"))

    def test_clear_all_cookies(self):
        self.rh.clear_cookie = Mock()
        self.rh.request.cookies = {"foo": None}
        self.rh.clear_all_cookies()
        self.rh.clear_cookie.assert_called_with("foo")

    def test_redirect_too_late(self):
        self.rh._headers_written = True
        self.assertRaises(Exception, self.rh.redirect, "/")

    def test_redirect_with_perm(self):
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.rh.redirect("/", permanent=True)

    def test_redirect_with_slashes(self):
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.assertRaises(
            AssertionError,
            self.rh.redirect,
            "//example.com",
            status=400)

    def test_redirect_bad_url(self):
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.rh.request.uri = "foo"
        self.rh.redirect("http://foo.com", permanent=True)

    def test_write_when_finished(self):
        self.rh._finished = True
        self.assertRaises(RuntimeError, self.rh.write, "foo")

    def test_write_dict(self):
        self.rh.write({"foo": "bar"})
        self.assertEqual(
            self.rh._write_buffer,
            ['{"foo": "bar"}']
        )

    def test_create_template_loader(self):
        self.rh.application.settings = {"autoescape": True}
        res = self.rh.create_template_loader("/foo")
        self.assertTrue(res)

    def test_finish_already_finished(self):
        self.rh._finished = True
        self.assertRaises(RuntimeError, self.rh.finish)

    def test_finish_304_with_body(self):
        self.rh._status_code = 304
        self.rh._write_buffer = ""
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.rh.finish()

    def test_send_error(self):
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.rh.write_error = Mock()
        self.rh.send_error()
        self.rh.write_error.assert_called_with(500)

    def test_write_error(self):
        self.rh.flush = Mock()
        self.rh._log = Mock()
        self.rh.get_error_html = Mock()
        exc = [Mock(), Mock()]
        self.rh.finish = Mock()
        self.rh.write_error(500, exc_info=exc)

    def test_locale(self):
        self.request.headers = {
            "Accept-Language": "en"
        }
        self.rh.locale

    def test_get_user_locale(self):
        self.rh.get_user_locale()

    def test_get_browser_locale(self):
        self.request.headers = {
            "Accept-Language": "en"
        }
        self.rh.get_browser_locale()

    def test_current_user(self):
        self.rh.current_user

    def test_xsrf_token(self):
        self.request.cookies = {}
        self.rh.xsrf_token

    def test_check_xsrf_cookie(self):
        self.request.arguments = {self.rh.xsrf_cookie_name: "foo"}
        self.request.cookies = {}
        self.assertRaises(HTTPError, self.rh.check_xsrf_cookie)

    def test_xsrf_form_html(self):
        self.request.arguments = {self.rh.xsrf_cookie_name: "foo"}
        self.request.cookies = {}
        self.rh.xsrf_form_html()

    def test_static_url(self):
        self.rh.application.settings = {"static_path": "."}
        self.rh.static_url("/")


class TestUrlSpec(unittest.TestCase):

    def test_reverse(self):
        spec = URLSpec("/page", None)
        self.assertEqual(spec.reverse(), "/page")
        self.assertRaises(
            URLReverseError,
            lambda: spec.reverse(42)
        )
        self.assertEqual(
            spec.reverse(name="val ue"),
            "/page?name=val+ue")
        self.assertEqual(
            spec.reverse(name="value", val2=42),
            "/page?name=value&val2=42")

        spec = URLSpec("/page/(d+)", None)
        self.assertRaises(
            URLReverseError,
            lambda: spec.reverse()
        )
        self.assertEqual(spec.reverse(1), "/page/1")
        self.assertEqual(
            spec.reverse(15, name="test"),
            "/page/15?name=test")

        spec = URLSpec("/page/(d+)/(/d+)/(/d+)", None)
        self.assertRaises(
            URLReverseError,
            lambda: spec.reverse()
        )
        self.assertRaises(
            URLReverseError,
            lambda: spec.reverse(1)
        )
        self.assertRaises(
            URLReverseError,
            lambda: spec.reverse(1, 2)
        )
        self.assertEqual(spec.reverse(11, 22, 33), "/page/11/22/33")
        self.assertEqual(
            spec.reverse(11, 22, 33, hello="world"),
            "/page/11/22/33?hello=world")


class TestRequestHandler(unittest.TestCase):

    @defer.inlineCallbacks
    def test_render_string(self):
        _mkDeferred = self._mkDeferred
        self.assertEqual(
            self.handler.render_string("simple.html", msg="Hello World!"),
            "simple: Hello World!"
        )
        self.assertEqual(
            self.handler.render_string(
                "simple.html", msg=_mkDeferred("Hello Deferred!")),
            "simple: Hello Deferred!"
        )
        d = self.handler.render_string(
            "simple.html",
            msg=_mkDeferred("Hello Deferred!", 0.1))
        self.assertTrue(isinstance(d, defer.Deferred), d)
        msg = yield d
        self.assertEqual(msg, "simple: Hello Deferred!")

    def test_generate_headers(self):
        headers = self.handler._generate_headers()
        self.assertIn(
            "HTTP MOCK 200 OK",
            headers,
        )

    """
    @defer.inlineCallbacks
    def test_simple_handler(self):
        self.handler.get = lambda: self.handler.finish("HELLO WORLD")
        page = yield self._execute_request(False)
        self.assertEqual(page, "HELLO WORLD")
    """

    """
    @defer.inlineCallbacks
    def test_deferred_handler(self):
        self.handler.get = lambda: self._mkDeferred(
            lambda: self.handler.finish("HELLO DEFERRED"), 0.01)
        page = yield self._execute_request(False)
        self.assertEqual(page, "HELLO DEFERRED")
    """

    """
    @defer.inlineCallbacks
    def test_deferred_arg_in_render(self):
        templateArg = self._mkDeferred("it works!", 0.1)
        handlerGetFn = lambda: self.handler.render(
            "simple.html", msg=templateArg)
        self.handler.get = handlerGetFn
        page = yield self._execute_request(False)
        self.assertEqual(page, "simple: it works!")
    """

    def setUp(self):
        self.app = app = Mock()
        app.ui_methods = {}
        app.ui_modules = {}
        app.settings = {
            "template_loader": DictLoader({
                "simple.html": "simple: {{msg}}",
            }),
        }

        self.request = request = Mock()
        request.headers = {}
        request.method = "GET"
        request.version = "HTTP MOCK"
        request.notifyFinish.return_value = defer.Deferred()
        request.supports_http_1_1.return_value = True

        self.handler = RequestHandler(app, request)
        self._onFinishD = defer.Deferred()

        origFinish = self.handler.on_finish
        self.handler.on_finish = lambda: (
            origFinish(),
            self._onFinishD.callback(None),
        )

    def _mkDeferred(self, rv, delay=None):
        d = defer.Deferred()

        if callable(rv):
            cb = lambda: d.callback(rv())
        else:
            cb = lambda: d.callback(rv)

        if delay is None:
            cb()
        else:
            reactor.callLater(delay, cb)
        return d

    @defer.inlineCallbacks
    def _execute_request(self, outputHeaders):
        handler = self.handler

        handler._headers_written = True
        handler._execute([])
        yield self._onFinishD

        out = ""
        for (args, kwargs) in self.request.write.call_args_list:
            self.assertFalse(kwargs)
            self.assertEqual(len(args), 1)
            out += args[0]
        defer.returnValue(out)
