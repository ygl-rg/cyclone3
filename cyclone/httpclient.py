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

"""Non-blocking HTTP client"""

import functools
from cyclone import escape
from cyclone.web import HTTPError

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint

from twisted.web.client import Agent, ProxyAgent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from zope.interface import implementer


agent = Agent(reactor)
proxy_agent = ProxyAgent(None, reactor)


@implementer(IBodyProducer)
class StringProducer(object):
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class Receiver(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, bytes):
        self.data.append(bytes)

    def connectionLost(self, reason):
        self.finished.callback("".join(self.data))


class HTTPClient(object):
    def __init__(self, url, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.url = url
        self.followRedirect = self._kwargs.get("followRedirect", 0)
        self.maxRedirects = self._kwargs.get("maxRedirects", 3)
        self.headers = self._kwargs.get("headers", {})
        self.body = self._kwargs.get("postdata")
        self.proxyConfig = self._kwargs.get("proxy", None)
        self.timeout = self._kwargs.get("timeout", None)
        if self.proxyConfig:
            proxyEndpoint = TCP4ClientEndpoint(
                reactor, *self.proxyConfig,
                timeout=self.timeout
            )
            self.agent = proxy_agent
            self.agent._proxyEndpoint = proxyEndpoint
        else:
            agent._connectTimeout = self.timeout
            self.agent = agent
        self.method = self._kwargs.get("method", self.body and "POST" or "GET")
        if self.method.upper() == "POST" and \
                                  "Content-Type" not in self.headers:
            self.headers["Content-Type"] = \
                        ["application/x-www-form-urlencoded"]

        self.response = None
        if self.body:
            self.body_producer = StringProducer(self.body)
        else:
            self.body_producer = None

    @defer.inlineCallbacks
    def fetch(self):
        request_headers = Headers(self.headers)
        response = yield self.agent.request(
            self.method,
            self.url,
            request_headers,
            self.body_producer)

        mr = self.maxRedirects
        while mr >= 1:
            if response.code in (301, 302, 303) and self.followRedirect:
                mr -= 1
                headers = dict(response.headers.getAllRawHeaders())
                location = headers.get("Location")
                if location:
                    if isinstance(location, list):
                        location = location[0]

                    #print("redirecting to:", location)
                    response = yield self.agent.request(
                        "GET",  # self.method,
                        location,
                        request_headers,
                        self.body_producer)
                else:
                    break
            else:
                break
        response.error = response.code >= 400
        response.headers = dict(response.headers.getAllRawHeaders())
        # HTTP 204 and 304 responses have no body
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
        # responses, which have been requested with HEAD method
        # have no body too.
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html
        if response.code in (204, 304) or self.method == 'HEAD':
            response.body = ''
        else:
            d = defer.Deferred()
            response.deliverBody(Receiver(d))
            response.body = yield d
        response.request = self
        defer.returnValue(response)


def fetch(url, *args, **kwargs):
    """A non-blocking HTTP client.

    Example::

        d = httpclient.fetch("http://google.com")
        d.addCallback(on_response)

    By default the client does not follow redirects on HTTP 301, 302, 303
    or 307.

    Parameters:

    followRedirect: Boolean, to tell the client whether to follow redirects
                    or not. [default: False]

    maxRedirects: Maximum number of redirects to follow. This is to avoid
                  infinite loops cause by misconfigured servers.

    postdata: Data that accompanies the request. If a request ``method`` is not
              set but ``postdata`` is, then it is automatically turned into
              a ``POST`` and the ``Content-Type`` is set to
              ``application/x-www-form-urlencoded``.

    headers: A python dictionary containing HTTP headers for this request.
             Note that all values must be lists::

                 headers={"Content-Type": ["application/json"]}

    The response is an object with the following attributes:

    code: HTTP server response code.

    phrase: Text that describe the response code. e.g.: 302 ``See Other``

    headers: Response headers

    length: Content length

    body: The data, untouched

    proxy: A python tuple containing host string as first member and
                        port string as second member;
                        describing which proxy to use when making request
    """
    return HTTPClient(url, *args, **kwargs).fetch()


class JsonRPC:
    """JSON-RPC client.

    Once instantiated, may be used to make multiple calls to the server.

    Example::

        cli = httpclient.JsonRPC("http://localhost:8888/jsonrpc")
        response1 = yield cli.echo("foobar")
        response2 = yield cli.sort(["foo", "bar"])

    Note that in the example above, ``echo`` and ``sort`` are remote methods
    provided by the server.

    Optional parameters of ``httpclient.fetch`` may also be used.
    """
    def __init__(self, url, *args, **kwargs):
        self.__rpcId = 0
        self.__rpcUrl = url
        self.__fetch_args = args
        self.__fetch_kwargs = kwargs

    def __getattr__(self, attr):
        return functools.partial(self.__rpcRequest, attr)

    def __rpcRequest(self, method, *args):
        q = escape.json_encode({"method": method, "params": args,
                                "id": self.__rpcId})
        self.__rpcId += 1
        r = defer.Deferred()

        fetch_kwargs = {
            'method': "POST",
            'postdata': q,
            'headers': {"Content-Type": ["application/json-rpc"]},
        }
        fetch_kwargs.update(self.__fetch_kwargs)
        d = fetch(self.__rpcUrl, *self.__fetch_args, **fetch_kwargs)

        def _success(response, deferred):
            if response.code == 200:
                data = escape.json_decode(response.body)
                error = data.get("error")
                if error:
                    if isinstance(error, dict) and 'message' in error:
                        # JSON-RPC spec is not very verbose about error schema,
                        # but it should look like {'code': 0, 'message': 'msg'}
                        deferred.errback(Exception(error['message']))
                    else:
                        # For backward compatibility with previous versions of
                        # cyclone.jsonrpc.JsonrpcRequestHandler
                        deferred.errback(Exception(error))
                else:
                    deferred.callback(data.get("result"))
            else:
                deferred.errback(HTTPError(response.code, response.phrase))

        def _failure(failure, deferred):
            deferred.errback(failure)

        d.addCallback(_success, r)
        d.addErrback(_failure, r)
        return r
