.. currentmodule:: cyclone.web

Deferreds and inline callbacks
==============================

This is one of the major differences between Cyclone and Tornado, and needs
special attention. If you're not familiar with the subject, it is highly
recommended that you start by reading Twisted's documentation:
http://twistedmatrix.com/documents/current/core/howto/defer.html

Following is an example where the HTTP client `cyclone.httpclient.fetch`
returns a ``Deferred``, which is fired once the response is received::

    from cyclone.httpclient import fetch

    class MyRequestHandler(web.RequestHandler):
        @web.asynchronous
        def get(self):
            deferred = fetch("http://freegeoip.net/json/")
            deferred.addCallback(self.on_response)

        def on_response(self, response):
            self.write(response.body)
            self.finish()

Although this method seems simple, it introduces other problems. Think of
multiple queries on a database for example. Once the result set of the first
query is received, you parse it and issue a second query::

    from twisted.enterprise import adbapi

    class MySQLMixin(object):
        mysql = adbapi.ConnectionPool("MySQLdb", db="dummy")

    class MyRequestHandler(web.RequestHandler, MySQLMixin):
        @web.asynchronous
        def get(self):
            deferred = self.mysql.runQuery("SELECT 1")
            deferred.addCallback(self.on_response1)

        # here's where you handle the results of the 1st query
        def on_response1(self, response):
            ...
            deferred = self.mysql.runQuery("SELECT 2")
            deferred.addCallback(self.on_response2)

        # handle the results of the 2nd query and terminate the request
        def on_response2(self, response):
            ...
            self.finish()

Now add an HTTP client request to the mix and you're done, it becomes a real
mess and practically unmaintainable code. Debugging is even more problematic
as your software grows in complexity.

On the other hand, the use of ``Deferred`` objects is a pretty decent
approach for event based programming, and plays very well with the reactor
pattern. Combined with Python generators, ``Deferreds`` can take your
application to a whole new level, as you will see in the following section.

Inline callbacks
~~~~~~~~~~~~~~~~

Things become much easier with inline callbacks. Since generators were
introduced in Python 2.5, the implementation of `continuation
<http://en.wikipedia.org/wiki/Continuation>`_ pretty much made it possible
to write sequential code that is easy to read and maintain, and use
``Deferreds`` in a different, better way.

Check out the official documentation of `twisted.internet.defer.inlineCallbacks
<http://twistedmatrix.com/documents/current/api/twisted.internet.defer.html#inlineCallbacks>`_.

Basically, once you decorate a function with ``inlineCallbacks`` it's possible
to ``yield`` anything that returns a ``Deferred``, and get the results
directly, without having to define a callback function.

Example::

    from cyclone.httpclient import fetch
    from twisted.internet import defer

    class MyRequestHandler(web.RequestHandler):
        @defer.inlineCallbacks
        def get(self):
            response = yield fetch("http://freegeoip.net/json/")
            self.write(response.body)
            self.finish()

Now let's have a second look at the MySQL example::

    from twisted.enterprise import adbapi
    from twisted.web.client import getPage

    class MySQLMixin(object):
        mysql = adbapi.ConnectionPool("MySQLdb", db="dummy")

    class MyRequestHandler(web.RequestHandler, MySQLMixin):
        @defer.inlineCallbacks
        def get(self):
            rs1 = yield self.mysql.runQuery("SELECT 1")
            rs2 = yield self.mysql.runQuery("SELECT 2")
            xml = yield getPage("http://freegeoip.net/xml/")

