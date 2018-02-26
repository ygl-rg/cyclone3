# coding: utf-8
#
# Copyright 2010 Alexandre Fiori
# based on the original Tornado by Facebook
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

"""
The cyclone web framework looks a bit like web.py (http://webpy.org/) or
Google's webapp (http://code.google.com/appengine/docs/python/tools/webapp/),
but with additional tools and optimizations to take advantage of the
non-blocking web server and tools.

Here is the canonical "Hello, world" example app::

    import cyclone.web
    from twisted.internet import reactor

    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            self.write("Hello, world")

    if __name__ == "__main__":
        application = cyclone.web.Application([
            (r"/", MainHandler),
        ])
        reactor.listenTCP(8888, application)
        reactor.run()

See the cyclone walkthrough on http://cyclone.io for more details and a good
getting started guide.

Thread-safety notes
-------------------

In general, methods on RequestHandler and elsewhere in cyclone are not
thread-safe.  In particular, methods such as write(), finish(), and
flush() must only be called from the main thread.  For more information on
using threads, please check the twisted documentation:
http://twistedmatrix.com/documents/current/core/howto/threading.html
"""

from __future__ import absolute_import, division, with_statement

#import Cookie
from http import cookies as http_cookies
from http import client as http_client
import base64
import binascii
import calendar
import datetime
import email.utils
import functools
import gzip
import hashlib
import hmac
import itertools
import mimetypes
import numbers
import os.path
import re
import stat
import sys
import threading
import time
import traceback
import types
import urllib
#import urlparse
from urllib import parse as urllib_parse
import uuid

import cyclone
from cyclone import escape
from cyclone import httpserver
from cyclone import locale
from cyclone import template
from cyclone.escape import utf8, _unicode
from cyclone.util import ObjectDict
from cyclone.util import bytes_type
from cyclone.util import import_object
from cyclone.util import unicode_type
from io import BytesIO
from twisted.python import failure
from twisted.python import log
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor


