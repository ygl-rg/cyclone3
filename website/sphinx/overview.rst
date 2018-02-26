.. currentmodule:: cyclone.web

Overview
========

`Cyclone <https://github.com/fiorix/cyclone>`_ is a web server framework
for Python, that implements the Tornado API as a Twisted protocol.

`Twisted <http://twistedmatrix.com>`_ is an event-driven network programming
framework for Python, that dates back from 2002. It's one of the most mature
libraries for non-blocking I/O available to the public. `Tornado
<http://tornadoweb.org>`_ is the open source version of FriendFeed's
web server, one of the most popular and fast web servers for Python, with
a very decent API for building web applications.

The idea is that applications built with Cyclone look like Tornado, which is
a very nice and straightforward way of structuring web applications, but
on the other hand leverage all protocols supported by twisted.

This combination provides the ground for building up hybrid servers that not
only can handle http clients very efficiently, but also serve or use e-mail,
ssh, sip, irc, etc, all concurrently.

Besides the rich feature set, there's also an effort for addressing the C10K
problem. For more information check http://www.kegel.com/c10k.html.

Here is the canonical "Hello, world" example app:

::

    import cyclone.web
    import sys

    from twisted.internet import reactor
    from twisted.python import log


    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            self.write("Hello, world")


    if __name__ == "__main__":
        application = cyclone.web.Application([
            (r"/", MainHandler)
        ])

        log.startLogging(sys.stdout)
        reactor.listenTCP(8888, application)
        reactor.run()

We attempted to clean up the code base to reduce interdependencies
between modules, so you should (theoretically) be able to use any of the
modules independently in your project without using the whole package.

Request handlers and arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Cyclone web application maps URLs or URL patterns to subclasses of
`cyclone.web.RequestHandler`. Those classes define ``get()`` or ``post()``
methods to handle HTTP ``GET`` or ``POST`` requests to that URL.

This code maps the root URL ``/`` to ``MainHandler`` and the URL pattern
``/story/([0-9]+)`` to ``StoryHandler``. Regular expression groups are
passed as arguments to the ``RequestHandler`` methods:

::

    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            self.write("You requested the main page")

    class StoryHandler(cyclone.web.RequestHandler):
        def get(self, story_id):
            self.write("You requested the story " + story_id)

    application = cyclone.web.Application([
        (r"/", MainHandler),
        (r"/story/([0-9]+)", StoryHandler),
    ])

You can get query string arguments and parse ``POST`` bodies with the
``get_argument()`` method:

::

    class MyFormHandler(cyclone.web.RequestHandler):
        def get(self):
            self.write('<html><body><form action="/myform" method="post">'
                       '<input type="text" name="message">'
                       '<input type="submit" value="Submit">'
                       '</form></body></html>')

        def post(self):
            self.set_header("Content-Type", "text/plain")
            self.write("You wrote " + self.get_argument("message"))

Uploaded files are available in ``self.request.files``, which maps names
(the name of the HTML ``<input type="file">`` element) to a list of
files. Each file is a dictionary of the form
``{"filename":..., "content_type":..., "body":...}``.

If you want to send an error response to the client, e.g., 403
Unauthorized, you can just raise a ``cyclone.web.HTTPError`` exception:

::

    if not self.user_is_logged_in():
        raise cyclone.web.HTTPError(403)

The request handler can access the object representing the current request
with ``self.request``. The ``HTTPRequest`` object includes a number of useful
attributes, including:

-  ``arguments`` - all of the ``GET`` and ``POST`` arguments
-  ``files`` - all of the uploaded files (via ``multipart/form-data``
   POST requests)
-  ``path`` - the request path (everything before the ``?``)
-  ``headers`` - the request headers

See the class definition for `cyclone.httpserver.HTTPRequest` for a
complete list of attributes.

Overriding RequestHandler methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to ``get()``/``post()``/etc, certain other methods in
``RequestHandler`` are designed to be overridden by subclasses when
necessary. On every request, the following sequence of calls takes
place:

1. A new RequestHandler object is created on each request
2. ``initialize()`` is called with keyword arguments from the
   ``Application`` configuration. (the ``initialize`` method is new in
   Tornado 1.1; in older versions subclasses would override ``__init__``
   instead). ``initialize`` should typically just save the arguments
   passed into member variables; it may not produce any output or call
   methods like ``send_error``.
3. ``prepare()`` is called. This is most useful in a base class shared
   by all of your handler subclasses, as ``prepare`` is called no matter
   which HTTP method is used. ``prepare`` may produce output; if it
   calls ``finish`` (or ``send_error``, etc), processing stops here.
4. One of the HTTP methods is called: ``get()``, ``post()``, ``put()``,
   etc. If the URL regular expression contains capturing groups, they
   are passed as arguments to this method.
5. When the request is finished, ``on_finish()`` is called.  For synchronous
   handlers this is immediately after ``get()`` (etc) return; for
   asynchronous handlers it is after the call to ``finish()``.

Here is an example demonstrating the ``initialize()`` method:

::

    class ProfileHandler(RequestHandler):
        def initialize(self, database):
            self.database = database

        def get(self, username):
            ...

    app = Application([
        (r'/user/(.*)', ProfileHandler, dict(database=database)),
        ])

Other methods designed for overriding include:

-  ``write_error(self, status_code, exc_info=None, **kwargs)`` -
   outputs HTML for use on error pages.
-  ``get_current_user(self)`` - see `User
   Authentication <#user-authentication>`_ below
-  ``get_user_locale(self)`` - returns ``locale`` object to use for the
   current user
-  ``get_login_url(self)`` - returns login url to be used by the
   ``@authenticated`` decorator (default is in ``Application`` settings)
-  ``get_template_path(self)`` - returns location of template files
   (default is in ``Application`` settings)
-  ``set_default_headers(self)`` - may be used to set additional headers
   on the response (such as a custom ``Server`` header)

Error Handling
~~~~~~~~~~~~~~

There are three ways to return an error from a `RequestHandler`:

1. Manually call `~cyclone.web.RequestHandler.set_status` and output the
   response body normally.
2. Call `~RequestHandler.send_error`.  This discards
   any pending unflushed output and calls `~RequestHandler.write_error` to
   generate an error page.
3. Raise an exception.  `cyclone.web.HTTPError` can be used to generate
   a specified status code; all other exceptions return a 500 status.
   The exception handler uses `~RequestHandler.send_error` and
   `~RequestHandler.write_error` to generate the error page.

The default error page includes a stack trace in debug mode and a one-line
description of the error (e.g. "500: Internal Server Error") otherwise.
To produce a custom error page, override `RequestHandler.write_error`.
This method may produce output normally via methods such as
`~RequestHandler.write` and `~RequestHandler.render`.  If the error was
caused by an exception, an ``exc_info`` triple will be passed as a keyword
argument (note that this exception is not guaranteed to be the current
exception in ``sys.exc_info``, so ``write_error`` must use e.g.
`traceback.format_exception` instead of `traceback.format_exc`).

In Tornado 2.0 and earlier, custom error pages were implemented by overriding
``RequestHandler.get_error_html``, which returned the error page as a string
instead of calling the normal output methods (and had slightly different
semantics for exceptions).  This method is still supported, but it is
deprecated and applications are encouraged to switch to
`RequestHandler.write_error`.

Redirection
~~~~~~~~~~~

There are two main ways you can redirect requests in Cyclone:
``self.redirect`` and with the ``RedirectHandler``.

You can use ``self.redirect`` within a ``RequestHandler`` method (like
``get``) to redirect users elsewhere. There is also an optional
parameter ``permanent`` which you can use to indicate that the
redirection is considered permanent.

This triggers a ``301 Moved Permanently`` HTTP status, which is useful
for e.g. redirecting to a canonical URL for a page in an SEO-friendly
manner.

