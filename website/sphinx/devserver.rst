Development server and production
=================================

This section describes how to create new projects, manage the development
server and deploy in production.

Cyclone ships with the ``cyclone`` command line tool to help on creating
projects, and running your applications.

To create a new "Hello world" application::

    $ cyclone app -n > hello.py

If you need a full featured project, with Redis and MySQL support, as well
as sign up and password reset forms, check out the ``signup`` project
template::

    $ cyclone app --project=foobar --appskel=signup

Add ``--git`` to the command line if you want it to be initialized as a git
repository.

For details on creating new projects see:

.. toctree::

    app


Running
~~~~~~~

The ``cyclone`` command line is a wrapper to help on the development process.

Servers can be started like this::

    $ cyclone run hello.py

As long as there's at least one class that inherits from
`cyclone.web.Application` in the Python file - like the ``hello.py`` above.
You can also specify it using the absolute Python module path::

    $ cyclone run --app=hello.Application

Always set ``debug=True`` in `cyclone.web.Application.settings` to get more
detailed log messages, for development.

For more complex setups, like choosing different pid and log files, as well
as daemonizing your server, use ``twistd``::

    $ twistd --pidfile=/var/run/cyclone.pid --logfile=/var/log/cyclone.log \
             --reactor=epoll cyclone --port 8888 --listen 0.0.0.0 hello.py

Cyclone project templates ship with `Debian <http://debian.org>`_ init scripts
for starting the server in production. For a single instance, or for one
instance per CPU core, by setting the CPU affinity.

Faster DBs and Nginx
~~~~~~~~~~~~~~~~~~~~

Always consider using `Unix Sockets <http://en.wikipedia.org/wiki/Unix_domain_socket>`_
in production. They are considerably faster as they use less operating system
resources, like all the syn/ack on regular INET/TCP connections.

Unix Sockets may be used for database communication, as well as for Cyclone
servers behind Nginx.

Example::

    # hello.py
    import cyclone.redis
    from twisted.internet import defer
    from twisted.enterprise import adbapi

    class DatabaseMixin(object):
        redis = cyclone.redis.lazyUnixConnectionPool(path="/tmp/redis.sock")
        mysql = adbapi.ConnectionPool("MySQLdb", db="dummy",
                                      unix_socket="/tmp/mysql.sock")

    class MainHandler(web.RequestHandler, DatabaseMixin):
        @dbsafe
        @defer.inlineCallbacks
        def get(self):
            rs1 = yield self.mysql.runQuery("SELECT 1")
            rs2 = yield self.redis.get("foo")
            ...

And start one instance of this server per CPU core on the system, listening
on Unix Sockets::

    $ twistd --pidfile=/tmp/cyclone1.pid -n cyclone -u /tmp/cyclone1.sock hello.py
    $ twistd --pidfile=/tmp/cyclone2.pid -n cyclone -u /tmp/cyclone2.sock hello.py
    ...

Now make Nginx connect on Cyclone via Unix Socket, with this configuration::

    upstream backend {
      server unix:/tmp/cyclone1.sock;
      server unix:/tmp/cyclone2.sock;
    }

    server {
      listen      80;
      server_name localhost;

      location / {
        proxy_pass        http://backend;
        proxy_redirect    off;
        proxy_set_header  Host             $host;
        proxy_set_header  X-Real-IP        $remote_addr;
        proxy_set_header  X-Forwarded-For  $proxy_add_x_forwarded_for;
      }
    }

When Cyclone is reverse proxied by Nginx, you must set ``xheaders=True``
in `cyclone.web.Application.settings` so it uses ``X-Real-IP`` and
``X-Forwarded-For`` HTTP headers.

PyPy is better
~~~~~~~~~~~~~~

Cyclone runs much better on `PyPy <http://pypy.org>`_ than it does on CPython.
Turns out that Twisted is actually faster, and therefore Cyclone too.

Besides using Unix Sockets for databases and Nginx, it is highly recommended
that you run Cyclone on PyPy in production.

It has been tested on PyPy 1.8, 1.9 and 2.0-beta1 and runs well. There are
some limitations though, like PyPy 1.8 does not support OpenSSL.

If you're not familiar with setting up PyPy, try our bash script that selects
the right PyPy version for your architecture and install it on ``/opt``, with
symbolic links to ``/usr/local/bin``.

Make sure you have a compiler and openssl-dev. On Debian and Ubuntu systems,
install these packages::

    $ sudo apt-get install build-essential libssl-dev 

Then run the installer script: http://cyclone.io/install-pypy.sh
