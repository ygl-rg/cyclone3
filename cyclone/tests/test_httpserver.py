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
from twisted.internet import address
from twisted.trial import unittest
from unittest.mock import Mock
from unittest import mock
from cyclone.httpserver import HTTPConnection, HTTPRequest
from twisted.internet.defer import Deferred
from twisted.test.proto_helpers import StringTransport
from twisted.internet import interfaces
from io import BytesIO
from http import cookies as http_cookies


class HTTPConnectionTest(unittest.TestCase):
    def setUp(self):
        self.con = HTTPConnection()
        self.con.factory = Mock()

    def test_connectionMade(self):
        self.con.factory.settings.get.return_value = None
        self.con.connectionMade()
        self.assertTrue(hasattr(self.con, "no_keep_alive"))
        self.assertTrue(hasattr(self.con, "content_length"))
        self.assertTrue(hasattr(self.con, "xheaders"))

    def test_connectionLost(self):
        m = Mock()
        reason = Mock()
        reason.getErrorMessage.return_value = "Some message"
        self.con._finish_callback = Deferred().addCallback(m)
        self.con.connectionLost(reason)
        m.assert_called_with("Some message")

    def test_notifyFinish(self):
        self.con.connectionMade()
        d = self.con.notifyFinish()
        self.assertIsInstance(d, Deferred)

    def test_lineReceived(self):
        self.con.connectionMade()
        line = b"Header: something"
        self.con.lineReceived(line)
        self.assertTrue(line + self.con.delimiter in self.con._headersbuffer)
        self.con._on_headers = Mock()
        self.con.lineReceived(b"")
        self.con._on_headers.assert_called_with(b'Header: something\r\n')

    def test_rawDataReceived(self):
        self.con.connectionMade()
        self.con._contentbuffer = BytesIO()
        self.con._on_request_body = Mock()
        self.con.content_length = 5
        data = b"some data"
        self.con.rawDataReceived(data)
        self.con._on_request_body.assert_called_with(b"some ")

    def test_write(self):
        self.con.transport = StringTransport()
        self.con._request = Mock()
        self.con.write(b"data")
        self.assertEqual(self.con.transport.io.getvalue(), b"data")

    def test_finish(self):
        self.con._request = Mock()
        self.con._finish_request = Mock()
        self.con.finish()
        self.con._finish_request.assert_called_with()
        self.assertTrue(self.con._request_finished)

    def test_on_write_complete(self):
        self.con._request_finished = True
        self.con._finish_request = Mock()
        self.con._on_write_complete()
        self.con._finish_request.assert_called_with()

    def test_finish_request_close(self):
        self.con.connectionMade()
        self.con.transport = Mock()
        self.con._request = Mock()
        self.con._request.headers.get.return_value = "close"
        self.con._finish_request()
        self.con.transport.loseConnection.assert_called_with()

    def test_finish_request_no_keep_alive(self):
        self.con.connectionMade()
        self.con.transport = Mock()
        self.con._request = Mock()
        self.con._request.headers = {
            "Content-Length": "1",
            "Connection": "close"
        }
        self.con._request.supports_http_1_1.return_value = False
        self.con._finish_request()
        self.con.transport.loseConnection.assert_called_with()

    def test_finish_request_no_keep_alive_setting(self):
        self.con.connectionMade()
        self.con.no_keep_alive = True
        self.con.transport = Mock()
        self.con._request = Mock()
        self.con._finish_request()
        self.con.transport.loseConnection.assert_called_with()

    def test_finish_request_head(self):
        self.con.connectionMade()
        self.con.transport = Mock()
        self.con._request = Mock()
        self.con._request.method = "HEAD"
        self.con._request.headers = {
            "Connection": "close"
        }
        self.con._request.supports_http_1_1.return_value = False
        self.con._finish_request()
        self.con.transport.loseConnection.assert_called_with()

    def test_finish_request_http1_discon(self):
        self.con.connectionMade()
        self.con.transport = Mock()
        self.con._request = Mock()
        self.con._request.method = "POST"
        self.con._request.headers = {
            "Connection": "Keep-Alive"
        }
        self.con._request.supports_http_1_1.return_value = False
        self.con._finish_request()
        self.con.transport.loseConnection.assert_called_with()

    def test_on_headers_simple(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.request_callback = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = b"GET / HTTP/1.1\r\n"
            self.con._on_headers(data)
            self.assertEqual(self.con.request_callback.call_count, 1)

    def test_on_headers_invalid(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.request_callback = Mock()
            self.con.transport = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = b"GET /"
            self.con._on_headers(data)
            self.con.transport.loseConnection.assert_called_with()

    def test_on_headers_invalid_version(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.request_callback = Mock()
            self.con.transport = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = b"GET / HTTS/1.1"
            self.con._on_headers(data)
            self.con.transport.loseConnection.assert_called_with()

    def test_on_headers_content_length(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.setRawMode = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = \
                b"GET / HTTP/1.1\r\n" \
                b"Content-Length: 5\r\n" \
                b"\r\n"
            self.con._on_headers(data)
            self.con.setRawMode.assert_called_with()
            self.assertEqual(self.con.content_length, 5)

    def test_on_headers_continue(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.transport = StringTransport()
            self.con.setRawMode = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = \
                b"GET / HTTP/1.1\r\n"\
                b"Content-Length: 5\r\n"\
                b"Expect: 100-continue"\
                b"\r\n"
            self.con._on_headers(data)
            self.assertEqual(self.con.transport.io.getvalue().strip(), b"HTTP/1.1 100 (Continue)")

    def test_on_headers_big_body(self):
        with mock.patch.object(HTTPConnection, '_remote_ip', return_value=None) as m_obj:
            self.con = HTTPConnection()
            self.con.factory = Mock()
            self.con.transport = StringTransport()
            self.con.setRawMode = Mock()
            self.con._remote_ip = "127.0.0.1"
            self.con.connectionMade()
            data = \
                b"GET / HTTP/1.1\r\n"\
                b"Content-Length: 10000000\r\n"\
                b"\r\n"
            self.con._on_headers(data)
            self.assertTrue(self.con._contentbuffer)

    def test_on_request_body_get(self):
        self.con.request_callback = Mock()
        self.con._request = Mock()
        self.con._request.method = "GET"
        self.con._request.headers = {
        }
        data = b""
        self.con._on_request_body(data)
        self.assertEqual(self.con.request_callback.call_count, 1)

    def test_on_request_body_post_form_data(self):
        self.con.request_callback = Mock()
        self.con._request = Mock()
        self.con._request.arguments = {}
        self.con._request.method = "POST"
        self.con._request.headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = "a=b"
        self.con._on_request_body(data)
        self.assertEqual(self.con.request_callback.call_count, 1)
        self.assertEqual(self.con._request.arguments, {"a": ["b"]})

    def test_on_request_body_post_multipart_form_data(self):
        self.con.request_callback = Mock()
        self.con._request = Mock()
        self.con._request.arguments = {}
        self.con._request.method = "POST"
        self.con._request.headers = {
            "Content-Type": "multipart/form-data; boundary=AaB03x"
        }
        data = \
            b"--AaB03x\r\n"\
            b'Content-Disposition: form-data; name="a"\r\n'\
            b"\r\n"\
            b"b\r\n"\
            b"--AaB03x--\r\n"
        self.con._on_request_body(data)
        self.assertEqual(self.con.request_callback.call_count, 1)
        self.assertEqual(self.con._request.arguments, {"a": [b"b"]})

    def test_remote_ip(self):
        self.con.transport = StringTransport()
        ip = self.con._remote_ip
        self.assertTrue(ip)

    def test_remote_ip_unix(self):
        self.con.transport = Mock()
        self.con.transport.getHost.return_value.name = "rawr"
        self.con.transport.getPeer.return_value = address.UNIXAddress("rawr")
        ip = self.con._remote_ip
        self.assertTrue(ip)


class HTTPRequestTest(unittest.TestCase):
    def setUp(self):
        self.req = HTTPRequest("GET", "/something")

    def test_init(self):
        req = HTTPRequest("GET", "/something")
        self.assertTrue(hasattr(req, "method"))
        self.assertTrue(hasattr(req, "uri"))
        self.assertTrue(hasattr(req, "version"))
        self.assertTrue(hasattr(req, "headers"))
        self.assertTrue(hasattr(req, "body"))
        self.assertTrue(hasattr(req, "host"))
        self.assertTrue(hasattr(req, "files"))
        self.assertTrue(hasattr(req, "connection"))
        self.assertTrue(hasattr(req, "path"))
        self.assertTrue(hasattr(req, "arguments"))
        self.assertTrue(hasattr(req, "remote_ip"))

    def test_init_with_connection_xheaders(self):
        connection = Mock()
        connection.xheaders = True
        headers = {
            "X-Real-Ip": "127.0.0.1"
        }
        req = HTTPRequest(
            "GET", "/something", headers=headers, connection=connection)
        self.assertEqual(req.remote_ip, "127.0.0.1")
        self.assertEqual(req.protocol, "http")

    def test_init_with_invalid_connection_xheaders(self):
        connection = Mock()
        connection.xheaders = True
        headers = {
            "X-Real-Ip": "256.0.0.1"
        }
        req = HTTPRequest(
            "GET", "/something", headers=headers, connection=connection)
        self.assertEqual(req.remote_ip, None)
        self.assertEqual(req.protocol, "http")

    def test_init_with_invalid_protocol_xheaders(self):
        connection = Mock()
        connection.xheaders = True
        protocol = "ftp"
        req = HTTPRequest(
            "GET", "/something", connection=connection, protocol=protocol)
        self.assertEqual(req.protocol, "http")

    def test_init_with_https(self):
        connection = Mock()
        connection.xheaders = False
        connection.transport = StringTransport()
        interfaces.ISSLTransport.providedBy = lambda x: True
        req = HTTPRequest(
            "GET", "/something", connection=connection)
        self.assertEqual(req.protocol, "https")

    def test_supports_http_1_1(self):
        req = HTTPRequest("GET", "/something", version="HTTP/1.0")
        self.assertFalse(req.supports_http_1_1())
        req = HTTPRequest("GET", "/something", version="HTTP/1.1")
        self.assertTrue(req.supports_http_1_1())

    def test_cookies_create(self):
        cookies = self.req.cookies
        self.assertFalse(cookies)

    def test_cookies_load(self):
        self.req.headers = {
            "Cookie": "a=b"
        }
        cookies = self.req.cookies
        self.assertEqual(cookies['a'].value, 'b')

    def test_cookies_invalid(self):
        self.req.headers = {
            "Cookie": "a"
        }

        def throw_exc(ignore):
            raise Exception()

        old_cookie = http_cookies.SimpleCookie
        http_cookies.SimpleCookie = Mock()
        http_cookies.SimpleCookie.return_value.load = throw_exc
        self.req.cookies
        cookies = self.req.cookies
        self.assertEqual(cookies, {})
        http_cookies.SimpleCookie = old_cookie

    def test_full_url(self):
        expected = "http://127.0.0.1/something"
        self.assertEqual(self.req.full_url(), expected)

    def test_request_time_empty_finish(self):
        self.req._finish_time = None
        self.assertTrue(self.req.request_time() < 0.01)

    def test_request_time(self):
        self.assertTrue(self.req.request_time() < 0.01)

    def test_repr(self):
        """
        Purely for coverage.
        """
        repr(self.req)