class RequestHandler(object):
    """Subclass this class and define get() or post() to make a handler.

    If you want to support more methods than the standard GET/HEAD/POST, you
    should override the class variable SUPPORTED_METHODS in your
    RequestHandler class.

    If you want lists to be serialized when calling self.write() set
    serialize_lists to True.
    This may have some security implications if you are not protecting against
    XSRF with other means (such as a XSRF token).
    More details on this vulnerability here:
    http://haacked.com/archive/2008/11/20/anatomy-of-a-subtle-json-vulnerability.aspx
    """
    SUPPORTED_METHODS = ("GET", "HEAD", "POST", "DELETE", "PATCH", "PUT",
                         "OPTIONS")

    serialize_lists = False
    no_keep_alive = False
    xsrf_cookie_name = "_xsrf"
    _template_loaders = {}  # {path: template.BaseLoader}
    _template_loader_lock = threading.Lock()

    def __init__(self, application, request, **kwargs):
        super(RequestHandler, self).__init__()

        self.application = application
        self.request = request
        self._headers_written = False
        self._finished = False
        self._auto_finish = True
        self._transforms = None  # will be set in _execute
        self.path_args = None
        self.path_kwargs = None
        self.ui = ObjectDict((n, self._ui_method(m)) for n, m in
                     application.ui_methods.items())
        # UIModules are available as both `modules` and `_modules` in the
        # template namespace.  Historically only `modules` was available
        # but could be clobbered by user additions to the namespace.
        # The template {% module %} directive looks in `_modules` to avoid
        # possible conflicts.
        self.ui["_modules"] = ObjectDict((n, self._ui_module(n, m)) for n, m in
                                 application.ui_modules.items())
        self.ui["modules"] = self.ui["_modules"]
        self.clear()
        self.request.connection.no_keep_alive = self.no_keep_alive
        self.initialize(**kwargs)

    def initialize(self, **kwargs):
        """Hook for subclass initialization.

        A dictionary passed as the third argument of a url spec will be
        supplied as keyword arguments to initialize().

        Example::

            class ProfileHandler(RequestHandler):
                def initialize(self, database):
                    self.database = database

                def get(self, username):
                    ...

            app = Application([
                (r'/user/(.*)', ProfileHandler, dict(database=database)),
                ])
        """
        pass

    @property
    def settings(self):
        """An alias for `self.application.settings`."""
        return self.application.settings

    def default(self, *args, **kwargs):
        """Called when a request does not match any implemented methods.

        Example::

            class ExampleHandler(RequestHandler):
                def get(self):
                    self.write('That was a GET request!')

                def default(self):
                    self.write('That was anything but a GET request!')
        """
        raise HTTPError(405)

    def prepare(self):
        """Called at the beginning of a request before `get`/`post`/etc.

        Override this method to perform common initialization regardless
        of the request method.
        """
        pass

    def on_finish(self):
        """Called after the end of a request.

        Override this method to perform cleanup, logging, etc.
        This method is a counterpart to `prepare`.  ``on_finish`` may
        not produce any output, as it is called after the response
        has been sent to the client.
        """
        pass

    def on_connection_close(self, *args, **kwargs):
        """Called in async handlers if the client closed the connection.

        Override this to clean up resources associated with
        long-lived connections.  Note that this method is called only if
        the connection was closed during asynchronous processing; if you
        need to do cleanup after every request override `on_finish`
        instead.

        Proxies may keep a connection open for a time (perhaps
        indefinitely) after the client has gone away, so this method
        may not be called promptly after the end user closes their
        connection.
        """
        pass

    def clear(self):
        """Resets all headers and content for this response."""
        # The performance cost of cyclone.httputil.HTTPHeaders is significant
        # (slowing down a benchmark with a trivial handler by more than 10%),
        # and its case-normalization is not generally necessary for
        # headers we generate on the server side, so use a plain dict
        # and list instead.
        self._headers = {
            "Server": "cyclone/%s" % cyclone.version,
            "Content-Type": "text/html; charset=UTF-8",
            "Date": datetime.datetime.utcnow().strftime(
                                                "%a, %d %b %Y %H:%M:%S GMT"),
        }
        self._list_headers = []
        self.set_default_headers()
        if not self.request.supports_http_1_1():
            if self.request.headers.get("Connection") == "Keep-Alive":
                self.set_header("Connection", "Keep-Alive")
        self._write_buffer = []
        self._status_code = 200
        self._reason = http_client.responses[200]

    def set_default_headers(self):
        """Override this to set HTTP headers at the beginning of the request.

        For example, this is the place to set a custom ``Server`` header.
        Note that setting such headers in the normal flow of request
        processing may not do what you want, since headers may be reset
        during error handling.
        """
        pass

    def set_status(self, status_code, reason=None):
        """Sets the status code for our response.

        :arg int status_code: Response status code. If `reason` is ``None``,
            it must be present in `httplib.responses`.
        :arg string reason: Human-readable reason phrase describing the status
            code. If ``None``, it will be filled in from `httplib.responses`.
        """
        self._status_code = status_code
        if reason is not None:
            self._reason = escape.native_str(reason)
        else:
            try:
                self._reason = http_client.responses[status_code]
            except KeyError:
                raise ValueError("unknown status code %d", status_code)

    def get_status(self):
        """Returns the status code for our response."""
        return self._status_code

    def set_header(self, name, value):
        """Sets the given response header name and value.

        If a datetime is given, we automatically format it according to the
        HTTP specification. If the value is not a string, we convert it to
        a string. All header values are then encoded as UTF-8.
        """
        self._headers[name] = self._convert_header_value(value)

    def add_header(self, name, value):
        """Adds the given response header and value.

        Unlike `set_header`, `add_header` may be called multiple times
        to return multiple values for the same header.
        """
        self._list_headers.append((name, self._convert_header_value(value)))

    def clear_header(self, name):
        """Clears an outgoing header, undoing a previous `set_header` call.

        Note that this method does not apply to multi-valued headers
        set by `add_header`.
        """
        if name in self._headers:
            del self._headers[name]

    def _convert_header_value(self, value):
        if isinstance(value, bytes_type):
            value = value.decode('utf-8')
        elif isinstance(value, unicode_type):
            pass
        elif isinstance(value, numbers.Integral):
            # return immediately since we know the converted value will be safe
            return str(value)
        elif isinstance(value, datetime.datetime):
            t = calendar.timegm(value.utctimetuple())
            return email.utils.formatdate(t, localtime=False, usegmt=True)
        else:
            raise TypeError("Unsupported header value %r" % value)
        # If \n is allowed into the header, it is possible to inject
        # additional headers or split the request. Also cap length to
        # prevent obviously erroneous values.
        if len(value) > 4000 or re.search(r"[\x00-\x1f]", value):
            raise ValueError("Unsafe header value %r", value)
        return value

    _ARG_DEFAULT = []

    def get_argument(self, name, default=_ARG_DEFAULT, strip=True):
        """Returns the value of the argument with the given name.

        If default is not provided, the argument is considered to be
        required, and we throw an HTTP 400 exception if it is missing.

        If the argument appears in the url more than once, we return the
        last value.

        The returned value is always unicode.
        """
        args = self.get_arguments(name, strip=strip)
        if not args:
            if default is self._ARG_DEFAULT:
                raise HTTPError(400, "Missing argument " + name)
            return default
        return args[-1]

    def get_arguments(self, name, strip=True):
        """Returns a list of the arguments with the given name.

        If the argument is not present, returns an empty list.

        The returned values are always unicode.
        """
        values = []
        for v in self.request.arguments.get(name, []):
            v = self.decode_argument(v, name=name)
            if isinstance(v, unicode_type):
                # Get rid of any weird control chars (unless decoding gave
                # us bytes, in which case leave it alone)
                v = re.sub(r"[\x00-\x08\x0e-\x1f]", " ", v)
            if strip:
                v = v.strip()
            values.append(v)
        return values

    def decode_argument(self, value, name=None):
        """Decodes an argument from the request.

        The argument has been percent-decoded and is now a byte string.
        By default, this method decodes the argument as utf-8 and returns
        a unicode string, but this may be overridden in subclasses.

        This method is used as a filter for both get_argument() and for
        values extracted from the url and passed to get()/post()/etc.

        The name of the argument is provided if known, but may be None
        (e.g. for unnamed groups in the url regex).
        """
        return _unicode(value)

    @property
    def cookies(self):
        return self.request.cookies

    def get_cookie(self, name, default=None):
        """Gets the value of the cookie with the given name, else default."""
        if self.request.cookies is not None and name in self.request.cookies:
            return self.request.cookies[name].value
        return default

    def set_cookie(self, name, value, domain=None, expires=None, path="/",
                   expires_days=None, **kwargs):
        """Sets the given cookie name/value with the given options.

        Additional keyword arguments are set on the Cookie.Morsel directly.
        See http://docs.python.org/library/cookie.html#morsel-objects
        for available attributes.
        """
        # The cookie library only accepts type str, in both python 2 and 3
        name = escape.native_str(name)
        value = escape.native_str(value)
        if re.search(r"[\x00-\x20]", name + value):
            # Don't let us accidentally inject bad stuff
            raise ValueError("Invalid cookie %r: %r" % (name, value))
        if not hasattr(self, "_new_cookie"):
            self._new_cookie = http_cookies.SimpleCookie()
        if name in self._new_cookie:
            del self._new_cookie[name]
        self._new_cookie[name] = value
        morsel = self._new_cookie[name]
        if domain:
            morsel["domain"] = domain
        if expires_days is not None and not expires:
            expires = datetime.datetime.utcnow() + datetime.timedelta(
                                                        days=expires_days)
        if expires:
            timestamp = calendar.timegm(expires.utctimetuple())
            morsel["expires"] = email.utils.formatdate(
                                    timestamp, localtime=False, usegmt=True)
        if path:
            morsel["path"] = path
        for k, v in kwargs.items():
            if k == 'max_age':
                k = 'max-age'
            morsel[k] = v

    def clear_cookie(self, name, path="/", domain=None):
        """Deletes the cookie with the given name."""
        expires = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        self.set_cookie(name, value="", path=path, expires=expires,
                        domain=domain)

    def clear_all_cookies(self):
        """Deletes all the cookies the user sent with this request."""
        for name in self.request.cookies.keys():
            self.clear_cookie(name)

    def set_secure_cookie(self, name, value, expires_days=30, **kwargs):
        """Signs and timestamps a cookie so it cannot be forged.

        You must specify the ``cookie_secret`` setting in your Application
        to use this method. It should be a long, random sequence of bytes
        to be used as the HMAC secret for the signature.

        To read a cookie set with this method, use `get_secure_cookie()`.

        Note that the ``expires_days`` parameter sets the lifetime of the
        cookie in the browser, but is independent of the ``max_age_days``
        parameter to `get_secure_cookie`.

        Secure cookies may contain arbitrary byte values, not just unicode
        strings (unlike regular cookies)
        """
        self.set_cookie(name, self.create_signed_value(name, value),
                        expires_days=expires_days, **kwargs)

    def create_signed_value(self, name, value):
        """Signs and timestamps a string so it cannot be forged.

        Normally used via set_secure_cookie, but provided as a separate
        method for non-cookie uses.  To decode a value not stored
        as a cookie use the optional value argument to get_secure_cookie.
        """
        self.require_setting("cookie_secret", "secure cookies")
        return create_signed_value(self.application.settings["cookie_secret"],
                                   name, value)

    def get_secure_cookie(self, name, value=None, max_age_days=31):
        """Returns the given signed cookie if it validates, or None.

        The decoded cookie value is returned as a byte string (unlike
        `get_cookie`).
        """
        self.require_setting("cookie_secret", "secure cookies")
        if value is None:
            value = self.get_cookie(name)
        return decode_signed_value(self.application.settings["cookie_secret"],
                                   name, value, max_age_days=max_age_days)

    def redirect(self, url, permanent=False, status=None):
        """Sends a redirect to the given (optionally relative) URL.

        If the ``status`` argument is specified, that value is used as the
        HTTP status code; otherwise either 301 (permanent) or 302
        (temporary) is chosen based on the ``permanent`` argument.
        The default is 302 (temporary).
        """
        if self._headers_written:
            raise Exception("Cannot redirect after headers have been written")
        if status is None:
            status = 301 if permanent else 302
        else:
            assert isinstance(status, int) and 300 <= status <= 399
        self.set_status(status)
        # Remove whitespace
        url = re.sub(r"[\x00-\x20]+", "", url)
        if not self.request.uri.startswith('/'):
            request_uri = ''
        if self.request.uri.startswith('//'):
            request_uri = ''
        else:
            request_uri = self.request.uri
        self.set_header("Location", urllib_parse.urljoin(request_uri, url))
        self.finish()

    def write(self, chunk):
        """Writes the given chunk to the output buffer.

        To write the output to the network, use the flush() method below.

        If the given chunk is a dictionary, we write it as JSON and set
        the Content-Type of the response to be application/json.
        (if you want to send JSON as a different Content-Type, call
        set_header *after* calling write()).

        Note that lists are not converted to JSON because of a potential
        cross-site security vulnerability.  All JSON output should be
        wrapped in a dictionary.  More details at
        http://haacked.com/archive/2008/11/20/\
            anatomy-of-a-subtle-json-vulnerability.aspx
        """

        if self._finished:
            raise RuntimeError("Cannot write() after finish().  May be caused "
                               "by using async operations without the "
                               "@asynchronous decorator.")
        if isinstance(chunk, dict) or \
                (self.serialize_lists and isinstance(chunk, list)):
            chunk = escape.json_encode(chunk)
            self.set_header("Content-Type", "application/json")
        chunk = utf8(chunk)
        self._write_buffer.append(chunk)

    def render(self, template_name, **kwargs):
        """Renders the template with the given arguments as the response."""
        d = defer.maybeDeferred(self.render_string, template_name, **kwargs)
        d.addCallback(self._insertAdditionalPageElements)
        d.addCallbacks(self.finish, self._execute_failure)
        return d

    def _insertAdditionalPageElements(self, html): # pragma: no cover
        """Insert the additional JS and CSS added by the modules on the page"""
        js_embed = []
        js_files = []
        css_embed = []
        css_files = []
        html_heads = []
        html_bodies = []
        for module in getattr(self, "_active_modules", {}).values():
            embed_part = module.embedded_javascript()
            if embed_part:
                js_embed.append(utf8(embed_part))
            file_part = module.javascript_files()
            if file_part:
                if isinstance(file_part, (unicode_type, bytes_type)):
                    js_files.append(file_part)
                else:
                    js_files.extend(file_part)
            embed_part = module.embedded_css()
            if embed_part:
                css_embed.append(utf8(embed_part))
            file_part = module.css_files()
            if file_part:
                if isinstance(file_part, (unicode_type, bytes_type)):
                    css_files.append(file_part)
                else:
                    css_files.extend(file_part)
            head_part = module.html_head()
            if head_part:
                html_heads.append(utf8(head_part))
            body_part = module.html_body()
            if body_part:
                html_bodies.append(utf8(body_part))

        def is_absolute(path):
            return any(path.startswith(x) for x in ["/", "http:", "https:"])
        if js_files:
            # Maintain order of JavaScript files given by modules
            paths = []
            unique_paths = set()
            for path in js_files:
                if not is_absolute(path):
                    path = self.static_url(path)
                if path not in unique_paths:
                    paths.append(path)
                    unique_paths.add(path)
            js = ''.join('<script src="' + escape.xhtml_escape(p) +
                         '" type="text/javascript"></script>'
                         for p in paths)
            sloc = html.rindex('</body>')
            html = html[:sloc] + utf8(js) + '\n' + html[sloc:]
        if js_embed:
            js = '<script type="text/javascript">\n//<![CDATA[\n' + \
                '\n'.join(js_embed) + '\n//]]>\n</script>'
            sloc = html.rindex('</body>')
            html = html[:sloc] + js + '\n' + html[sloc:]
        if css_files:
            paths = []
            unique_paths = set()
            for path in css_files:
                if not is_absolute(path):
                    path = self.static_url(path)
                if path not in unique_paths:
                    paths.append(path)
                    unique_paths.add(path)
            css = ''.join('<link href="' + escape.xhtml_escape(p) + '" '
                          'type="text/css" rel="stylesheet"/>'
                          for p in paths)
            hloc = html.index('</head>')
            html = html[:hloc] + utf8(css) + '\n' + html[hloc:]
        if css_embed:
            css = '<style type="text/css">\n' + '\n'.join(css_embed) + \
                '\n</style>'
            hloc = html.index('</head>')
            html = html[:hloc] + css + '\n' + html[hloc:]
        if html_heads:
            hloc = html.index('</head>')
            html = html[:hloc] + ''.join(html_heads) + '\n' + html[hloc:]
        if html_bodies:
            hloc = html.index('</body>')
            html = html[:hloc] + ''.join(html_bodies) + '\n' + html[hloc:]
        return html

    def render_string(self, template_name, **kwargs):
        """Generate the given template with the given arguments.

        We return the generated string. To generate and write a template
        as a response, use render() above.
        """
        # If no template_path is specified, use the path of the calling file
        template_path = self.get_template_path()
        if not template_path:
            frame = sys._getframe(0)
            web_file = frame.f_code.co_filename
            while frame.f_code.co_filename == web_file:
                frame = frame.f_back
            template_path = os.path.dirname(frame.f_code.co_filename)
        with RequestHandler._template_loader_lock:
            if template_path not in RequestHandler._template_loaders:
                loader = self.create_template_loader(template_path)
                RequestHandler._template_loaders[template_path] = loader
            else:
                loader = RequestHandler._template_loaders[template_path]
        t = loader.load(template_name)
        namespace = self.get_template_namespace()
        namespace.update(kwargs)
        return t.generate(**namespace)

    def get_template_namespace(self):
        """Returns a dictionary to be used as the default template namespace.

        May be overridden by subclasses to add or modify values.

        The results of this method will be combined with additional
        defaults in the `tornado.template` module and keyword arguments
        to `render` or `render_string`.
        """
        namespace = dict(
            handler=self,
            request=self.request,
            current_user=self.current_user,
            locale=self.locale,
            _=self.locale.translate,
            static_url=self.static_url,
            xsrf_form_html=self.xsrf_form_html,
            reverse_url=self.reverse_url
        )
        namespace.update(self.ui)
        return namespace

    def create_template_loader(self, template_path):
        """Returns a new template loader for the given path.

        May be overridden by subclasses.  By default returns a
        directory-based loader on the given path, using the
        ``autoescape`` application setting.  If a ``template_loader``
        application setting is supplied, uses that instead.
        """
        settings = self.application.settings
        if "template_loader" in settings:
            return settings["template_loader"]
        kwargs = {}
        if "autoescape" in settings:
            # autoescape=None means "no escaping", so we have to be sure
            # to only pass this kwarg if the user asked for it.
            kwargs["autoescape"] = settings["autoescape"]
        return template.Loader(template_path, **kwargs)

    def flush(self, include_footers=False):
        """Flushes the current output buffer to the network."""
        chunk = b"".join(self._write_buffer)
        self._write_buffer = []

        if not self._headers_written:
            self._headers_written = True
            for transform in self._transforms:
                self._status_code, self._headers, chunk = \
                    transform.transform_first_chunk(
                    self._status_code, self._headers, chunk, include_footers)
            headers = self._generate_headers()
        else:
            for transform in self._transforms:  # pragma: no cover
                chunk = transform.transform_chunk(chunk, include_footers)
            headers = b""

        # Ignore the chunk and only write the headers for HEAD requests
        if self.request.method == "HEAD":
            if headers:
                self.request.write(headers)
            return

        if headers or chunk:
            self.request.write(headers + chunk)

    def notifyFinish(self):
        """Returns a deferred, which is fired when the request is terminated
        and the connection is closed.
        """
        return self.request.notifyFinish()

    def finish(self, chunk=None):
        """Finishes this response, ending the HTTP request."""
        if self._finished:
            raise RuntimeError("finish() called twice.  May be caused "
                               "by using async operations without the "
                               "@asynchronous decorator.")

        if chunk is not None:
            self.write(chunk)

        # Automatically support ETags and add the Content-Length header if
        # we have not flushed any content yet.
        if not self._headers_written:
            if (self._status_code == 200 and
                self.request.method in ("GET", "HEAD") and
                "Etag" not in self._headers):
                etag = self.compute_etag()
                if etag is not None:
                    self.set_header("Etag", etag)
                    inm = self.request.headers.get("If-None-Match")
                    if inm and inm.find(etag) != -1:
                        self._write_buffer = []
                        self.set_status(304)
            if self._status_code == 304:
                assert not self._write_buffer, "Cannot send body with 304"
                self._clear_headers_for_304()
            elif "Content-Length" not in self._headers:
                content_length = sum(len(part) for part in self._write_buffer)
                self.set_header("Content-Length", content_length)

        self.flush(include_footers=True)
        self.request.finish()
        self._log()
        self._finished = True
        self.on_finish()

    def send_error(self, status_code=500, **kwargs):
        """Sends the given HTTP error code to the browser.

        If `flush()` has already been called, it is not possible to send
        an error, so this method will simply terminate the response.
        If output has been written but not yet flushed, it will be discarded
        and replaced with the error page.

        Override `write_error()` to customize the error page that is returned.
        Additional keyword arguments are passed through to `write_error`.
        """
        if self._headers_written:
            log.msg("Cannot send error response after headers written")
            if not self._finished:
                self.finish()
            return
        self.clear()

        reason = None
        if "exc_info" in kwargs:
            e = kwargs["exc_info"][1]
            if isinstance(e, HTTPError) and e.reason:
                reason = e.reason
        elif "exception" in kwargs:
            e = kwargs["exception"]
            if isinstance(e, HTTPAuthenticationRequired):
                args = ",".join(['%s="%s"' % (k, v)
                                 for k, v in e.kwargs.items()])
                self.set_header("WWW-Authenticate", "%s %s" %
                                (e.auth_type, args))

        self.set_status(status_code, reason=reason)
        try:
            self.write_error(status_code, **kwargs)
        except Exception as e:
            log.msg("Uncaught exception in write_error: " + str(e))
        if not self._finished:
            self.finish()

    def write_error(self, status_code, **kwargs):
        """Override to implement custom error pages.

        ``write_error`` may call `write`, `render`, `set_header`, etc
        to produce output as usual.

        If this error was caused by an uncaught exception (including
        HTTPError), an ``exc_info`` triple will be available as
        ``kwargs["exc_info"]``.  Note that this exception may not be
        the "current" exception for purposes of methods like
        ``sys.exc_info()`` or ``traceback.format_exc``.

        For historical reasons, if a method ``get_error_html`` exists,
        it will be used instead of the default ``write_error`` implementation.
        ``get_error_html`` returned a string instead of producing output
        normally, and had different semantics for exception handling.
        Users of ``get_error_html`` are encouraged to convert their code
        to override ``write_error`` instead.

        In order for error pages to be generated for paths that do not match any
        handlers, you can use the `error_handler` keyword argument when
        instantiating the ``cyclone.web.Application`` object.

        For example::

            import cyclone.web
            import httplib

            class CustomErrorPageMixin(object):
                def write_error(self, status_code, **kwargs**):
                    kwargs["code"] = status_code

                    if 'message' not in kwargs:
                        kwargs["message"] = httplib.responses[status_code]

                    try:
                        self.render("error_%d.html" % status_code, fields=kwargs)
                    except IOError:
                        self.render("error_all.html", fields=kwargs)

            class CustomErrorHandler(CustomErrorPageMixin, cyclone.web.ErrorHandler):
                pass

            class BaseHandler(CustomErrorPageMixin, cyclone.web.RequestHandler):
                ...

        Then, when constructing the ``cyclone.web.Application`` object::

            from cyclone import web

            application = web.Application([
                (r"/", MainPageHandler),
            ], error_handler=CustomErrorHandler)

        This technique is also compatible with Bottle-style applications::

            from cyclone.bottle import create_app

            # create_app takes the same arguments as run
            application = create_app(base_handler=BaseHandler,
                error_handler=CustomErrorHandler)
        """
        if hasattr(self, 'get_error_html'):
            if 'exc_info' in kwargs:
                exc_info = kwargs.pop('exc_info')
                kwargs['exception'] = exc_info[1]
                try:
                    # Put the traceback into sys.exc_info()
                    #raise exc_info[0], exc_info[1], exc_info[2]
                    raise exc_info[0].with_traceback(exc_info[1], exc_info[2])
                except Exception:
                    self.finish(self.get_error_html(status_code, **kwargs))
            else:
                self.finish(self.get_error_html(status_code, **kwargs))
            return
        if self.settings.get("debug") and "exc_info" in kwargs:
            # in debug mode, try to send a traceback
            self.set_header('Content-Type', 'text/plain')
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
            self.finish()
        else:
            self.set_header('Content-Type', 'text/html; charset=UTF-8')
            self.finish("<html><title>%(code)d: %(message)s</title>"
                        "<body>%(code)d: %(message)s</body></html>" %
                        {"code": status_code, "message": self._reason})

    @property
    def locale(self):
        """The local for the current session.

        Determined by either get_user_locale, which you can override to
        set the locale based on, e.g., a user preference stored in a
        database, or get_browser_locale, which uses the Accept-Language
        header.
        """
        if not hasattr(self, "_locale"):
            self._locale = self.get_user_locale()
            if not self._locale:
                self._locale = self.get_browser_locale()
                assert self._locale
        return self._locale

    def get_user_locale(self):
        """Override to determine the locale from the authenticated user.

        If None is returned, we fall back to get_browser_locale().

        This method should return a cyclone.locale.Locale object,
        most likely obtained via a call like cyclone.locale.get("en")
        """
        return None

    def get_browser_locale(self, default="en_US"):
        """Determines the user's locale from Accept-Language header.

        See http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.4
        """
        if "Accept-Language" in self.request.headers:
            languages = self.request.headers["Accept-Language"].split(",")
            locales = []
            for language in languages:
                parts = language.strip().split(";")
                if len(parts) > 1 and parts[1].startswith("q="):
                    try:
                        score = float(parts[1][2:])
                    except (ValueError, TypeError):
                        score = 0.0
                else:
                    score = 1.0
                locales.append((parts[0], score))
            if locales:
                locales.sort(key=lambda pair: pair[1], reverse=True)
                codes = [l[0] for l in locales]
                return locale.get(*codes)
        return locale.get(default)

    @property
    def current_user(self):
        """The authenticated user for this request.

        Determined by either get_current_user, which you can override to
        set the user based on, e.g., a cookie. If that method is not
        overridden, this method always returns None.

        We lazy-load the current user the first time this method is called
        and cache the result after that.
        """
        if not hasattr(self, "_current_user"):
            self._current_user = self.get_current_user()
        return self._current_user

    def get_current_user(self):
        """Override to determine the current user from, e.g., a cookie."""
        return None

    def get_login_url(self):
        """Override to customize the login URL based on the request.

        By default, we use the 'login_url' application setting.
        """
        self.require_setting("login_url", "@cyclone.web.authenticated")
        return self.application.settings["login_url"]

    def get_template_path(self):
        """Override to customize template path for each handler.

        By default, we use the 'template_path' application setting.
        Return None to load templates relative to the calling file.
        """
        return self.application.settings.get("template_path")

    @property
    def xsrf_token(self):
        """The XSRF-prevention token for the current user/session.

        To prevent cross-site request forgery, we set an '_xsrf' cookie
        and include the same '_xsrf' value as an argument with all POST
        requests. If the two do not match, we reject the form submission
        as a potential forgery.

        See http://en.wikipedia.org/wiki/Cross-site_request_forgery
        """
        if not hasattr(self, "_xsrf_token"):
            token = self.get_cookie(self.xsrf_cookie_name)
            if not token:
                token = binascii.b2a_hex(uuid.uuid4().bytes)
                expires_days = 30 if self.current_user else None
                self.set_cookie(self.xsrf_cookie_name, token, expires_days=expires_days)
            self._xsrf_token = token
        return self._xsrf_token

    def check_xsrf_cookie(self):
        """Verifies that the '_xsrf' cookie matches the '_xsrf' argument.

        To prevent cross-site request forgery, we set an '_xsrf'
        cookie and include the same value as a non-cookie
        field with all POST requests. If the two do not match, we
        reject the form submission as a potential forgery.

        The _xsrf value may be set as either a form field named _xsrf
        or in a custom HTTP header named X-XSRFToken or X-CSRFToken
        (the latter is accepted for compatibility with Django).

        See http://en.wikipedia.org/wiki/Cross-site_request_forgery

        Prior to release 1.1.1, this check was ignored if the HTTP header
        "X-Requested-With: XMLHTTPRequest" was present.  This exception
        has been shown to be insecure and has been removed.  For more
        information please see
        http://www.djangoproject.com/weblog/2011/feb/08/security/
        http://weblog.rubyonrails.org/2011/2/8/\
            csrf-protection-bypass-in-ruby-on-rails
        """
        token = (self.get_argument(self.xsrf_cookie_name, None) or
                 self.request.headers.get("X-Xsrftoken") or
                 self.request.headers.get("X-Csrftoken"))
        if not token:
            raise HTTPError(403, "'_xsrf' argument missing from POST")
        if self.xsrf_token != token:
            raise HTTPError(403, "XSRF cookie does not match POST argument")

    def xsrf_form_html(self):
        """An HTML <input/> element to be included with all POST forms.

        It defines the _xsrf input value, which we check on all POST
        requests to prevent cross-site request forgery. If you have set
        the 'xsrf_cookies' application setting, you must include this
        HTML within all of your HTML forms.

        See check_xsrf_cookie() above for more information.
        """
        return '<input type="hidden" name="' + self.xsrf_cookie_name + \
                '" value="' + escape.xhtml_escape(self.xsrf_token) + '"/>'

    def static_url(self, path, include_host=None):
        """Returns a static URL for the given relative static file path.

        This method requires you set the 'static_path' setting in your
        application (which specifies the root directory of your static
        files).

        We append ?v=<signature> to the returned URL, which makes our
        static file handler set an infinite expiration header on the
        returned content. The signature is based on the content of the
        file.

        By default this method returns URLs relative to the current
        host, but if ``include_host`` is true the URL returned will be
        absolute.  If this handler has an ``include_host`` attribute,
        that value will be used as the default for all `static_url`
        calls that do not pass ``include_host`` as a keyword argument.
        """
        self.require_setting("static_path", "static_url")
        static_handler_class = self.settings.get(
            "static_handler_class", StaticFileHandler)

        if include_host is None:
            include_host = getattr(self, "include_host", False)

        if include_host:
            base = self.request.protocol + "://" + self.request.host + \
                   static_handler_class.make_static_url(self.settings, path)
        else:
            base = static_handler_class.make_static_url(self.settings, path)
        return base

    def async_callback(self, callback, *args, **kwargs):
        """Obsolete - catches exceptions from the wrapped function.

        This function is unnecessary since Tornado 1.1.
        """
        if callback is None:
            return None
        if args or kwargs:
            callback = functools.partial(callback, *args, **kwargs)

        def wrapper(*args, **kwargs):
            try:
                return callback(*args, **kwargs)
            except Exception as e:
                if self._headers_written:
                    log.msg("Exception after headers written: " + e)
                else:
                    self._handle_request_exception(e)
        return wrapper

    def require_setting(self, name, feature="this feature"):
        """Raises an exception if the given app setting is not defined."""
        if not self.application.settings.get(name):
            raise Exception("You must define the '%s' setting in your "
                            "application to use %s" % (name, feature))

    def reverse_url(self, name, *args, **kwargs):
        """Alias for `Application.reverse_url`."""
        return self.application.reverse_url(name, *args, **kwargs)

    def compute_etag(self):
        """Computes the etag header to be used for this request.

        May be overridden to provide custom etag implementations,
        or may return None to disable cyclone's default etag support.
        """
        hasher = hashlib.sha1()
        for part in self._write_buffer:
            hasher.update(part)
        return '"' + hasher.hexdigest() + '"'

    def _execute(self, transforms, *args, **kwargs):
        """Executes this request with the given output transforms."""
        self._transforms = transforms
        try:
            if self.request.method not in self.SUPPORTED_METHODS:
                raise HTTPError(405)
            self.path_args = [self.decode_argument(arg) for arg in args]
            self.path_kwargs = dict((k, self.decode_argument(v, name=k))
                                    for (k, v) in kwargs.items())
            # If XSRF cookies are turned on, reject form submissions without
            # the proper cookie
            if self.request.method not in ("GET", "HEAD", "OPTIONS") and \
                    self.application.settings.get("xsrf_cookies"):  # is True
                if not getattr(self, "no_xsrf", False):
                    self.check_xsrf_cookie()
            defer.maybeDeferred(self.prepare).addCallbacks(
                    self._execute_handler,
                    lambda f: self._handle_request_exception(f.value),
                    callbackArgs=(args, kwargs))
        except Exception as e:
            self._handle_request_exception(e)

    def _deferred_handler(self, function, *args, **kwargs):
        try:
            result = function(*args, **kwargs)
        except Exception as e:
            return defer.fail(failure.Failure(
                              captureVars=defer.Deferred.debug))
        else:
            if isinstance(result, defer.Deferred):
                return result
            elif isinstance(result, types.GeneratorType):
                # This may degrade performance a bit, but at least avoid the
                # server from breaking when someone call yield without
                # decorating their handler with @inlineCallbacks.
                log.msg("[warning] %s.%s() returned a generator. "
                        "Perhaps it should be decorated with "
                        "@inlineCallbacks." % (self.__class__.__name__,
                                               self.request.method.lower()))
                return self._deferred_handler(defer.inlineCallbacks(function),
                                              *args, **kwargs)
            elif isinstance(result, failure.Failure):
                return defer.fail(result)
            else:
                return defer.succeed(result)

    def _execute_handler(self, r, args, kwargs):
        if not self._finished:
            args = [self.decode_argument(arg) for arg in args]
            kwargs = dict((k, self.decode_argument(v, name=k)) for (k, v) in kwargs.items())
            function = getattr(self, self.request.method.lower(), self.default)
            d = self._deferred_handler(function, *args, **kwargs)
            d.addCallbacks(self._execute_success, self._execute_failure)
            self.notifyFinish().addCallback(self.on_connection_close)

    def _execute_success(self, ign):
        if self._auto_finish and not self._finished:
            return self.finish()

    def _execute_failure(self, err):
        return self._handle_request_exception(err)

    def _generate_headers(self):
        reason = self._reason
        lines = [utf8(self.request.version + " " +
                      str(self._status_code) +
                      " " + reason)]
        lines.extend([(utf8(n) + b": " + utf8(v)) for n, v in itertools.chain(self._headers.items(), self._list_headers)])
        if hasattr(self, "_new_cookie"):
            for cookie in self._new_cookie.values():
                lines.append(utf8("Set-Cookie: " + cookie.OutputString(None)))
        return b"\r\n".join(lines) + b"\r\n\r\n"

    def _log(self):
        """Logs the current request.

        Sort of deprecated since this functionality was moved to the
        Application, but left in place for the benefit of existing apps
        that have overridden this method.
        """
        self.application.log_request(self)

    def _request_summary(self):
        return self.request.method + " " + self.request.uri + " (" + \
                self.request.remote_ip + ")"

    def _handle_request_exception(self, e):
        try:
            # These are normally twisted.python.failure.Failure
            if isinstance(e.value, (template.TemplateError,
                                    HTTPError, HTTPAuthenticationRequired)):
                e = e.value
        except:
            pass

        if isinstance(e, template.TemplateError):
            log.msg(str(e))
            self.send_error(500, exception=e)
        elif isinstance(e, (HTTPError, HTTPAuthenticationRequired)):
            if e.log_message and self.settings.get("debug") is True:
                log.msg(str(e))

            if e.status_code not in http_client.responses:
                log.msg("Bad HTTP status code: " + repr(e.status_code))
                e.status_code = 500

            self.send_error(e.status_code, exception=e)
        else:
            log.msg("Uncaught exception\n" + str(e))
            if self.settings.get("debug"):
                log.msg(repr(self.request))

            self.send_error(500, exception=e)

    def _ui_module(self, name, module):
        def render(*args, **kwargs):
            if not hasattr(self, "_active_modules"):
                self._active_modules = {}
            if name not in self._active_modules:
                self._active_modules[name] = module(self)
            rendered = self._active_modules[name].render(*args, **kwargs)
            return rendered
        return render

    def _ui_method(self, method):
        return lambda *args, **kwargs: method(self, *args, **kwargs)

    def _clear_headers_for_304(self):
        # 304 responses should not contain entity headers (defined in
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec7.html#sec7.1)
        # not explicitly allowed by
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.3.5
        headers = ["Allow", "Content-Encoding", "Content-Language",
                   "Content-Length", "Content-MD5", "Content-Range",
                   "Content-Type", "Last-Modified"]
        for h in headers:
            self.clear_header(h)