Note that every function decorated with ``inlineCallbacks`` must call ``yield``
at least once, so they become a generator. They always return a ``Deferred``,
and you can never call ``return``. Instead, call ``returnValue`` to suspend
the execution and return a value (keep in mind that this is a ``Deferred``
and you're actually making it fire its callback with the value - it gets a
bit confusing here, but don't worry.)::

    from cyclone.httpclient import fetch
    from twisted.internet import defer

    class MyRequestHandler(web.RequestHandler):
        @defer.inlineCallbacks
        def get_my_location(self):
            response = yield fetch("http://freegeoip.net/xml/")
            if response.code == 200:
                defer.returnValue(response.body)
            else:
                defer.returnValue(None)

        @defer.inlineCallbacks
        def get(self):
            location = yield self.get_my_location()
            if location:
                self.write(location)
            else:
                self.write("No idea where you are.")

Error Handling
~~~~~~~~~~~~~~

One of the most common mistakes is to ``yield`` things without decorating the
handler with ``inlineCallbacks``.

Example::

    from cyclone.httpclient import fetch
    from twisted.internet import defer

    class MainHandler(web.RequestHandler):
        # @inlineCallbacks missing here
        def get(self):
            response = yield fetch("http://freegeoip.net/xml/")
            ...

Old versions of Cyclone would not catch errors like this, and therefore no
error is detected at all. The request terminates normally, but without any
content. The `Content-Length` HTTP header is set to zero.

Cyclone 1.1 and newer versions can detect when the handler returns a
generator, and automatically decorate it with ``inlineCallbacks``. It also
dumps a warning message::

    2013-01-20 17:55:11-0500 [warning] MainHandler.get() returned a generator. Perhaps it should be decorated with @inlineCallbacks.

Another common mistake is to decorate the handler with ``inlineCallback`` but
never ``yield`` anything::

        @inlineCallbacks
        def get(self):
            response = fetch("http://freegeoip.net/xml/")  # yield missing
            ...

This is captured by Twisted, and an HTTP 500 is returned along with an error
message::

    2013-01-20 16:53:03-0500 Uncaught exception
        [Failure instance: Traceback: <type 'exceptions.TypeError'>: inlineCallbacks requires <function get at 0x10b07c8c0> to produce a generator; instead got None
        cyclone/web.py:1056:_execute
        twisted/internet/defer.py:290:addCallbacks
        twisted/internet/defer.py:551:_runCallbacks
        cyclone/web.py:1066:_execute_handler
        --- <exception caught here> ---
        twisted/internet/defer.py:134:maybeDeferred
        twisted/internet/defer.py:1186:unwindGenerator
        ]
    2013-01-20 16:53:03-0500 [http] 500 GET / (127.0.0.1) 1.09ms

Last, but not least, are the errors caused by the called function - the one
that you ``yield``. The ``Deferred`` class provides both ``.addCallback`` and
``.addErrback`` methods to schedule your callbacks, and they get called when
things succeed or fail.

Example::

    from cyclone.httpclient import fetch

    class MyRequestHandler(web.RequestHandler):
        @web.asynchronous
        def get(self):
            deferred = fetch("http://freegeoip.next/json/")  # note: .next
            deferred.addCallback(self.on_response)
            deferred.addErrback(self.on_error)

        def on_response(self, response):
            ...

        def on_error(self, error):
            ...

When the handler is decorated with ``inlineCallbacks`` and you ``yield``
things, there's no way to call ``.addErrback``. It turns out that exceptions
are actually thrown right away, and if not catch may cause Cyclone to return
an HTTP 500.

This is how you handle it::

    from cyclone.httpclient import fetch
    from twisted.internet import defer

    class MainHandler(web.RequestHandler):
        @defer.inlineCallbacks
        def get(self):
            try:
                response = yield fetch("http://freegeoip.net/xml/")
            except Exception, e:
                raise web.HTTPError(503, str(e))  # Service Unavailable
            ...

Database errors
~~~~~~~~~~~~~~~

Going back to our MySQL example, plus what was covered on the previous section,
let's see how to handle database errors.

Example::

    import MySQLdb
    from twisted.enterprise import adbapi
    from twisted.python import log

    class MySQLMixin(object):
        mysql = adbapi.ConnectionPool("MySQLdb", db="dummy")

    class MyRequestHandler(web.RequestHandler, MySQLMixin):
        @defer.inlineCallbacks
        def get(self):
            try:
                rs = yield self.mysql.runQuery("SELECT 1")
            except MySQLdb.OperationalError, e:
                log.msg("MySQL error: " + str(e))
                raise web.HTTPError(503)  # Service Unavailable
            ...

If these exceptions are not catch, they make it to the handler and therefore
cause Cyclone to respond with HTTP 500.

Same goes for Redis::

    import cyclone.redis
    from twisted.internet import defer
    from twisted.python import log

    class RedisMixin(object):
        redis = cyclone.redis.lazyConnectionPool()

    class MainHandler(web.RequestHandler, RedisMixin):
        @defer.inlineCallbacks
        def get(self):
            try:
                rs = yield self.redis.get("foo")
            except cyclone.redis.RedisError, e:
                log.msg("Redis error: " + str(e))
                raise web.HTTPError(503)  # Service Unavailable

And whenever you have multiple databases on the same handler, like making
queries on both MySQL and Redis on the same request, it's better to handle
common errors elsewhere.

Like every time one of the DBs fail due to syntax errors, or because they are
temporarily disconnected, you end up with too many try/except in the code.

We recommend creating a decorator that always respond with HTTP 503 on DB
errors::

    import MySQLdb
    import functools
    import cyclone.redis
    from twisted.internet import defer
    from twisted.python import log
    from twisted.enterprise import adbapi

    def dbsafe(method):
        @defer.inlineCallbacks
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                result = yield defer.maybeDeferred(method, self, *args, **kwargs)
            except MySQLdb.OperationalError, e:
                log.msg("MySQL error: " + str(e))
            except cyclone.redis.RedisError, e:
                log.msg("Redis error: " + str(e))
            else:
                defer.returnValue(result)
            raise web.HTTPError(503)  # Service Unavailable
        return wrapper

    class DatabaseMixin(object):
        redis = cyclone.redis.lazyConnectionPool()
        mysql = adbapi.ConnectionPool("MySQLdb", db="dummy")

    class MainHandler(web.RequestHandler, DatabaseMixin):
        @dbsafe
        @defer.inlineCallbacks
        def get(self):
            rs1 = yield self.mysql.runQuery("SELECT 1")
            rs2 = yield self.redis.get("foo")
            ...

The same approach can be used for any other resource that may become
temporarily unavailable. This helps on making the server fault tolerant.

Other decorators
~~~~~~~~~~~~~~~~

When chaining decorators on a handler, just declare them in the natural order
that you expect things to happen.

Example::

    class MainHandler(web.RequestHandler):
        @web.authenticated  # make sure the user is authenticated
        @dbsafe             # avoid DB issues from breaking things
        @web.asynchronous   # only terminate the request on self.finish()
        @inlineCallbacks    # prepare for inline calls
        def get(self):
            ...
