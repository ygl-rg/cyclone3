Cyclone
=======
Cyclone is a web server framework for Python, that implements the Tornado API
as a Twisted protocol.

See http://cyclone.io for details.

Installation
------------

Cyclone is listed in PyPI and can be installed with pip or easy_install.
Note that the source distribution includes demo applications that are not
present when Cyclone is installed in this way, so you may wish to download a
copy of the source tarball as well.

Manual installation
-------------------

Download the latest release from http://pypi.python.org/pypi/cyclone

    tar zxvf cyclone-$VERSION.tar.gz
    cd cyclone-$VERSION
    sudo python setup.py install

The Cyclone source code is hosted on GitHub: https://github.com/fiorix/cyclone

Prerequisites
-------------

Cyclone runs on Python 2.5, 2.6 and 2.7, and requires:

- Twisted: http://twistedmatrix.com/trac/wiki/Downloads
- pyOpenSSL: https://launchpad.net/pyopenssl (only if you want SSL/TLS)

On Python 2.5, simplejson is required too.

Platforms
---------

Cyclone should run on any Unix-like platform, although for the best
performance and scalability only Linux and BSD (including BSD derivatives like
Mac OS X) are recommended.

Credits
-------

Thanks to (in no particular order):

- Nuswit Telephony API
  - Granting permission for this code to be published and sponsoring

- Gleicon Moraes
  - Testing and using on RestMQ <https://github.com/gleicon/restmq>

- Vanderson Mota
  - Patching setup.py and PyPi maintenance

- Andrew Badr
  - Fixing auth bugs and adding current Tornado's features

- Jon Oberheide
  - Syncing code with Tornado and security features/fixes

- Silas Sewell <https://github.com/silas>
  - Syncing code and minor mail fix

- Twitter Bootstrap <https://github.com/twitter/bootstrap>
  - For making our demo applications look good

- Dan Griffin <https://github.com/dgriff1>
  - WebSocket Keep-Alive for OpDemand

- Toby Padilla <https://github.com/tobypadilla>
  - WebSocket server

- Jeethu Rao <https://github.com/jeethu>
  - Minor bugfixes and patches

- Flavio Grossi <https://github.com/flaviogrossi>
  - Minor code fixes and websockets chat statistics example

- Gautam Jeyaraman <https://github.com/gautamjeyaraman>
  - Minor code fixes and patches

- DhilipSiva <https://github.com/dhilipsiva>
  - Minor patches