The default value of ``permanent`` is ``False``, which is apt for things
like redirecting users on successful POST requests.

::

    self.redirect('/some-canonical-page', permanent=True)

``RedirectHandler`` is available for your use when you initialize
``Application``.

For example, notice how we redirect to a longer download URL on this
website:

::

    application = cyclone.web.Application([
        (r"/([a-z]*)", ContentHandler),
    (r"/static/file1", cyclone.web.RedirectHandler,
                            dict(url="http://server/downloads/xyz/file1")),
    ], **settings)

The default ``RedirectHandler`` status code is
``301 Moved Permanently``, but to use ``302 Found`` instead, set
``permanent`` to ``False``.

::

    application = cyclone.web.Application([
        (r"/foo", cyclone.web.RedirectHandler,
                            {"url":"/bar", "permanent":False}),
    ], **settings)

Note that the default value of ``permanent`` is different in
``self.redirect`` than in ``RedirectHandler``. This should make some
sense if you consider that ``self.redirect`` is used in your methods and
is probably invoked by logic involving environment, authentication, or
form submission, but ``RedirectHandler`` patterns are going to fire 100%
of the time they match the request URL.

Templates
~~~~~~~~~

You can use any template language supported by Python, but Cyclone ships
with its own templating language that is a lot faster and more flexible
than many of the most popular templating systems out there. See the
`cyclone.template` module documentation for complete documentation.

A Cyclone template is just HTML (or any other text-based format) with
Python control sequences and expressions embedded within the markup:

::

    <html>
       <head>
          <title>{{ title }}</title>
       </head>
       <body>
         <ul>
           {% for item in items %}
             <li>{{ escape(item) }}</li>
           {% end %}
         </ul>
       </body>
     </html>

If you saved this template as "template.html" and put it in the same
directory as your Python file, you could render this template with:

::

    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            items = ["Item 1", "Item 2", "Item 3"]
            self.render("template.html", title="My title", items=items)

Cyclone templates support *control statements* and *expressions*.
Control statements are surronded by ``{%`` and ``%}``, e.g.,
``{% if len(items) > 2 %}``. Expressions are surrounded by ``{{`` and
``}}``, e.g., ``{{ items[0] }}``.

Control statements more or less map exactly to Python statements. We
support ``if``, ``for``, ``while``, and ``try``, all of which are
terminated with ``{% end %}``. We also support *template inheritance*
using the ``extends`` and ``block`` statements, which are described in
detail in the documentation for the `cyclone.template`.

Expressions can be any Python expression, including function calls.
Template code is executed in a namespace that includes the following
objects and functions (Note that this list applies to templates rendered
using ``RequestHandler.render`` and ``render_string``. If you're using
the ``template`` module directly outside of a ``RequestHandler`` many of
these entries are not present).

-  ``escape``: alias for ``cyclone.escape.xhtml_escape``
-  ``xhtml_escape``: alias for ``cyclone.escape.xhtml_escape``
-  ``url_escape``: alias for ``cyclone.escape.url_escape``
-  ``json_encode``: alias for ``cyclone.escape.json_encode``
-  ``squeeze``: alias for ``cyclone.escape.squeeze``
-  ``linkify``: alias for ``cyclone.escape.linkify``
-  ``datetime``: the Python ``datetime`` module
-  ``handler``: the current ``RequestHandler`` object
-  ``request``: alias for ``handler.request``
-  ``current_user``: alias for ``handler.current_user``
-  ``locale``: alias for ``handler.locale``
-  ``_``: alias for ``handler.locale.translate``
-  ``static_url``: alias for ``handler.static_url``
-  ``xsrf_form_html``: alias for ``handler.xsrf_form_html``
-  ``reverse_url``: alias for ``Application.reverse_url``
-  All entries from the ``ui_methods`` and ``ui_modules``
   ``Application`` settings
-  Any keyword arguments passed to ``render`` or ``render_string``

