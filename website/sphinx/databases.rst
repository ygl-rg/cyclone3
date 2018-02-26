Database connections
====================

Cyclone supports a number of different databases, from RDBMs to NoSQL:

- Built-in SQLite: `cyclone.sqlite`
- Built-in Redis: `cyclone.redis`
- RDBMs like MySQL and PostgreSQL: `twisted.enterprise.adbapi <http://twistedmatrix.com/documents/current/core/howto/rdbms.html>`_
- MongoDB: `txmongo <https://github.com/fiorix/mongo-async-python-driver>`_

Here is an example of a server with both Redis and MySQL::

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
