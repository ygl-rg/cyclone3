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
from cyclone.httpclient import StringProducer, Receiver, HTTPClient, fetch
import cyclone.httpclient
from io import StringIO
from twisted.internet.defer import inlineCallbacks, Deferred, succeed, fail
from unittest.mock import Mock
#from unittest import mock
import functools
from cyclone import escape
from cyclone.web import HTTPError


class TestStringProducer(unittest.TestCase):
    @inlineCallbacks
    def test_stringproducer(self):
        text = "some text"
        producer = StringProducer(text)
        self.assertNot(producer.stopProducing())
        self.assertNot(producer.pauseProducing())
        self.assertEqual(producer.length, len(text))
        consumer = StringIO()
        yield producer.startProducing(consumer)
        self.assertEqual(consumer.getvalue(), text)


class TestReceiver(unittest.TestCase):
    def test_receiver(self):
        text = "Some text"
        mock = Mock()
        finished = Deferred().addCallback(mock)
        receiver = Receiver(finished)
        receiver.dataReceived(text)
        receiver.dataReceived(text)
        receiver.connectionLost(None)
        mock.assert_called_with("Some textSome text")


class TestHTTPClient(unittest.TestCase):
    URL = "http://example.com"

    def test_create_client(self):
        client = HTTPClient(self.URL)
        self.assertEqual(client._args, ())

    def test_create_client_with_proxy(self):
        client = HTTPClient(self.URL, proxy=("example.com", 8080))
        self.assertEqual(client.proxyConfig, ("example.com", 8080))
        self.assertEqual(client.agent._proxyEndpoint._port, 8080)
        self.assertEqual(client.agent._proxyEndpoint._host, "example.com")

    def test_ensure_method_set_properly(self):
        client = HTTPClient(self.URL, postdata="something")
        self.assertEqual(client.method, "POST")
        client = HTTPClient(self.URL)
        self.assertEqual(client.method, "GET")

    def test_ensure_contenttype_set_properly(self):
        client = HTTPClient(self.URL, postdata="something")
        self.assertEqual(
            client.headers,
            {'Content-Type': ['application/x-www-form-urlencoded']}
        )
        client = HTTPClient(self.URL, postdata="something", headers={
            "Content-Type": "nothing"
        })
        self.assertEqual(client.headers, {"Content-Type": "nothing"})

    def test_slightly_ambiguous_things(self):
        """
        Test some broken things.

        This is to make sure we dont break backwards compat
        if they are ever fixed.
        """
        client = HTTPClient(self.URL, postdata="")
        self.assertEqual(client.method, "GET")

    @inlineCallbacks
    def test_fetch_basic(self):
        client = HTTPClient("http://example.com")
        client.agent = Mock()
        _response = Mock()
        _response.code = 200
        _response.headers.getAllRawHeaders.return_value = {}
        _response.deliverBody = lambda x: x.dataReceived("done") \
            or x.connectionLost(None)
        client.agent.request.return_value = succeed(_response)
        response = yield client.fetch()
        self.assertEqual(response.body, "done")

    @inlineCallbacks
    def test_fetch_head(self):
        client = HTTPClient("http://example.com", method="HEAD")
        client.agent = Mock()
        _response = Mock()
        _response.headers.getAllRawHeaders.return_value = {}
        _response.deliverBody = lambda x: x.connectionLost(None)
        _response.code = 200
        client.agent.request.return_value = succeed(_response)
        response = yield client.fetch()
        self.assertEqual(response.body, "")

    @inlineCallbacks
    def test_fetch_redirect(self):
        client = HTTPClient("http://example.com")
        client.agent = Mock()
        client.followRedirect = True
        client.maxRedirects = 1
        _response1 = Mock()
        _response1.code = 302
        _response1.headers.getAllRawHeaders.return_value = {
            "Location": "http://example.com"
        }
        _response1.deliverBody = lambda x: x.connectionLost(None)
        _response2 = Mock()
        _response2.code = 200
        _response2.headers.getAllRawHeaders.return_value = {}
        _response2.deliverBody = lambda x: x.connectionLost(None)
        client.agent.request.side_effect = [
            succeed(_response1),
            succeed(_response2)
        ]
        response = yield client.fetch()
        self.assertEqual(response.body, "")
        self.assertEqual(_response2.headers, {})

    @inlineCallbacks
    def test_fetch_redirect_list_query(self):
        client = HTTPClient("http://example.com")
        client.agent = Mock()
        client.followRedirect = True
        client.maxRedirects = 1
        _response1 = Mock()
        _response1.code = 302
        _response1.headers.getAllRawHeaders.return_value = {
            "Location": ["http://example.com"]
        }
        _response1.deliverBody = lambda x: x.connectionLost(None)
        _response2 = Mock()
        _response2.code = 200
        _response2.headers.getAllRawHeaders.return_value = {}
        _response2.deliverBody = lambda x: x.connectionLost(None)
        client.agent.request.side_effect = [
            succeed(_response1),
            succeed(_response2)
        ]
        response = yield client.fetch()
        self.assertEqual(response.body, "")
        self.assertEqual(_response2.headers, {})

    @inlineCallbacks
    def test_fetch_redirect_empty(self):
        client = HTTPClient("http://example.com")
        client.agent = Mock()
        client.followRedirect = True
        client.maxRedirects = 1
        _response1 = Mock()
        _response1.code = 302
        _response1.headers.getAllRawHeaders.return_value = {}
        _response1.deliverBody = lambda x: x.connectionLost(None)
        _response2 = Mock()
        _response2.code = 200
        _response2.headers.getAllRawHeaders.return_value = {}
        _response2.deliverBody = lambda x: x.connectionLost(None)
        client.agent.request.side_effect = [
            succeed(_response1),
            succeed(_response2)
        ]
        response = yield client.fetch()
        self.assertEqual(response.body, "")