When you are building a real application, you are going to want to use
all of the features of Cyclone templates, especially template
inheritance. Read all about those features in the `cyclone.template`
section (some features, including ``UIModules`` are implemented in the
``web`` module)

Under the hood, Cyclone templates are translated directly to Python. The
expressions you include in your template are copied verbatim into a
Python function representing your template. We don't try to prevent
anything in the template language; we created it explicitly to provide
the flexibility that other, stricter templating systems prevent.
Consequently, if you write random stuff inside of your template
expressions, you will get random Python errors when you execute the
template.

All template output is escaped by default, using the
``cyclone.escape.xhtml_escape`` function. This behavior can be changed
globally by passing ``autoescape=None`` to the ``Application`` or
``TemplateLoader`` constructors, for a template file with the
``{% autoescape None %}`` directive, or for a single expression by
replacing ``{{ ... }}`` with ``{% raw ...%}``. Additionally, in each of
these places the name of an alternative escaping function may be used
instead of ``None``.

Note that while Cyclone's automatic escaping is helpful in avoiding
XSS vulnerabilities, it is not sufficient in all cases.  Expressions
that appear in certain locations, such as in Javascript or CSS, may need
additional escaping.  Additionally, either care must be taken to always
use double quotes and ``xhtml_escape`` in HTML attributes that may contain
untrusted content, or a separate escaping function must be used for
attributes (see e.g. http://wonko.com/post/html-escaping)

Cookies and secure cookies
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can set cookies in the user's browser with the ``set_cookie``
method:

::

    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            if not self.get_cookie("mycookie"):
                self.set_cookie("mycookie", "myvalue")
                self.write("Your cookie was not set yet!")
            else:
                self.write("Your cookie was set!")

Cookies are easily forged by malicious clients. If you need to set
cookies to, e.g., save the user ID of the currently logged in user, you
need to sign your cookies to prevent forgery. Cyclone supports this out
of the box with the ``set_secure_cookie`` and ``get_secure_cookie``
methods. To use these methods, you need to specify a secret key named
``cookie_secret`` when you create your application. You can pass in
application settings as keyword arguments to your application:

::

    application = cyclone.web.Application([
        (r"/", MainHandler),
    ], cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__")

Signed cookies contain the encoded value of the cookie in addition to a
timestamp and an `HMAC <http://en.wikipedia.org/wiki/HMAC>`_ signature.
If the cookie is old or if the signature doesn't match,
``get_secure_cookie`` will return ``None`` just as if the cookie isn't
set. The secure version of the example above:

::

    class MainHandler(cyclone.web.RequestHandler):
        def get(self):
            if not self.get_secure_cookie("mycookie"):
                self.set_secure_cookie("mycookie", "myvalue")
                self.write("Your cookie was not set yet!")
            else:
                self.write("Your cookie was set!")

User authentication
~~~~~~~~~~~~~~~~~~~

The currently authenticated user is available in every request handler
as ``self.current_user``, and in every template as ``current_user``. By
default, ``current_user`` is ``None``.

To implement user authentication in your application, you need to
override the ``get_current_user()`` method in your request handlers to
determine the current user based on, e.g., the value of a cookie. Here
is an example that lets users log into the application simply by
specifying a nickname, which is then saved in a cookie:

::

    class BaseHandler(cyclone.web.RequestHandler):
        def get_current_user(self):
            return self.get_secure_cookie("user")

    class MainHandler(BaseHandler):
        def get(self):
            if not self.current_user:
                self.redirect("/login")
                return
            name = cyclone.escape.xhtml_escape(self.current_user)
            self.write("Hello, " + name)

    class LoginHandler(BaseHandler):
        def get(self):
            self.write('<html><body><form action="/login" method="post">'
                       'Name: <input type="text" name="name">'
                       '<input type="submit" value="Sign in">'
                       '</form></body></html>')

        def post(self):
            self.set_secure_cookie("user", self.get_argument("name"))
            self.redirect("/")

    application = cyclone.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
    ], cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__")

You can require that the user be logged in using the `Python
decorator <http://www.python.org/dev/peps/pep-0318/>`_
``cyclone.web.authenticated``. If a request goes to a method with this
decorator, and the user is not logged in, they will be redirected to
``login_url`` (another application setting). The example above could be
rewritten:

::

    class MainHandler(BaseHandler):
        @cyclone.web.authenticated
        def get(self):
            name = cyclone.escape.xhtml_escape(self.current_user)
            self.write("Hello, " + name)

    settings = {
        "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
    }
    application = cyclone.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
    ], **settings)

