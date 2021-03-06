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

from twisted.python import log


def _emit(self, eventDict):
    text = log.textFromEventDict(eventDict)
    if not text:
        return
    timeStr = self.formatTime(eventDict['time'])

    log.util.untilConcludes(self.write, "%s %s\n" % (timeStr,
                                            text.replace("\n", "\n\t")))
    log.util.untilConcludes(self.flush)  # Hoorj!


# monkey patch, sorry
log.FileLogObserver.emit = _emit


class ObjectDict(dict):
    """Makes a dictionary behave like an object."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def import_object(name):
    """Imports an object by name.

    import_object('x.y.z') is equivalent to 'from x.y import z'.

    >>> import cyclone.escape
    >>> import_object('cyclone.escape') is cyclone.escape
    True
    >>> import_object('cyclone.escape.utf8') is cyclone.escape.utf8
    True
    """
    parts = name.split('.')
    obj = __import__('.'.join(parts[:-1]), None, None, [parts[-1]], 0)
    method = getattr(obj, parts[-1], None)
    if method:
        return method
    else:
        raise ImportError("No method named %s" % parts[-1])


bytes_type = bytes
unicode_type = str
basestring_type = str


def doctests():  # pragma: no cover
    import doctest
    return doctest.DocTestSuite()