class FetchTest(unittest.TestCase):
    URL = "http://example.com"

    def setUp(self):
        cyclone.httpclient.HTTPClient = Mock()

    def tearDown(self):
        cyclone.httpclient.HTTPClient = HTTPClient

    def test_fetch(self):
        fetch(self.URL)
        cyclone.httpclient.HTTPClient.assert_called_with(self.URL)


class JsonRPCTest(unittest.TestCase):
    URL = "http://example.com/jsonrpc"

    def setUp(self):
        self._old_fetch = cyclone.httpclient.fetch
        cyclone.httpclient.fetch = Mock()
        self.client = cyclone.httpclient.JsonRPC(self.URL)

    def tearDown(self):
        cyclone.httpclient.fetch = self._old_fetch

    def test_create_client(self):
        client = cyclone.httpclient.JsonRPC(self.URL)
        self.assertEqual(client.__dict__['_JsonRPC__rpcId'], 0)
        self.assertEqual(client.__dict__['_JsonRPC__rpcUrl'], self.URL)

    def test_client_method_access(self):
        method = self.client.foo
        self.assertTrue(isinstance(method, functools.partial))
        self.assertTrue(method.args[0], 'foo')

    @inlineCallbacks
    def test_rpc_request(self):
        response = Mock()
        response.code = 200
        response.body = escape.json_encode({"result": True})
        cyclone.httpclient.fetch.return_value = succeed(response)
        result = yield self.client.foo()
        self.assertTrue(result)

    def test_rpc_request_error1(self):
        response = Mock()
        response.code = 404
        response.body = escape.json_encode({"result": True})
        cyclone.httpclient.fetch.return_value = fail(HTTPError(404))
        return self.assertFailure(self.client.foo(), HTTPError)

    def test_rpc_request_error2(self):
        response = Mock()
        response.code = 200
        response.body = escape.json_encode({"error": {"message": "failed"}})
        cyclone.httpclient.fetch.return_value = succeed(response)
        return self.assertFailure(self.client.foo(), Exception)

    def test_rpc_request_error_old(self):
        response = Mock()
        response.code = 200
        response.body = escape.json_encode({"error": "some error"})
        cyclone.httpclient.fetch.return_value = succeed(response)
        return self.assertFailure(self.client.foo(), Exception)

    def test_rpc_request_404(self):
        response = Mock()
        response.code = 404
        response.phrase = "Not found."
        response.body = escape.json_encode({"result": True})
        cyclone.httpclient.fetch.return_value = succeed(response)
        return self.assertFailure(self.client.foo(), HTTPError)