If you decorate ``post()`` methods with the ``authenticated`` decorator,
and the user is not logged in, the server will send a ``403`` response.

Cyclone comes with built-in support for third-party authentication
schemes like Google OAuth. See the `cyclone.auth`
for more details.

.. _xsrf:

Cross-site request forgery protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Cross-site request
forgery <http://en.wikipedia.org/wiki/Cross-site_request_forgery>`_, or
XSRF, is a common problem for personalized web applications. See the
`Wikipedia
article <http://en.wikipedia.org/wiki/Cross-site_request_forgery>`_ for
more information on how XSRF works.

The generally accepted solution to prevent XSRF is to cookie every user
with an unpredictable value and include that value as an additional
argument with every form submission on your site. If the cookie and the
value in the form submission do not match, then the request is likely
forged.

Cyclone comes with built-in XSRF protection. To include it in your site,
include the application setting ``xsrf_cookies``:

::

    settings = {
        "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
        "xsrf_cookies": True,
    }
    application = cyclone.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
    ], **settings)

If ``xsrf_cookies`` is set, the Cyclone web application will set the
``_xsrf`` cookie for all users and reject all ``POST``, ``PUT``, and
``DELETE`` requests that do not contain a correct ``_xsrf`` value. If
you turn this setting on, you need to instrument all forms that submit
via ``POST`` to contain this field. You can do this with the special
function ``xsrf_form_html()``, available in all templates:

::

    <form action="/new_message" method="post">
      {% module xsrf_form_html() %}
      <input type="text" name="message"/>
      <input type="submit" value="Post"/>
    </form>

If you submit AJAX ``POST`` requests, you will also need to instrument
your JavaScript to include the ``_xsrf`` value with each request. This
is the `jQuery <http://jquery.com/>`_ function used by FriendFeed for
AJAX ``POST`` requests that automatically adds the ``_xsrf`` value to
all requests:

::

    function getCookie(name) {
        var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
        return r ? r[1] : undefined;
    }

    jQuery.postJSON = function(url, args, callback) {
        args._xsrf = getCookie("_xsrf");
        $.ajax({url: url, data: $.param(args), dataType: "text", type: "POST",
            success: function(response) {
            callback(eval("(" + response + ")"));
        }});
    };

For ``PUT`` and ``DELETE`` requests (as well as ``POST`` requests that
do not use form-encoded arguments), the XSRF token may also be passed
via an HTTP header named ``X-XSRFToken``.  The XSRF cookie is normally
set when ``xsrf_form_html`` is used, but in a pure-Javascript application
that does not use any regular forms you may need to access
``self.xsrf_token`` manually (just reading the property is enough to
set the cookie as a side effect).

If you need to customize XSRF behavior on a per-handler basis, you can
override ``RequestHandler.check_xsrf_cookie()``. For example, if you
have an API whose authentication does not use cookies, you may want to
disable XSRF protection by making ``check_xsrf_cookie()`` do nothing.
However, if you support both cookie and non-cookie-based authentication,
it is important that XSRF protection be used whenever the current
request is authenticated with a cookie.

Static files and aggressive file caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can serve static files from Cyclone by specifying the
``static_path`` setting in your application:

::

    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
        "xsrf_cookies": True,
    }
    application = cyclone.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/(apple-touch-icon\.png)", cyclone.web.StaticFileHandler,
         dict(path=settings['static_path'])),
    ], **settings)