def asynchronous(method):
    """Wrap request handler methods with this if they are asynchronous.

    If this decorator is given, the response is not finished when the
    method returns. It is up to the request handler to call self.finish()
    to terminate the HTTP request. Without this decorator, the request is
    automatically finished when the get() or post() method returns. ::

        from twisted.internet import reactor

        class MyRequestHandler(web.RequestHandler):
            @web.asynchronous
            def get(self):
                self.write("Processing your request...")
                reactor.callLater(5, self.do_something)

            def do_something(self):
                self.finish("done!")

    It may be used for Comet and similar push techniques.
    http://en.wikipedia.org/wiki/Comet_(programming)
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        self._auto_finish = False
        return method(self, *args, **kwargs)
    return wrapper


def removeslash(method):
    """Use this decorator to remove trailing slashes from the request path.

    For example, a request to ``'/foo/'`` would redirect to ``'/foo'`` with
    this decorator. Your request handler mapping should use a regular
    expression like ``r'/foo/*'`` in conjunction with using the decorator.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.request.path.endswith("/"):
            if self.request.method in ("GET", "HEAD", "POST", "PUT", "DELETE"):
                uri = self.request.path.rstrip("/")
                if uri:  # don't try to redirect '/' to ''
                    if self.request.query:
                        uri = uri + "?" + self.request.query
                self.redirect(uri, permanent=True)
                return
            else:
                raise HTTPError(404)
        return method(self, *args, **kwargs)
    return wrapper


