# cyclone-based project

    This is the source code of $project_name
    $name <$email>


## About

This file has been created automatically by cyclone for $project_name.
It contains the following:

- ``start.sh``: simple shell script to start the development server
- ``$modname.conf``: configuration file for the web server
- ``$modname/``: web server code
- ``frontend/``: static files, templates and locales
- ``scripts/``: debian init scripts and other useful scripts


### Running

For development and testing:

    twistd -n cyclone --help
    twistd -n cyclone -r $modname.web.Application [--help]

    or just run ./start.sh


For production:

    twistd cyclone \
            --logfile=/var/log/$project.log \
            --pidfile=/var/run/$project.pid \
            -r $modname.web.Application

    or check scripts/debian-init.d and scripts/debian-multicore-init.d


## Customization

This section is dedicated to explaining how to customize your brand new
package.


### Databases

cyclone provides built-in support for SQLite and Redis databases.
It also supports any RDBM supported by the ``twisted.enterprise.adbapi``
module, like MySQL or PostgreSQL.

The default configuration file ``$modname.conf`` ships with pre-configured
settings for SQLite, Redis and MySQL.

The code for loading all the database settings is in ``$modname/config.py``
and is required by this application.

Take a look at ``$modname/storage.py``, which is where persistent database
connections are initialized.

This template uses the experimental ``$modname/txdbapi.py`` for interacting
with MySQL.


### Email

Please edit ``$modname.conf`` and adjust the email settings. This server
sends email on user sign up, and to reset passwords.


### Internationalization

cyclone uses the standard ``gettext`` library for dealing with string
translation.

Make sure you have the ``gettext`` package installed. If you don't, you won't
be able to translate your software.

For installing the ``gettext`` package on Debian and Ubuntu systems, do this:

    apt-get install gettext

For Mac OS X, I'd suggest using [HomeBrew](http://mxcl.github.com/homebrew>).
If you already use HomeBrew, run:

    brew install gettext
    brew link gettext

For generating translatable files for HTML and Python code of your software,
run this:

    cat frontend/template/*.html $modname/*.py | python scripts/localefix.py | xgettext - --language=Python --from-code=utf-8 --keyword=_:1,2 -d $modname

Then translate $modname.po, compile and copy to the appropriate locale
directory:

    (pt_BR is used as example here)
    vi $modname.po
    mkdir -p frontend/locale/pt_BR/LC_MESSAGES/
    msgfmt $modname.po -o frontend/locale/pt_BR/LC_MESSAGES/$modname.mo

There are sample translations for both Spanish and Portuguese in this package,
already compiled.


### Cookie Secret

The current cookie secret key in ``$modname.conf`` was generated during the
creation of this package. However, if you need a new one, you may run the
``scripts/cookie_secret.py`` script to generate a random key.

## Credits

- [cyclone](http://github.com/fiorix/cyclone) web server.