This setting will automatically make all requests that start with
``/static/`` serve from that static directory, e.g.,
`http://localhost:8888/static/foo.png <http://localhost:8888/static/foo.png>`_
will serve the file ``foo.png`` from the specified static directory. We
also automatically serve ``/robots.txt`` and ``/favicon.ico`` from the
static directory (even though they don't start with the ``/static/``
prefix).

In the above settings, we have explicitly configured Cyclone to serve
``apple-touch-icon.png`` “from” the root with the ``StaticFileHandler``,
though it is physically in the static file directory. (The capturing
group in that regular expression is necessary to tell
``StaticFileHandler`` the requested filename; capturing groups are
passed to handlers as method arguments.) You could do the same thing to
serve e.g. ``sitemap.xml`` from the site root. Of course, you can also
avoid faking a root ``apple-touch-icon.png`` by using the appropriate
``<link />`` tag in your HTML.

To improve performance, it is generally a good idea for browsers to
cache static resources aggressively so browsers won't send unnecessary
``If-Modified-Since`` or ``Etag`` requests that might block the
rendering of the page. Cyclone supports this out of the box with *static
content versioning*.

To use this feature, use the ``static_url()`` method in your templates
rather than typing the URL of the static file directly in your HTML:

::

    <html>
       <head>
          <title>FriendFeed - {{ _("Home") }}</title>
       </head>
       <body>
         <div><img src="{{ static_url("images/logo.png") }}"/></div>
       </body>
     </html>

The ``static_url()`` function will translate that relative path to a URI
that looks like ``/static/images/logo.png?v=aae54``. The ``v`` argument
is a hash of the content in ``logo.png``, and its presence makes the
Cyclone server send cache headers to the user's browser that will make
the browser cache the content indefinitely.

Since the ``v`` argument is based on the content of the file, if you
update a file and restart your server, it will start sending a new ``v``
value, so the user's browser will automatically fetch the new file. If
the file's contents don't change, the browser will continue to use a
locally cached copy without ever checking for updates on the server,
significantly improving rendering performance.

In production, you probably want to serve static files from a more
optimized static file server like `nginx <http://nginx.net/>`_. You can
configure most any web server to support these caching semantics. Here
is the nginx configuration used by FriendFeed:

::

    location /static/ {
        root /var/friendfeed/static;
        if ($query_string) {
            expires max;
        }
     }

Localization
~~~~~~~~~~~~

The locale of the current user (whether they are logged in or not) is
always available as ``self.locale`` in the request handler and as
``locale`` in templates. The name of the locale (e.g., ``en_US``) is
available as ``locale.name``, and you can translate strings with the
``locale.translate`` method. Templates also have the global function
call ``_()`` available for string translation. The translate function
has two forms:

::

    _("Translate this string")

which translates the string directly based on the current locale, and

::

    _("A person liked this", "%(num)d people liked this",
      len(people)) % {"num": len(people)}

which translates a string that can be singular or plural based on the
value of the third argument. In the example above, a translation of the
first string will be returned if ``len(people)`` is ``1``, or a
translation of the second string will be returned otherwise.

The most common pattern for translations is to use Python named
placeholders for variables (the ``%(num)d`` in the example above) since
placeholders can move around on translation.

Here is a properly localized template:

::

    <html>
       <head>
          <title>FriendFeed - {{ _("Sign in") }}</title>
       </head>
       <body>
         <form action="{{ request.path }}" method="post">
           <div>{{ _("Username") }} <input type="text" name="username"/></div>
           <div>{{ _("Password") }} <input type="password" name="password"/></div>
           <div><input type="submit" value="{{ _("Sign in") }}"/></div>
           {% module xsrf_form_html() %}
         </form>
       </body>
     </html>

By default, we detect the user's locale using the ``Accept-Language``
header sent by the user's browser. We choose ``en_US`` if we can't find
an appropriate ``Accept-Language`` value. If you let user's set their
locale as a preference, you can override this default locale selection
by overriding ``get_user_locale`` in your request handler:

::

    class BaseHandler(cyclone.web.RequestHandler):
        def get_current_user(self):
            user_id = self.get_secure_cookie("user")
            if not user_id: return None
            return self.backend.get_user_by_id(user_id)

        def get_user_locale(self):
            if "locale" not in self.current_user.prefs:
                # Use the Accept-Language header
                return None
            return self.current_user.prefs["locale"]

If ``get_user_locale`` returns ``None``, we fall back on the
``Accept-Language`` header.

You can load all the translations for your application using the
``cyclone.locale.load_translations`` method. It takes in the name of the
directory which should contain CSV files named after the locales whose
translations they contain, e.g., ``es_GT.csv`` or ``fr_CA.csv``. The
method loads all the translations from those CSV files and infers the
list of supported locales based on the presence of each CSV file. You
typically call this method once in the ``main()`` method of your server:

::

    def main():
        cyclone.locale.load_translations(
            os.path.join(os.path.dirname(__file__), "translations"))
        start_server()

You can get the list of supported locales in your application with
``cyclone.locale.get_supported_locales()``. The user's locale is chosen
to be the closest match based on the supported locales. For example, if
the user's locale is ``es_GT``, and the ``es`` locale is supported,
``self.locale`` will be ``es`` for that request. We fall back on
``en_US`` if no close match can be found.

See the `cyclone.locale` documentation for detailed information on the CSV
format and other localization methods.

.. _ui-modules:

UI modules
~~~~~~~~~~

Cyclone inherits *UI modules* from Tornado. However, there's currently no way
to support database connections and other forms of network intractivity from
within the these modules, making them a bit unuseful.

A better solution for this is still in the works and will eventually make
it to the framework one day.

Non-blocking, asynchronous requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a request handler is executed, the request is automatically finished.
Since Cyclone uses a non-blocking I/O style, you can override this default
behavior if you want a request to remain open after the main request handler
method returns using the ``cyclone.web.asynchronous`` decorator.

When you use this decorator, it is your responsibility to call
``self.finish()`` to finish the HTTP request, or the user's browser will
simply hang:

::

    class MainHandler(cyclone.web.RequestHandler):
        @cyclone.web.asynchronous
        def get(self):
            self.write("Hello, world")
            self.finish()

Here's an example::

    from twisted.internet import reactor

    class MyRequestHandler(web.RequestHandler):
        @web.asynchronous
        def get(self):
            self.write("Processing your request...")
            reactor.callLater(5, self.do_something)

        def do_something(self):
            self.write("done!")
            self.finish()

When ``get()`` returns, the request has not finished. When the reactor calls
``do_something()``, the request is still open, and the response is finally
flushed to the client with the call to ``self.finish()``.

For a more advanced asynchronous example, take a look at the `chat
example application
<https://github.com/fiorix/cyclone/tree/master/demos/chat>`_, which
implements an AJAX chat room using `long polling
<http://en.wikipedia.org/wiki/Push_technology#Long_polling>`_.  Users
of long polling may want to override ``on_connection_close()`` to
clean up after the client closes the connection (but see that method's
docstring for caveats).

Asynchronous HTTP clients
~~~~~~~~~~~~~~~~~~~~~~~~~

Cyclone ships with an HTTP client based on Twisted's Agent. It also supports
the native `twisted.web.getPage <http://twistedmatrix.com/documents/current/api/twisted.web.client.getPage.html>`_.

Example::

    from twisted.web.client import getPage

    class MyRequestHandler(web.RequestHandler):
        @web.asynchronous
        def get(self):
            deferred = getPage("http://freegeoip.net/json")
	    deferred.addCallback(self.on_response)

        def on_response(self, data):
            self.set_headers("Content-Type", "application/json")
            self.write(data)
            self.finish()