def addslash(method):
    """Use this decorator to add a missing trailing slash to the request path.

    For example, a request to '/foo' would redirect to '/foo/' with this
    decorator. Your request handler mapping should use a regular expression
    like r'/foo/?' in conjunction with using the decorator.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.request.path.endswith("/"):
            if self.request.method in ("GET", "HEAD", "POST", "PUT", "DELETE"):
                uri = self.request.path + "/"
                if self.request.query:
                    uri = uri + "?" + self.request.query
                self.redirect(uri, permanent=True)
                return
            raise HTTPError(404)
        return method(self, *args, **kwargs)
    return wrapper


class Application(protocol.ServerFactory):
    """A collection of request handlers that make up a web application.

    Instances of this class are callable and can be passed directly to
    HTTPServer to serve the application::

        application = web.Application([
            (r"/", MainPageHandler),
        ])
        reactor.listenTCP(8888, application)
        reactor.run()

    The constructor for this class takes in a list of URLSpec objects
    or (regexp, request_class) tuples. When we receive requests, we
    iterate over the list in order and instantiate an instance of the
    first request class whose regexp matches the request path.

    Each tuple can contain an optional third element, which should be a
    dictionary if it is present. That dictionary is passed as keyword
    arguments to the contructor of the handler. This pattern is used
    for the StaticFileHandler below (note that a StaticFileHandler
    can be installed automatically with the static_path setting described
    below)::

        application = web.Application([
            (r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ])

    We support virtual hosts with the add_handlers method, which takes in
    a host regular expression as the first argument::

        application.add_handlers(r"www\.myhost\.com", [
            (r"/article/([0-9]+)", ArticleHandler),
        ])

    You can serve static files by sending the static_path setting as a
    keyword argument. We will serve those files from the /static/ URI
    (this is configurable with the static_url_prefix setting),
    and we will serve /favicon.ico and /robots.txt from the same directory.
    A custom subclass of StaticFileHandler can be specified with the
    static_handler_class setting.

    It is also possible to customize the error pages the application generates
    in case it does not find any handler for the incoming request by using the
    `error_handler` keyword argument. This allows for consistent error pages
    across the application.

    .. attribute:: settings

       Additonal keyword arguments passed to the constructor are saved in the
       `settings` dictionary, and are often referred to in documentation as
       "application settings".
    """
    protocol = httpserver.HTTPConnection

    def __init__(self, handlers=None, default_host="",
                 transforms=None, error_handler=None, **settings):
        if transforms is None:
            self.transforms = []
            if settings.get("gzip"):
                self.transforms.append(GZipContentEncoding)
            self.transforms.append(ChunkedTransferEncoding)
        else:
            self.transforms = transforms
        self.handlers = []
        self.named_handlers = {}
        self.error_handler = error_handler or ErrorHandler
        self.default_host = default_host
        self.settings = ObjectDict(settings)
        self.ui_modules = {"linkify": _linkify,
                           "xsrf_form_html": _xsrf_form_html,
                           "Template": TemplateModule}
        self.ui_methods = {}
        self._load_ui_modules(settings.get("ui_modules", {}))
        self._load_ui_methods(settings.get("ui_methods", {}))
        if "static_path" in self.settings:
            path = self.settings["static_path"]
            handlers = list(handlers or [])
            static_url_prefix = settings.get("static_url_prefix",
                                             "/static/")
            static_handler_class = settings.get("static_handler_class",
                                                StaticFileHandler)
            static_handler_args = settings.get("static_handler_args", {})
            static_handler_args["path"] = path
            for pattern in [re.escape(static_url_prefix) + r"(.*)",
                            r"/(favicon\.ico)", r"/(robots\.txt)"]:
                handlers.insert(0, (pattern, static_handler_class,
                                    static_handler_args))
        if handlers:
            self.add_handlers(".*$", handlers)

    def add_handlers(self, host_pattern, host_handlers):
        """Appends the given handlers to our handler list.

        Host patterns are processed sequentially in the order they were
        added. All matching patterns will be considered.
        """
        if not host_pattern.endswith("$"):
            host_pattern += "$"
        handlers = []
        # The handlers with the wildcard host_pattern are a special
        # case - they're added in the constructor but should have lower
        # precedence than the more-precise handlers added later.
        # If a wildcard handler group exists, it should always be last
        # in the list, so insert new groups just before it.
        if self.handlers and self.handlers[-1][0].pattern == '.*$':
            self.handlers.insert(-1, (re.compile(host_pattern), handlers))
        else:
            self.handlers.append((re.compile(host_pattern), handlers))

        for spec in host_handlers:
            if isinstance(spec, tuple):
                assert len(spec) in (2, 3)
                pattern = spec[0]
                handler = spec[1]

                if isinstance(handler, str):
                    # import the Module and instantiate the class
                    # Must be a fully qualified name (module.ClassName)
                    try:
                        handler = import_object(handler)
                    except ImportError as e:
                        reactor.callWhenRunning(log.msg,
                            "Unable to load handler '%s' for "
                            "'%s': %s" % (handler, pattern, e))
                        continue

                if len(spec) == 3:
                    kwargs = spec[2]
                else:
                    kwargs = {}
                spec = URLSpec(pattern, handler, kwargs)
            handlers.append(spec)
            if spec.name:
                if spec.name in self.named_handlers:
                    log.msg("Multiple handlers named %s; "
                            "replacing previous value" % spec.name)
                self.named_handlers[spec.name] = spec

    def add_transform(self, transform_class):
        """Adds the given OutputTransform to our transform list."""
        self.transforms.append(transform_class)

    def _get_host_handlers(self, request):
        host = request.host.lower().split(':')[0]
        matches = []
        for pattern, handlers in self.handlers:
            if pattern.match(host):
                matches.extend(handlers)
        # Look for default host if not behind load balancer (for debugging)
        if not matches and "X-Real-Ip" not in request.headers:
            for pattern, handlers in self.handlers:
                if pattern.match(self.default_host):
                    matches.extend(handlers)
        return matches or None

    def _load_ui_methods(self, methods):
        if isinstance(methods, types.ModuleType):
            self._load_ui_methods(dict((n, getattr(methods, n))
                                       for n in dir(methods)))
        elif isinstance(methods, list):
            for m in methods:
                self._load_ui_methods(m)
        else:
            for name, fn in methods.items():
                if not name.startswith("_") and hasattr(fn, "__call__") \
                   and name[0].lower() == name[0]:
                    self.ui_methods[name] = fn

    def _load_ui_modules(self, modules):
        if isinstance(modules, types.ModuleType):
            self._load_ui_modules(dict((n, getattr(modules, n))
                                       for n in dir(modules)))
        elif isinstance(modules, list):
            for m in modules:
                self._load_ui_modules(m)
        else:
            assert isinstance(modules, dict)
            for name, cls in modules.items():
                try:
                    if issubclass(cls, UIModule):
                        self.ui_modules[name] = cls
                except TypeError:
                    pass

    def __call__(self, request):
        """Called by HTTPServer to execute the request."""
        transforms = [t(request) for t in self.transforms]
        handler = None
        args = []
        kwargs = {}
        handlers = self._get_host_handlers(request)
        if not handlers:
            handler = RedirectHandler(self, request,
                                      url="http://" + self.default_host + "/")
        else:
            for spec in handlers:
                match = spec.regex.match(request.path)
                if match:
                    handler = spec.handler_class(self, request, **spec.kwargs)
                    if spec.regex.groups:
                        # None-safe wrapper around url_unescape to handle
                        # unmatched optional groups correctly
                        def unquote(s):
                            if s is None:
                                return s
                            return escape.url_unescape(s)
                        # Pass matched groups to the handler.  Since
                        # match.groups() includes both named and
                        # unnamed groups,we want to use either groups
                        # or groupdict but not both.
                        # Note that args are passed as bytes so the handler can
                        # decide what encoding to use.

                        if spec.regex.groupindex:
                            kwargs = dict((str(k), unquote(v))
                                for (k, v) in match.groupdict().items())
                        else:
                            args = [unquote(s) for s in match.groups()]
                    break
            if not handler:
                handler = self.error_handler(self, request, status_code=404)

        # In debug mode, re-compile templates and reload static files on every
        # request so you don't need to restart to see changes
        if self.settings.get("debug"):
            with RequestHandler._template_loader_lock:
                for loader in RequestHandler._template_loaders.values():
                    loader.reset()
            StaticFileHandler.reset()

        handler._execute(transforms, *args, **kwargs)
        return handler

    def reverse_url(self, name, *args, **kwargs):
        """Returns a URL path for handler named `name`

        The handler must be added to the application as a named URLSpec.

        Args will be substituted for capturing groups in the URLSpec regex.
        They will be converted to strings if necessary, encoded as utf8,
        and url-escaped.

        Kwargs will be urlencoded and passed as named parameters.
        """
        if name in self.named_handlers:
            return self.named_handlers[name].reverse(*args, **kwargs)
        raise KeyError("%s not found in named urls" % name)

    def log_request(self, handler):
        """Writes a completed HTTP request to the logs.

        By default writes to the python root logger.  To change
        this behavior either subclass Application and override this method,
        or pass a function in the application settings dictionary as
        'log_function'.
        """
        if "log_function" in self.settings:
            self.settings["log_function"](handler)
            return

        request_time = 1000.0 * handler.request.request_time()
        log.msg("[" + handler.request.protocol + "] " +
                str(handler.get_status()) + " " + handler._request_summary() +
                " %.2fms" % request_time)


class HTTPError(Exception):
    """An exception that will turn into an HTTP error response.

    :arg int status_code: HTTP status code.  Must be listed in
        `httplib.responses` unless the ``reason`` keyword argument is given.
    :arg string log_message: Message to be written to the log for this error
        (will not be shown to the user unless the `Application` is in debug
        mode).  May contain ``%s``-style placeholders, which will be filled
        in with remaining positional parameters.
    :arg string reason: Keyword-only argument.  The HTTP "reason" phrase
        to pass in the status line along with ``status_code``.  Normally
        determined automatically from ``status_code``, but can be used
        to use a non-standard numeric code.
    """
    def __init__(self, status_code, log_message=None, *args, **kwargs):
        self.status_code = status_code
        self.log_message = log_message
        self.args = args
        self.reason = kwargs.get("reason", None)

    def __str__(self):
        if self.log_message:
            return self.log_message % self.args
        else:
            return self.reason or http_client.responses.get(self.status_code, "Unknown")


class HTTPAuthenticationRequired(HTTPError):
    """An exception that will turn into an HTTP 401, Authentication Required.

    The arguments are used to compose the ``WWW-Authenticate`` header.
    See http://en.wikipedia.org/wiki/Basic_access_authentication for details.

    :arg string auth_type: Authentication type (``Basic``, ``Digest``, etc)
    :arg string realm: Realm (Usually displayed by the browser)
    """
    def __init__(self, log_message=None,
                 auth_type="Basic", realm="Restricted Access", **kwargs):
        self.status_code = 401
        self.log_message = log_message
        self.auth_type = auth_type
        self.kwargs = kwargs
        self.kwargs["realm"] = realm


class ErrorHandler(RequestHandler):
    """Generates an error response with status_code for all requests."""
    def initialize(self, status_code):
        self.set_status(status_code)

    def prepare(self):
        raise HTTPError(self._status_code)

    def check_xsrf_cookie(self):
        # POSTs to an ErrorHandler don't actually have side effects,
        # so we don't need to check the xsrf token.  This allows POSTs
        # to the wrong url to return a 404 instead of 403.
        pass


class RedirectHandler(RequestHandler):
    """Redirects the client to the given URL for all GET requests.

    You should provide the keyword argument "url" to the handler, e.g.::

        application = web.Application([
            (r"/oldpath", web.RedirectHandler, {"url": "/newpath"}),
        ])
    """
    def initialize(self, url, permanent=True):
        self._url = url
        self._permanent = permanent

    def get(self):
        self.redirect(self._url, permanent=self._permanent)


class StaticFileHandler(RequestHandler):
    """A simple handler that can serve static content from a directory.

    To map a path to this handler for a static data directory /var/www,
    you would add a line to your application like::

        application = web.Application([
            (r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ])

    The local root directory of the content should be passed as the "path"
    argument to the handler.

    To support aggressive browser caching, if the argument "v" is given
    with the path, we set an infinite HTTP expiration header. So, if you
    want browsers to cache a file indefinitely, send them to, e.g.,
    /static/images/myimage.png?v=xxx. Override ``get_cache_time`` method for
    more fine-grained cache control.
    """
    CACHE_MAX_AGE = 86400 * 365 * 10  # 10 years

    _static_hashes = {}
    _lock = threading.Lock()  # protects _static_hashes

    def initialize(self, path, default_filename=None):
        self.root = "%s%s" % (os.path.abspath(path), os.path.sep)
        self.default_filename = default_filename

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._static_hashes = {}

    def head(self, path):
        self.get(path, include_body=False)

    def get(self, path, include_body=True):
        path = self.parse_url_path(path)
        abspath = os.path.abspath(os.path.join(self.root, path))
        # os.path.abspath strips a trailing /
        # it needs to be temporarily added back for requests to root/
        if not (abspath + os.path.sep).startswith(self.root):
            raise HTTPError(403, "%s is not in root static directory", path)
        if os.path.isdir(abspath) and self.default_filename is not None:
            # need to look at the request.path here for when path is empty
            # but there is some prefix to the path that was already
            # trimmed by the routing
            if not self.request.path.endswith("/"):
                self.redirect("%s/" % self.request.path)
            abspath = os.path.join(abspath, self.default_filename)
        if not os.path.exists(abspath):
            raise HTTPError(404)
        if not os.path.isfile(abspath):
            raise HTTPError(403, "%s is not a file", path)

        stat_result = os.stat(abspath)
        modified = datetime.datetime.fromtimestamp(stat_result[stat.ST_MTIME])

        self.set_header("Last-Modified", modified)

        mime_type, encoding = mimetypes.guess_type(abspath)
        if mime_type:
            self.set_header("Content-Type", mime_type)

        cache_time = self.get_cache_time(path, modified, mime_type)

        if cache_time > 0:
            self.set_header("Expires", "%s" % (datetime.datetime.utcnow() +
                                       datetime.timedelta(seconds=cache_time)))
            self.set_header("Cache-Control", "max-age=%s" % str(cache_time))

        self.set_extra_headers(path)

        # Check the If-Modified-Since, and don't send the result if the
        # content has not been modified
        ims_value = self.request.headers.get("If-Modified-Since")
        if ims_value is not None:
            date_tuple = email.utils.parsedate(ims_value)
            if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
            if if_since >= modified:
                self.set_status(304)
                return

        with open(abspath, "rb") as file:
            data = file.read()
            if include_body:
                self.write(data)
            else:
                assert self.request.method == "HEAD"
                self.set_header("Content-Length", len(data))

    def set_extra_headers(self, path):
        """For subclass to add extra headers to the response"""
        pass

    def get_cache_time(self, path, modified, mime_type):
        """Override to customize cache control behavior.

        Return a positive number of seconds to trigger aggressive caching or 0
        to mark resource as cacheable, only.

        By default returns cache expiry of 10 years for resources requested
        with "v" argument.
        """
        return self.CACHE_MAX_AGE if "v" in self.request.arguments else 0

    @classmethod
    def make_static_url(cls, settings, path):
        """Constructs a versioned url for the given path.

        This method may be overridden in subclasses (but note that it is
        a class method rather than an instance method).

        ``settings`` is the `Application.settings` dictionary.  ``path``
        is the static path being requested.  The url returned should be
        relative to the current host.
        """
        static_url_prefix = settings.get('static_url_prefix', '/static/')
        version_hash = cls.get_version(settings, path)
        if version_hash:
            return "%s%s?v=%s" % (static_url_prefix, path, version_hash)
        return "%s%s" % (static_url_prefix, path)

    @classmethod
    def get_version(cls, settings, path):
        """Generate the version string to be used in static URLs.

        This method may be overridden in subclasses (but note that it
        is a class method rather than a static method).  The default
        implementation uses a hash of the file's contents.

        ``settings`` is the `Application.settings` dictionary and ``path``
        is the relative location of the requested asset on the filesystem.
        The returned value should be a string, or ``None`` if no version
        could be determined.
        """
        abs_path = os.path.join(settings["static_path"], path)
        with cls._lock:
            hashes = cls._static_hashes
            if abs_path not in hashes:
                try:
                    f = open(abs_path, "rb")
                    hashes[abs_path] = hashlib.md5(f.read()).hexdigest()
                    f.close()
                except Exception:
                    log.msg("Could not open static file %r" % path)
                    hashes[abs_path] = None
            hsh = hashes.get(abs_path)
            if hsh:
                return hsh[:5]
        return None

    def parse_url_path(self, url_path):
        """Converts a static URL path into a filesystem path.

        ``url_path`` is the path component of the URL with
        ``static_url_prefix`` removed.  The return value should be
        filesystem path relative to ``static_path``.
        """
        if os.path.sep != "/":
            url_path = url_path.replace("/", os.path.sep)
        return url_path


class FallbackHandler(RequestHandler):
    """A RequestHandler that wraps another HTTP server callback.

    Tornado has this to combine RequestHandlers and WSGI handlers, but it's
    not supported in cyclone and is just here for compatibily purposes.
    """
    def initialize(self, fallback):
        self.fallback = fallback

    def prepare(self):
        self.fallback(self.request)
        self._finished = True


class OutputTransform(object):
    """A transform modifies the result of an HTTP request (e.g., GZip encoding)

    A new transform instance is created for every request. See the
    ChunkedTransferEncoding example below if you want to implement a
    new Transform.
    """
    def __init__(self, request):
        pass

    def transform_first_chunk(self, status_code, headers, chunk, finishing):
        return status_code, headers, chunk

    def transform_chunk(self, chunk, finishing):
        return chunk


class GZipContentEncoding(OutputTransform):
    """Applies the gzip content encoding to the response.

    See http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.11
    """
    CONTENT_TYPES = set([
        "text/plain", "text/html", "text/css", "text/xml",
        "application/javascript", "application/x-javascript",
        "application/xml", "application/atom+xml",
        "text/javascript", "application/json", "application/xhtml+xml"])
    MIN_LENGTH = 5

    def __init__(self, request):
        self._gzipping = request.supports_http_1_1() and \
            "gzip" in request.headers.get("Accept-Encoding", [])

    def transform_first_chunk(self, status_code, headers, chunk, finishing):
        if 'Vary' in headers:
            headers['Vary'] += ', Accept-Encoding'
        else:
            headers['Vary'] = 'Accept-Encoding'
        if self._gzipping:
            ctype = _unicode(headers.get("Content-Type", "")).split(";")[0]
            self._gzipping = (ctype in self.CONTENT_TYPES) and \
                (not finishing or len(chunk) >= self.MIN_LENGTH) and \
                (finishing or "Content-Length" not in headers) and \
                ("Content-Encoding" not in headers)
        if self._gzipping:
            headers["Content-Encoding"] = "gzip"
            self._gzip_value = BytesIO()
            self._gzip_file = gzip.GzipFile(mode="w", fileobj=self._gzip_value)
            chunk = self.transform_chunk(chunk, finishing)
            if "Content-Length" in headers:
                headers["Content-Length"] = str(len(chunk))
        return status_code, headers, chunk

    def transform_chunk(self, chunk, finishing):
        if self._gzipping:
            self._gzip_file.write(chunk)
            if finishing:
                self._gzip_file.close()
            else:
                self._gzip_file.flush()
            chunk = self._gzip_value.getvalue()
            self._gzip_value.truncate(0)
            self._gzip_value.seek(0)
        return chunk


class ChunkedTransferEncoding(OutputTransform):
    """Applies the chunked transfer encoding to the response.

    See http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.6.1
    """
    def __init__(self, request):
        self._chunking = request.supports_http_1_1()

    def transform_first_chunk(self, status_code, headers, chunk, finishing):
        # 304 responses have no body (not even a zero-length body), and so
        # should not have either Content-Length or Transfer-Encoding headers.
        if self._chunking and status_code != 304:
            # No need to chunk the output if a Content-Length is specified
            if "Content-Length" in headers or "Transfer-Encoding" in headers:
                self._chunking = False
            else:
                headers["Transfer-Encoding"] = "chunked"
                chunk = self.transform_chunk(chunk, finishing)
        return status_code, headers, chunk

    def transform_chunk(self, block, finishing):
        if self._chunking:
            # Don't write out empty chunks because that means END-OF-STREAM
            # with chunked encoding
            if block:
                block = "%s\r\n%s\r\n" % (utf8("%x" % len(block)), block)
            if finishing:
                block = "%s0\r\n\r\n" % block
        return block


def authenticated(method):
    """Decorate methods with this to require that the user be logged in."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            if self.request.method in ("GET", "HEAD"):
                url = self.get_login_url()
                if "?" not in url:
                    if urllib_parse.urlsplit(url).scheme:
                        # if login url is absolute, make next absolute too
                        next_url = self.request.full_url()
                    else:
                        next_url = self.request.uri
                    url = "%s?%s" % (url,
                                     urllib_parse.urlencode(dict(next=next_url)))
                return self.redirect(url)
            raise HTTPError(403)
        return method(self, *args, **kwargs)
    return wrapper


class UIModule(object):
    """A UI re-usable, modular unit on a page.

    UI modules often execute additional queries, and they can include
    additional CSS and JavaScript that will be included in the output
    page, which is automatically inserted on page render.
    """
    def __init__(self, handler):
        self.handler = handler
        self.request = handler.request
        self.ui = handler.ui
        self.current_user = handler.current_user
        self.locale = handler.locale

    def render(self, *args, **kwargs):
        """Overridden in subclasses to return this module's output."""
        raise NotImplementedError()

    def embedded_javascript(self):
        """Returns a JavaScript string that will be embedded in the page."""
        return None

    def javascript_files(self):
        """Returns a list of JavaScript files required by this module."""
        return None

    def embedded_css(self):
        """Returns a CSS string that will be embedded in the page."""
        return None

    def css_files(self):
        """Returns a list of CSS files required by this module."""
        return None

    def html_head(self):
        """Returns a CSS string that will be put in the <head/> element"""
        return None

    def html_body(self):
        """Returns an HTML string that will be put in the <body/> element"""
        return None

    def render_string(self, path, **kwargs):
        """Renders a template and returns it as a string."""
        return self.handler.render_string(path, **kwargs)


class _linkify(UIModule):
    def render(self, text, **kwargs):
        return escape.linkify(text, **kwargs)


class _xsrf_form_html(UIModule):
    def render(self):
        return self.handler.xsrf_form_html()


class TemplateModule(UIModule):
    """UIModule that simply renders the given template.

    {% module Template("foo.html") %} is similar to {% include "foo.html" %},
    but the module version gets its own namespace (with kwargs passed to
    Template()) instead of inheriting the outer template's namespace.

    Templates rendered through this module also get access to UIModule's
    automatic javascript/css features.  Simply call set_resources
    inside the template and give it keyword arguments corresponding to
    the methods on UIModule: {{ set_resources(js_files=static_url("my.js")) }}
    Note that these resources are output once per template file, not once
    per instantiation of the template, so they must not depend on
    any arguments to the template.
    """
    def __init__(self, handler):
        super(TemplateModule, self).__init__(handler)
        # keep resources in both a list and a dict to preserve order
        self._resource_list = []
        self._resource_dict = {}

    def render(self, path, **kwargs):
        def set_resources(**kwargs):
            if path not in self._resource_dict:
                self._resource_list.append(kwargs)
                self._resource_dict[path] = kwargs
            else:
                if self._resource_dict[path] != kwargs:
                    raise ValueError("set_resources called with different "
                                     "resources for the same template")
            return ""
        return self.render_string(path, set_resources=set_resources,
                                  **kwargs)

    def _get_resources(self, key):
        return (r[key] for r in self._resource_list if key in r)

    def embedded_javascript(self):
        return "\n".join(self._get_resources("embedded_javascript"))

    def javascript_files(self):
        result = []
        for f in self._get_resources("javascript_files"):
            if isinstance(f, (str, bytes_type)):
                result.append(f)
            else:
                result.extend(f)
        return result

    def embedded_css(self):
        return "\n".join(self._get_resources("embedded_css"))

    def css_files(self):
        result = []
        for f in self._get_resources("css_files"):
            if isinstance(f, (str, bytes_type)):
                result.append(f)
            else:
                result.extend(f)
        return result

    def html_head(self):
        return "".join(self._get_resources("html_head"))

    def html_body(self):
        return "".join(self._get_resources("html_body"))


class URLReverseError(Exception):
    """Error generating reversed URL."""


class URLSpec(object):
    """Specifies mappings between URLs and handlers."""
    def __init__(self, pattern, handler_class, kwargs=None, name=None):
        """Creates a URLSpec.

        Parameters:

        pattern: Regular expression to be matched.  Any groups in the regex
            will be passed in to the handler's get/post/etc methods as
            arguments.

        handler_class: RequestHandler subclass to be invoked.

        kwargs (optional): A dictionary of additional arguments to be passed
            to the handler's constructor.

        name (optional): A name for this handler.  Used by
            Application.reverse_url.
        """
        if not pattern.endswith('$'):
            pattern += '$'
        self.regex = re.compile(pattern)
        assert len(self.regex.groupindex) in (0, self.regex.groups), \
            ("groups in url regexes must either be all named or all "
             "positional: %r" % self.regex.pattern)
        self.handler_class = handler_class
        self.kwargs = kwargs or {}
        self.name = name
        self._path, self._group_count = self._find_groups()

    def __repr__(self):
        return '%s(%r, %s, kwargs=%r, name=%r)' % \
                (self.__class__.__name__, self.regex.pattern,
                 self.handler_class, self.kwargs, self.name)

    def _find_groups(self):
        """Returns a tuple (reverse string, group count) for a url.

        For example: Given the url pattern /([0-9]{4})/([a-z-]+)/, this method
        would return ('/%s/%s/', 2).
        """
        pattern = self.regex.pattern
        if pattern.startswith('^'):
            pattern = pattern[1:]
        if pattern.endswith('$'):
            pattern = pattern[:-1]

        if self.regex.groups != pattern.count('('):
            # The pattern is too complicated for our simplistic matching,
            # so we can't support reversing it.
            return (None, None)

        pieces = []
        for fragment in pattern.split('('):
            if ')' in fragment:
                paren_loc = fragment.index(')')
                if paren_loc >= 0:
                    pieces.append('%s' + fragment[paren_loc + 1:])
            else:
                pieces.append(fragment)

        return (''.join(pieces), self.regex.groups)

    def reverse(self, *args, **kwargs):
        if not self._path:
            raise URLReverseError(
                "Cannot reverse url regex " + self.regex.pattern
            )
        if len(args) != self._group_count:
            raise URLReverseError(
                "required number of arguments not found"
            )

        rv = self._path
        if args:
            converted_args = []
            for a in args:
                if not isinstance(a, (unicode_type, bytes_type)):
                    a = str(a)
                converted_args.append(escape.url_escape(utf8(a)))

            rv = rv % tuple(converted_args)

        if kwargs:
            items = list(kwargs.items())
            items.sort(key=lambda el: el[0])
            rv += "?" + urllib_parse.urlencode(items)
        return rv

url = URLSpec


def _time_independent_equals(a, b):
    if len(a) != len(b):
        return False
    result = 0
    if isinstance(a[0], types.IntType):  # python3 byte strings
        for x, y in zip(a, b):
            result |= x ^ y
    else:  # python2
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
    return result == 0


def create_signed_value(secret, name, value):
    timestamp = utf8(str(int(time.time())))
    value = base64.b64encode(utf8(value))
    signature = _create_signature(secret, name, value, timestamp)
    value = "|".join([value, timestamp, signature])
    return value


def decode_signed_value(secret, name, value, max_age_days=31):
    if not value:
        return None
    parts = utf8(value).split("|")
    if len(parts) != 3:
        return None
    signature = _create_signature(secret, name, parts[0], parts[1])
    if not _time_independent_equals(parts[2], signature):
        log.msg("Invalid cookie signature %r" % value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - max_age_days * 86400:
        log.msg("Expired cookie %r" % value)
        return None
    if timestamp > time.time() + 31 * 86400:
        # _cookie_signature does not hash a delimiter between the
        # parts of the cookie, so an attacker could transfer trailing
        # digits from the payload to the timestamp without altering the
        # signature.  For backwards compatibility, sanity-check timestamp
        # here instead of modifying _cookie_signature.
        log.msg("Cookie timestamp in future; possible tampering %r" % value)
        return None
    if parts[1].startswith("0"):
        log.msg("Tampered cookie %r" % value)
        return None
    try:
        return base64.b64decode(parts[0])
    except Exception:
        return None


def _create_signature(secret, *parts):
    hash = hmac.new(utf8(secret), digestmod=hashlib.sha1)
    for part in parts:
        hash.update(utf8(part))
    return utf8(hash.hexdigest())