Our client returns not only the content, but also the response status and
headers::

    from cyclone.httpclient import fetch

    class MyRequestHandler(web.RequestHandler):
        @web.asynchronous
        def get(self):
            deferred = fetch("http://freegeoip.net/json")
	    deferred.addCallback(self.on_response)

        def on_response(self, response):
            if response.code == 200:
		content_type = response.headers.get("Content-Type")
                self.set_headers("Content-Type", content_type or "text/plain")
                self.write(response.body)
            	self.finish()
            else:
                raise web.HTTPError(response.code)

Third party authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~

Cyclone's ``auth`` module implements the authentication and authorization
protocols for a number of the most popular sites on the web, including
Google/Gmail, Facebook, Twitter, and FriendFeed.

The module includes methods to log users in via these sites and, where
applicable, methods to authorize access to the service so you can, e.g.,
download a user's address book or publish a Twitter message on their
behalf.

Here is an example handler that uses Google for authentication, saving
the Google credentials in a cookie for later access:

::

    class GoogleHandler(cyclone.web.RequestHandler, cyclone.auth.GoogleMixin):
        @cyclone.web.asynchronous
        def get(self):
            if self.get_argument("openid.mode", None):
                self.get_authenticated_user(self._on_auth)
                return
            self.authenticate_redirect()

        def _on_auth(self, user):
            if not user:
                self.authenticate_redirect()
                return
            # Save the user with, e.g., set_secure_cookie()

See the `cyclone.auth` module documentation for more details.

.. _debug-mode:

Debug mode and automatic reloading
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you pass ``debug=True`` to the ``Application`` constructor, the app
will be run in debug mode. In this mode, templates will not be cached
and the app will watch for changes to its source files and reload itself
when anything changes. This reduces the need to manually restart the
server during development. However, certain failures (such as syntax
errors at import time) can still take the server down in a way that
debug mode cannot currently recover from.

Running Cyclone in production
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We recommend `nginx <http://nginx.net/>`_ as a load balancer and static file
server. Run multiple instances of the Cyclone web server on multiple frontend
machines. Ideally, run one Cyclone frontend per core on the machine (or even
more depending on utilization).

When running behind a load balancer like nginx, it is recommended to
set ``xheaders=True`` to the ``Application`` constructor. This will tell
Cyclone to use headers like ``X-Real-IP`` to get the user's IP address
instead of attributing all traffic to the balancer's IP address.

This is a barebones nginx config file that is structurally similar to
the one used by FriendFeed. It assumes nginx and the Cyclone servers
are running on the same machine, and the four Cyclone servers are
running on ports 8000 - 8003:

::

    user nginx;
    worker_processes 1;

    error_log /var/log/nginx/error.log;
    pid /var/run/nginx.pid;

    events {
        worker_connections 1024;
        use epoll;
    }

    http {
        # Enumerate all the Cyclone servers here
        upstream frontends {
            server 127.0.0.1:8000;
            server 127.0.0.1:8001;
            server 127.0.0.1:8002;
            server 127.0.0.1:8003;
        }

        include /etc/nginx/mime.types;
        default_type application/octet-stream;

        access_log /var/log/nginx/access.log;

        keepalive_timeout 65;
        proxy_read_timeout 200;
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;
        gzip on;
        gzip_min_length 1000;
        gzip_proxied any;
        gzip_types text/plain text/html text/css text/xml
                   application/x-javascript application/xml
                   application/atom+xml text/javascript;

        # Only retry if there was a communication error, not a timeout
        # on the Cyclone server (to avoid propagating "queries of death"
        # to all frontends)
        proxy_next_upstream error;

        server {
            listen 80;

            # Allow file uploads
            client_max_body_size 50M;

            location ^~ /static/ {
                root /var/www;
                if ($query_string) {
                    expires max;
                }
            }
            location = /favicon.ico {
                rewrite (.*) /static/favicon.ico;
            }
            location = /robots.txt {
                rewrite (.*) /static/robots.txt;
            }

            location / {
                proxy_pass_header Server;
                proxy_set_header Host $http_host;
                proxy_redirect false;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Scheme $scheme;
                proxy_pass http://frontends;
            }
        }
    }
